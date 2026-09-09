"""Query Performance Lab.

Runs REAL before/after benchmarks against the live database. For each scenario
we:

  1. put the DB into the "before" state (e.g. drop an index, or use the naive
     query),
  2. run ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`` twice (discard the cold
     run, keep the warm one),
  3. put the DB into the "after" state (create the index / use the rewrite),
  4. EXPLAIN ANALYZE again,
  5. restore the production index set,
  6. return both plans plus a parsed comparison.

Nothing here is hardcoded -- execution time, buffers and row counts all come
straight out of the query planner. Scenario SQL is fully server-defined; the
only user input is a scenario id that must match a known key.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..db import app_pool

_run_lock = threading.Lock()


@dataclass
class Scenario:
    id: str
    title: str
    category: str
    problem: str
    technique: str
    # DDL/statements to reach each state (list of plain SQL strings)
    before_setup: list[str] = field(default_factory=list)
    after_setup: list[str] = field(default_factory=list)
    restore: list[str] = field(default_factory=list)
    query_before: str = ""
    query_after: str = ""
    requires_table: str | None = None
    takeaway: str = ""


# --------------------------------------------------------------------------
# Scenario definitions
# --------------------------------------------------------------------------
_CE_FUNNEL_QUERY = """
SELECT ce.campaign_id,
       count(*)      AS conversions,
       sum(ce.revenue) AS revenue
FROM campaign_events ce
WHERE ce.event_type = 'convert'
  AND ce.event_time >= now() - interval '365 days'
GROUP BY ce.campaign_id
ORDER BY revenue DESC
"""

_LTV_QUERY_NAIVE = """
SELECT o.customer_id, sum(o.net_amount) AS lifetime_net, count(*) AS orders
FROM orders o
WHERE o.status = 'completed'
GROUP BY o.customer_id
"""

_CATEGORY_REVENUE_BAD = """
SELECT p.category, sum(oi.line_total) AS revenue, count(DISTINCT o.order_id) AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p     ON p.product_id = oi.product_id
WHERE to_char(o.order_date, 'YYYY-MM-DD') >= to_char(now() - interval '45 days', 'YYYY-MM-DD')
  AND o.status = 'completed'
GROUP BY p.category
ORDER BY revenue DESC
"""

_CATEGORY_REVENUE_GOOD = """
WITH recent_orders AS (
    SELECT o.order_id
    FROM orders o
    WHERE o.order_date >= now() - interval '45 days'
      AND o.status = 'completed'
)
SELECT p.category, sum(oi.line_total) AS revenue, count(DISTINCT oi.order_id) AS orders
FROM recent_orders ro
JOIN order_items oi ON oi.order_id = ro.order_id
JOIN products p     ON p.product_id = oi.product_id
GROUP BY p.category
ORDER BY revenue DESC
"""

_SELECT_STAR_BAD = """
SELECT *
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.customer_id BETWEEN 1000 AND 3000
"""

_SELECT_STAR_GOOD = """
SELECT o.order_id, o.customer_id, o.net_amount
FROM orders o
WHERE o.customer_id BETWEEN 1000 AND 3000
  AND o.status = 'completed'
"""

_PART_QUERY = """
SELECT date_trunc('day', event_time) AS day, count(*) AS events, sum(revenue) AS revenue
FROM {table}
WHERE event_time >= date '2024-06-01'
  AND event_time <  date '2024-07-01'
GROUP BY 1
ORDER BY 1
"""

SCENARIOS: dict[str, Scenario] = {
    "index_event_type_time": Scenario(
        id="index_event_type_time",
        title="B-tree index on a high-selectivity filter",
        category="Indexing",
        problem=(
            "Conversion revenue by campaign filters campaign_events (~1.4M rows) on "
            "event_type='convert' plus a time range. Without a supporting index the "
            "planner has no choice but a full sequential scan."
        ),
        technique="CREATE INDEX ix_campaign_events_type_time (event_type, event_time) INCLUDE (campaign_id, revenue)",
        before_setup=["DROP INDEX IF EXISTS ix_campaign_events_type_time"],
        after_setup=[
            "CREATE INDEX ix_campaign_events_type_time ON campaign_events (event_type, event_time) INCLUDE (campaign_id, revenue)",
            "ANALYZE campaign_events",
        ],
        restore=[
            "CREATE INDEX IF NOT EXISTS ix_campaign_events_type_time ON campaign_events (event_type, event_time) INCLUDE (campaign_id, revenue)",
        ],
        query_before=_CE_FUNNEL_QUERY,
        query_after=_CE_FUNNEL_QUERY,
        takeaway=(
            "A composite index on (filter_col, range_col) turns a full scan into a "
            "bounded index range scan; the INCLUDE columns let it stay index-only."
        ),
    ),
    "filter_before_join": Scenario(
        id="filter_before_join",
        title="Filter before the join (and keep predicates sargable)",
        category="Join optimization",
        problem=(
            "Revenue by category for the last 45 days. The naive version joins all "
            "orders to all order_items to products first, and wraps order_date in "
            "to_char() so the date index can't be used. The planner materialises a "
            "huge join then throws most of it away."
        ),
        technique="Pre-filter orders in a CTE with a sargable range predicate, then join only the survivors.",
        before_setup=[],
        after_setup=[],
        restore=[],
        query_before=_CATEGORY_REVENUE_BAD,
        query_after=_CATEGORY_REVENUE_GOOD,
        takeaway=(
            "Cutting the driving row set before the join, and keeping the date "
            "predicate index-friendly (no function on the column), is usually a "
            "bigger win than any single index."
        ),
    ),
    "avoid_select_star": Scenario(
        id="avoid_select_star",
        title="Avoid SELECT * — let a covering index answer the query",
        category="Projection",
        problem=(
            "SELECT * across an orders/order_items join drags every wide column "
            "through memory and forces heap fetches. The report only needs three "
            "columns from orders."
        ),
        technique="Project only the needed columns; a covering INCLUDE index then serves an Index Only Scan.",
        before_setup=["DROP INDEX IF EXISTS ix_orders_cust_status_incl"],
        after_setup=[
            "CREATE INDEX ix_orders_cust_status_incl ON orders (customer_id, status) INCLUDE (net_amount, order_date)",
            "ANALYZE orders",
        ],
        restore=[
            "CREATE INDEX IF NOT EXISTS ix_orders_cust_status_incl ON orders (customer_id, status) INCLUDE (net_amount, order_date)",
        ],
        query_before=_SELECT_STAR_BAD,
        query_after=_SELECT_STAR_GOOD,
        takeaway=(
            "Narrow projection shrinks buffers and enables Index Only Scans. "
            "SELECT * also silently breaks those the moment a wide column is added."
        ),
    ),
    "aggregation_covering_index": Scenario(
        id="aggregation_covering_index",
        title="Aggregation on a covering / partial index",
        category="Aggregation optimization",
        problem=(
            "Customer lifetime value aggregates every completed order. On a bare "
            "table that is a full scan feeding a HashAggregate."
        ),
        technique="Covering index (customer_id, status) INCLUDE (net_amount) → pre-sorted, index-only input to the aggregate.",
        before_setup=["DROP INDEX IF EXISTS ix_orders_cust_status_incl"],
        after_setup=[
            "CREATE INDEX ix_orders_cust_status_incl ON orders (customer_id, status) INCLUDE (net_amount, order_date)",
            "ANALYZE orders",
        ],
        restore=[
            "CREATE INDEX IF NOT EXISTS ix_orders_cust_status_incl ON orders (customer_id, status) INCLUDE (net_amount, order_date)",
        ],
        query_before=_LTV_QUERY_NAIVE,
        query_after=_LTV_QUERY_NAIVE,
        takeaway=(
            "When the index already carries every column the aggregate touches, "
            "Postgres skips the heap entirely and buffer reads collapse."
        ),
    ),
    "partition_pruning": Scenario(
        id="partition_pruning",
        title="Partition pruning on a time-range query",
        category="Partitioning",
        problem=(
            "A one-month slice of campaign events. On the monolithic table the "
            "whole thing is scanned; on a monthly RANGE-partitioned copy the "
            "planner prunes to a single partition."
        ),
        technique="RANGE PARTITION BY (event_time), monthly — planner removes non-matching partitions at plan time.",
        before_setup=[],
        after_setup=[],
        restore=[],
        query_before=_PART_QUERY.format(table="campaign_events"),
        query_after=_PART_QUERY.format(table="campaign_events_part"),
        requires_table="campaign_events_part",
        takeaway=(
            "Partition pruning makes scan cost proportional to the time window, "
            "not to total history. Run db/partitioning.sql to enable this scenario."
        ),
    ),
}


# --------------------------------------------------------------------------
# Plan parsing
# --------------------------------------------------------------------------
def _walk(node: dict, acc: dict) -> None:
    acc["node_types"].append(node.get("Node Type"))
    acc["shared_hit"] += node.get("Shared Hit Blocks", 0) or 0
    acc["shared_read"] += node.get("Shared Read Blocks", 0) or 0
    if node.get("Actual Loops", 1) == 0:
        acc["never_executed"] += 1
    if "Relation Name" in node:
        acc["relations"].append(node["Relation Name"])
    for child in node.get("Plans", []) or []:
        _walk(child, acc)


def _summarise_plan(explain_json: Any) -> dict[str, Any]:
    root = explain_json[0] if isinstance(explain_json, list) else explain_json
    plan = root.get("Plan", {})
    acc = {
        "node_types": [],
        "relations": [],
        "shared_hit": 0,
        "shared_read": 0,
        "never_executed": 0,
    }
    _walk(plan, acc)
    return {
        "execution_ms": root.get("Execution Time"),
        "planning_ms": root.get("Planning Time"),
        "total_cost": plan.get("Total Cost"),
        "actual_rows": plan.get("Actual Rows"),
        "top_node": plan.get("Node Type"),
        "scan_types": sorted({n for n in acc["node_types"] if n and "Scan" in n}),
        "has_seq_scan": any(n == "Seq Scan" for n in acc["node_types"]),
        "has_index_only_scan": any(n == "Index Only Scan" for n in acc["node_types"]),
        "shared_blocks_hit": acc["shared_hit"],
        "shared_blocks_read": acc["shared_read"],
        "buffers_total": acc["shared_hit"] + acc["shared_read"],
        "partitions_pruned": acc["never_executed"],
        "relations": sorted(set(acc["relations"])),
    }


def _explain_analyze(cur, sql: str) -> Any:
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, TIMING, FORMAT JSON) {sql}")
    row = cur.fetchone()
    value = next(iter(row.values()))
    return value


def _run_statements(cur, statements: list[str]) -> None:
    for st in statements:
        cur.execute(st)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def list_scenarios() -> list[dict[str, Any]]:
    out = []
    for s in SCENARIOS.values():
        available = True
        reason = None
        if s.requires_table and not _table_exists(s.requires_table):
            available = False
            reason = f"Requires table '{s.requires_table}'. Run db/partitioning.sql."
        out.append(
            {
                "id": s.id,
                "title": s.title,
                "category": s.category,
                "problem": s.problem,
                "technique": s.technique,
                "takeaway": s.takeaway,
                "query_before": s.query_before.strip(),
                "query_after": s.query_after.strip(),
                "available": available,
                "unavailable_reason": reason,
            }
        )
    return out


def _table_exists(name: str) -> bool:
    with app_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) IS NOT NULL AS ok", (name,))
            return bool(cur.fetchone()["ok"])


def run_benchmark(scenario_id: str) -> dict[str, Any]:
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        raise KeyError(scenario_id)
    if scenario.requires_table and not _table_exists(scenario.requires_table):
        raise RuntimeError(
            f"Scenario '{scenario_id}' requires table '{scenario.requires_table}'. "
            "Run db/partitioning.sql first."
        )

    with _run_lock:
        started = time.perf_counter()
        with app_pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # ---- BEFORE ----
                _run_statements(cur, scenario.before_setup)
                _explain_analyze(cur, scenario.query_before)          # warm cache
                before_json = _explain_analyze(cur, scenario.query_before)

                # ---- AFTER ----
                _run_statements(cur, scenario.after_setup)
                _explain_analyze(cur, scenario.query_after)           # warm cache
                after_json = _explain_analyze(cur, scenario.query_after)

                # ---- RESTORE production state ----
                try:
                    _run_statements(cur, scenario.restore)
                except Exception:  # noqa: BLE001 - restore is best-effort
                    pass

    before = _summarise_plan(before_json)
    after = _summarise_plan(after_json)

    b_ms = before.get("execution_ms") or 0.0
    a_ms = after.get("execution_ms") or 0.0
    speedup = round(b_ms / a_ms, 1) if a_ms else None
    buf_b = before.get("buffers_total") or 0
    buf_a = after.get("buffers_total") or 0
    buffer_reduction = round(buf_b / buf_a, 1) if buf_a else None

    return {
        "scenario_id": scenario_id,
        "title": scenario.title,
        "category": scenario.category,
        "problem": scenario.problem,
        "technique": scenario.technique,
        "takeaway": scenario.takeaway,
        "query_before": scenario.query_before.strip(),
        "query_after": scenario.query_after.strip(),
        "before": {**before, "plan": before_json},
        "after": {**after, "plan": after_json},
        "comparison": {
            "execution_ms_before": b_ms,
            "execution_ms_after": a_ms,
            "speedup_x": speedup,
            "buffers_before": buf_b,
            "buffers_after": buf_a,
            "buffer_reduction_x": buffer_reduction,
            "seq_scan_removed": before.get("has_seq_scan") and not after.get("has_seq_scan"),
            "became_index_only": (not before.get("has_index_only_scan"))
            and after.get("has_index_only_scan"),
            "partitions_pruned_after": after.get("partitions_pruned", 0),
        },
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        "note": "EXPLAIN (ANALYZE, BUFFERS) run live; warm run reported after one discarded cold run.",
    }


# --------------------------------------------------------------------------
# Dataset-size scaling benchmark
# --------------------------------------------------------------------------
_SCALE_QUERY = """
SELECT ce.campaign_id, count(*) AS conversions, sum(ce.revenue) AS revenue
FROM campaign_events ce
WHERE ce.event_type = 'convert'
  AND ce.event_time >= now() - (%(days)s || ' days')::interval
GROUP BY ce.campaign_id
"""


def scaling_benchmark() -> dict[str, Any]:
    """Same query at growing time windows, with and without the supporting index.

    Shows that an index scan cost scales with the *matched* rows while a seq scan
    stays flat-and-expensive regardless of selectivity.
    """
    windows = [30, 180, 730, 3650]
    with _run_lock:
        with app_pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                results = {"with_index": [], "without_index": []}

                cur.execute("DROP INDEX IF EXISTS ix_campaign_events_type_time")
                cur.execute("ANALYZE campaign_events")
                for d in windows:
                    results["without_index"].append(_measure(cur, d))

                cur.execute(
                    "CREATE INDEX IF NOT EXISTS ix_campaign_events_type_time ON campaign_events "
                    "(event_type, event_time) INCLUDE (campaign_id, revenue)"
                )
                cur.execute("ANALYZE campaign_events")
                for d in windows:
                    results["with_index"].append(_measure(cur, d))

    return {
        "windows_days": windows,
        "results": results,
        "note": "Execution time and rows are read from EXPLAIN ANALYZE output.",
    }


def _measure(cur, days: int) -> dict[str, Any]:
    sql = _SCALE_QUERY % {"days": days}
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
    plan = next(iter(cur.fetchone().values()))
    summary = _summarise_plan(plan)
    return {
        "window_days": days,
        "execution_ms": summary["execution_ms"],
        "rows_returned": summary["actual_rows"],
        "buffers_total": summary["buffers_total"],
        "scan_types": summary["scan_types"],
    }
