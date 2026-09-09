"""SQL Analytics Workspace: pick a catalog question or run custom read-only SQL."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from .. import sql_guard
from ..catalog import all_queries, get_query
from ..config import get_settings
from ..db import explain_readonly, run_readonly
from ..models import RunQueryRequest

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/catalog")
def catalog() -> dict:
    qs = all_queries()
    return {
        "count": len(qs),
        "queries": [q.public() for q in qs],
        "note": "Catalog queries are reviewed in-repo (db/queries/) and run read-only.",
    }


def _plan_meta(plan) -> dict:
    root = plan[0] if isinstance(plan, list) else plan
    if not isinstance(root, dict):
        return {}
    p = root.get("Plan", {})
    return {
        "planning_ms": root.get("Planning Time"),
        "execution_ms": root.get("Execution Time"),
        "total_cost": p.get("Total Cost"),
        "top_node": p.get("Node Type"),
        "actual_rows": p.get("Actual Rows"),
    }


@router.post("/run")
def run(req: RunQueryRequest) -> dict:
    settings = get_settings()
    row_limit = settings.query_row_limit

    # ---- resolve SQL ----
    if req.query_id:
        cq = get_query(req.query_id)
        if not cq:
            raise HTTPException(status_code=404, detail=f"Unknown query_id '{req.query_id}'")
        source = "catalog"
        display_sql = cq.sql
        exec_sql = f"SELECT * FROM (\n{cq.sql}\n) AS _xeno_capped LIMIT {row_limit}"
        tables: list[str] = []
    elif req.sql and req.sql.strip():
        source = "custom"
        try:
            validated = sql_guard.validate(req.sql, row_limit)
        except sql_guard.SqlNotAllowed as exc:
            return {
                "ok": False,
                "source": source,
                "sql": req.sql,
                "error": str(exc),
            }
        display_sql = validated.original
        exec_sql = validated.safe_sql
        tables = validated.tables
    else:
        raise HTTPException(status_code=422, detail="Provide either 'sql' or 'query_id'.")

    # ---- execute ----
    try:
        result = run_readonly(exec_sql, row_limit)
    except Exception as exc:  # noqa: BLE001 - surface DB error to the user
        return {
            "ok": False,
            "source": source,
            "sql": display_sql,
            "executed_sql": exec_sql,
            "error": f"{type(exc).__name__}: {exc}",
        }

    payload = {
        "ok": True,
        "source": source,
        "sql": display_sql,
        "executed_sql": exec_sql,
        "tables": tables,
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "execution_ms": result.elapsed_ms,
    }

    # ---- optional query plan ----
    if req.explain:
        try:
            plan = explain_readonly(exec_sql, analyze=True)
            payload["plan"] = plan
            payload["plan_meta"] = _plan_meta(plan)
        except Exception as exc:  # noqa: BLE001
            payload["plan_error"] = f"{type(exc).__name__}: {exc}"

    return payload
