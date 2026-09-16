"""Customer Analytics: RFM, cohort retention, churn/inactivity, high-value, by-segment."""
from __future__ import annotations

from fastapi import APIRouter

from ..catalog import get_query
from ..config import get_settings
from ..db import run_readonly

router = APIRouter(prefix="/customers", tags=["customers"])

# analysis key -> catalog query id
_ANALYSES = {
    "rfm": "02_rfm_segments",
    "cohort": "03_cohort_retention",
    "at_risk": "04_at_risk_customers",
    "churn": "10_inactivity_churn",
    "repeat_by_channel": "07_repeat_purchase_rate",
    "campaign_by_segment": "06_campaign_perf_by_segment",
}


def _run(qid: str) -> dict:
    cq = get_query(qid)
    settings = get_settings()
    limit = settings.query_row_limit
    exec_sql = f"SELECT * FROM (\n{cq.sql}\n) AS _q LIMIT {limit}"
    base = {
        "id": cq.id,
        "name": cq.name,
        "question": cq.question,
        "techniques": cq.techniques,
        "sql": cq.sql,
    }
    try:
        res = run_readonly(exec_sql, limit, timeout_ms=settings.catalog_statement_timeout_ms)
    except Exception as exc:  # noqa: BLE001 - surface DB error to the user instead of a 500
        return {**base, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        **base,
        "ok": True,
        "columns": res.columns,
        "rows": res.rows,
        "row_count": res.row_count,
        "execution_ms": res.elapsed_ms,
    }


@router.get("/analyses")
def analyses() -> dict:
    return {
        "analyses": [
            {"key": k, "query_id": v, "name": (get_query(v).name if get_query(v) else v)}
            for k, v in _ANALYSES.items()
        ]
    }


@router.get("/{analysis}")
def analysis(analysis: str) -> dict:
    qid = _ANALYSES.get(analysis)
    if not qid or not get_query(qid):
        return {"ok": False, "error": f"Unknown analysis '{analysis}'.",
                "available": list(_ANALYSES)}
    return _run(qid)
