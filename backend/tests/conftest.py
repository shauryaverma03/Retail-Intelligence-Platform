"""Shared fixtures. DB-backed tests self-skip when no database is reachable."""
from __future__ import annotations

import os

import pytest


def _db_reachable() -> bool:
    url = os.environ.get("DATABASE_URL", "postgresql://xeno:xeno@localhost:5432/xenopulse")
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_reachable()

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason="No database reachable (set DATABASE_URL and start Postgres to run DB tests).",
)
