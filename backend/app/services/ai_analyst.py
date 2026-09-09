"""AI Analyst: natural-language question -> validated SQL -> live results -> summary.

Guarantees
----------
* SQL is always shown to the user before/with results.
* SQL is validated by ``sql_guard`` (single read-only SELECT, allow-listed
  tables) and executed on the read-only pool. Invalid SQL is never run.
* The summary + recommendation are constrained to the numbers actually
  returned. With an LLM key set, a second call does the write-up under a strict
  "use only these rows" instruction. Without a key, a deterministic template
  restates the real numbers and gives a generic, clearly-labelled recommendation.
* No number is ever invented.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .. import sql_guard
from ..catalog import get_query
from ..config import get_settings
from ..db import run_readonly
from ..schema_context import build_system_prompt

_DISCLAIMER = (
    "Numbers are computed live from the synthetic XenoPulse database. "
    "No values in this response are estimated or invented."
)


# --------------------------------------------------------------------------
# Rule-based fallback (works with zero external dependencies)
# --------------------------------------------------------------------------
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(rfm|segment(ation)?)\b", re.I), "02_rfm_segments"),
    (re.compile(r"\bcohort\b|\bretention\b", re.I), "03_cohort_retention"),
    (re.compile(r"at[- ]risk|laps(e|ing)|win[- ]?back", re.I), "04_at_risk_customers"),
    (re.compile(r"\bfunnel\b|\broas\b|conversion rate|campaign.*perform", re.I), "05_campaign_funnel"),
    (re.compile(r"campaign.*segment|segment.*campaign", re.I), "06_campaign_perf_by_segment"),
    (re.compile(r"repeat.*(rate|purchase)|repeat buyer", re.I), "07_repeat_purchase_rate"),
    (re.compile(r"top .*product|best[- ]sell|pareto|80/20", re.I), "08_top_products_pareto"),
    (re.compile(r"new vs returning|returning revenue|first order revenue", re.I), "09_new_vs_returning_revenue"),
    (re.compile(r"inactiv|churn|dormant", re.I), "10_inactivity_churn"),
    (re.compile(r"revenue.*(trend|month)|monthly revenue|sales trend", re.I), "01_revenue_trend"),
]

_INLINE: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"how many customers|total customers|customer count", re.I),
        "SELECT count(*) AS total_customers, "
        "count(*) FILTER (WHERE email IS NULL) AS customers_missing_email FROM customers",
    ),
    (
        re.compile(r"average order value|\baov\b", re.I),
        "SELECT round(avg(net_amount), 2) AS avg_order_value, count(*) AS completed_orders "
        "FROM orders WHERE status = 'completed'",
    ),
    (
        re.compile(r"total revenue|overall revenue|lifetime revenue", re.I),
        "SELECT round(sum(net_amount), 2) AS total_net_revenue, count(*) AS completed_orders "
        "FROM orders WHERE status = 'completed'",
    ),
    (
        re.compile(r"revenue by (channel|acquisition)", re.I),
        "SELECT c.acquisition_channel, round(sum(o.net_amount), 2) AS net_revenue, "
        "count(DISTINCT o.customer_id) AS buyers "
        "FROM customers c JOIN orders o ON o.customer_id = c.customer_id "
        "WHERE o.status = 'completed' GROUP BY 1 ORDER BY net_revenue DESC",
    ),
    (
        re.compile(r"revenue by (category|product category)", re.I),
        "SELECT p.category, round(sum(oi.line_total), 2) AS revenue, sum(oi.quantity) AS units "
        "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id AND o.status = 'completed' "
        "JOIN products p ON p.product_id = oi.product_id GROUP BY 1 ORDER BY revenue DESC",
    ),
]


def rule_based_sql(question: str) -> tuple[str | None, str | None]:
    for pattern, qid in _RULES:
        if pattern.search(question):
            cq = get_query(qid)
            if cq:
                return cq.sql, f"catalog:{qid}"
    for pattern, sql in _INLINE:
        if pattern.search(question):
            return sql, "inline-template"
    return None, None


# --------------------------------------------------------------------------
# LLM path
# --------------------------------------------------------------------------
def _anthropic_client():
    try:
        import anthropic  # noqa: PLC0415
    except ImportError:
        return None
    key = get_settings().anthropic_api_key
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def llm_generate_sql(question: str) -> tuple[str | None, str | None, str | None]:
    client = _anthropic_client()
    if client is None:
        return None, None, None
    settings = get_settings()
    try:
        msg = client.messages.create(
            model=settings.ai_model,
            max_tokens=settings.ai_max_tokens,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": f"Q: {question}\nSQL:"}],
        )
        raw = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    except Exception as exc:  # noqa: BLE001 - fall back cleanly
        return None, None, f"LLM call failed: {exc}"
    parsed = _extract_json(raw)
    sql = (parsed.get("sql") or "").strip()
    if not sql:
        return None, None, "Model did not return SQL for this question."
    return sql, settings.ai_model, None


def llm_summarise(question: str, columns: list[str], rows: list[dict]) -> dict[str, Any] | None:
    client = _anthropic_client()
    if client is None:
        return None
    settings = get_settings()
    sample = rows[:50]
    payload = json.dumps({"question": question, "columns": columns, "rows": sample}, default=str)
    system = (
        "You are a retail data analyst. You are given a question and the EXACT rows "
        "returned by a SQL query. Use ONLY numbers present in these rows. Do not "
        "estimate, extrapolate, or introduce any figure that is not in the data. If "
        "the data is insufficient, say so.\n"
        'Respond ONLY with minified JSON: {"summary": "...", "finding": "...", '
        '"evidence": "...", "recommendation": "...", "expected_impact": "...", '
        '"next_step": "..."}. "evidence" must quote specific numbers from the rows.'
    )
    try:
        msg = client.messages.create(
            model=settings.ai_model,
            max_tokens=settings.ai_max_tokens,
            system=system,
            messages=[{"role": "user", "content": payload}],
        )
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception:  # noqa: BLE001
        return None
    parsed = _extract_json(raw)
    return parsed or None


# --------------------------------------------------------------------------
# Deterministic summary (no LLM)
# --------------------------------------------------------------------------
def template_summarise(question: str, columns: list[str], rows: list[dict]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "summary": "The query ran successfully but returned no rows.",
            "finding": "No records match the question as interpreted.",
            "evidence": "0 rows returned.",
            "recommendation": "Broaden the time window or filters and re-run.",
            "expected_impact": "n/a",
            "next_step": "Try a related question from the SQL Workspace catalog.",
        }
    first = rows[0]
    numeric_cols = [c for c in columns if isinstance(first.get(c), (int, float))]
    highlights = ", ".join(f"{c} = {first.get(c)}" for c in (numeric_cols or columns)[:4])
    return {
        "summary": (
            f"Query returned {n} row(s) with columns: {', '.join(columns)}. "
            f"Top row: {highlights}."
        ),
        "finding": f"Leading result: {highlights}.",
        "evidence": f"{n} row(s); first-row values -> {highlights}.",
        "recommendation": (
            "Review the full result table below and compare the leading segments / "
            "periods against target. (LLM summarisation is disabled — set "
            "ANTHROPIC_API_KEY for a written analysis.)"
        ),
        "expected_impact": "Not estimated without an LLM; use the numbers in the table directly.",
        "next_step": "Open this query in the SQL Workspace to slice further.",
    }


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def answer(question: str, execute: bool = True) -> dict[str, Any]:
    settings = get_settings()
    question = question.strip()

    sql, model, gen_error = llm_generate_sql(question)
    engine = "llm"
    if sql is None:
        rb_sql, rb_src = rule_based_sql(question)
        if rb_sql is None:
            return {
                "ok": False,
                "question": question,
                "engine": "rule-based",
                "model": None,
                "error": (
                    "Could not map this question to a known query"
                    + (f" ({gen_error})" if gen_error else "")
                    + ". Pick a question from the SQL Workspace catalog, or set "
                    "ANTHROPIC_API_KEY to enable free-form NL-to-SQL."
                ),
                "disclaimer": _DISCLAIMER,
            }
        sql, engine, model = rb_sql, "rule-based", rb_src

    # ---- validate ----
    try:
        validated = sql_guard.validate(sql, settings.query_row_limit)
    except sql_guard.SqlNotAllowed as exc:
        return {
            "ok": False,
            "question": question,
            "engine": engine,
            "model": model,
            "sql": sql,
            "sql_valid": False,
            "validation_error": str(exc),
            "error": "Generated SQL failed the read-only guard and was not executed.",
            "disclaimer": _DISCLAIMER,
        }

    if not execute:
        return {
            "ok": True,
            "question": question,
            "engine": engine,
            "model": model,
            "sql": validated.original,
            "sql_valid": True,
            "tables": validated.tables,
            "disclaimer": _DISCLAIMER,
        }

    # ---- run ----
    started = time.perf_counter()
    result = run_readonly(validated.safe_sql, settings.query_row_limit)
    exec_ms = round((time.perf_counter() - started) * 1000, 2)

    # ---- summarise ----
    written = llm_summarise(question, result.columns, result.rows) if settings.ai_enabled else None
    summary_engine = "llm"
    if not written:
        written = template_summarise(question, result.columns, result.rows)
        summary_engine = "template"

    rec = {
        "finding": written.get("finding", ""),
        "evidence": written.get("evidence", ""),
        "recommendation": written.get("recommendation", ""),
        "expected_impact": written.get("expected_impact", ""),
        "next_step": written.get("next_step", ""),
    }

    return {
        "ok": True,
        "question": question,
        "engine": engine,
        "model": model,
        "summary_engine": summary_engine,
        "sql": validated.original,
        "executed_sql": validated.safe_sql,
        "sql_valid": True,
        "tables": validated.tables,
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "execution_ms": exec_ms,
        "summary": written.get("summary", ""),
        "recommendation": rec,
        "disclaimer": _DISCLAIMER,
    }
