"""Health, readiness and app metadata."""
from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import get_settings
from ..db import fetch_one
from ..sql_guard import ALLOWED_TABLES

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/ready")
def ready() -> dict:
    try:
        row = fetch_one("SELECT count(*) AS n FROM customers")
        seeded = bool(row and row["n"] > 0)
        return {"status": "ok" if seeded else "degraded", "db": "up", "seeded": seeded}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "db": "down", "error": str(exc)}


@router.get("/meta")
def meta() -> dict:
    s = get_settings()
    return {
        "version": __version__,
        "ai_enabled": s.ai_enabled,
        "ai_model": s.ai_model if s.ai_enabled else None,
        "query_row_limit": s.query_row_limit,
        "statement_timeout_ms": s.statement_timeout_ms,
        "allowed_tables": sorted(ALLOWED_TABLES),
        "data_disclaimer": "All data in this system is synthetic and for demonstration only.",
    }
