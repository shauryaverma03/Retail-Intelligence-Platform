"""Database access: two connection pools and small query helpers.

  * ``app_pool``  -- owner role. Trusted server-side SQL only.
  * ``ro_pool``   -- ``xeno_readonly`` role. Everything user-influenced
                     (SQL Workspace, AI Analyst) runs here, inside a
                     read-only transaction with a hard statement timeout.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

_settings = get_settings()

app_pool: ConnectionPool = ConnectionPool(
    conninfo=_settings.database_url,
    min_size=1,
    max_size=8,
    max_idle=60,
    kwargs={"row_factory": dict_row, "application_name": "xenopulse-app"},
    open=False,
)

ro_pool: ConnectionPool = ConnectionPool(
    conninfo=_settings.database_url_ro,
    min_size=1,
    max_size=6,
    max_idle=60,
    kwargs={"row_factory": dict_row, "application_name": "xenopulse-readonly"},
    open=False,
)


def open_pools() -> None:
    app_pool.open()
    ro_pool.open()


def close_pools() -> None:
    app_pool.close()
    ro_pool.close()


# --------------------------------------------------------------------------
# Trusted helpers (owner pool)
# --------------------------------------------------------------------------
def fetch_all(sql: str, params: dict | list | tuple | None = None) -> list[dict[str, Any]]:
    with app_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []


def fetch_one(sql: str, params: dict | list | tuple | None = None) -> dict[str, Any] | None:
    with app_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone() if cur.description else None


def fetch_scalar(sql: str, params: dict | list | tuple | None = None) -> Any:
    row = fetch_one(sql, params)
    if not row:
        return None
    return next(iter(row.values()))


@contextmanager
def app_cursor() -> Iterator[psycopg.Cursor]:
    with app_pool.connection() as conn:
        with conn.cursor() as cur:
            yield cur


# --------------------------------------------------------------------------
# Read-only execution (readonly pool) -- for user / AI supplied SQL
# --------------------------------------------------------------------------
class ReadOnlyResult:
    __slots__ = ("columns", "rows", "row_count", "elapsed_ms", "truncated")

    def __init__(self, columns, rows, row_count, elapsed_ms, truncated):
        self.columns = columns
        self.rows = rows
        self.row_count = row_count
        self.elapsed_ms = elapsed_ms
        self.truncated = truncated

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "elapsed_ms": self.elapsed_ms,
            "truncated": self.truncated,
        }


def run_readonly(sql: str, max_rows: int) -> ReadOnlyResult:
    """Execute already-validated SELECT SQL on the read-only pool.

    The SQL is expected to have passed ``sql_guard.validate`` first. This layer
    adds defence in depth: an explicit read-only transaction and a per-statement
    timeout, and it rolls the transaction back no matter what.
    """
    settings = get_settings()
    with ro_pool.connection() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = %s", (settings.statement_timeout_ms,))
            cur.execute("SET TRANSACTION READ ONLY")
            start = time.perf_counter()
            cur.execute(sql)
            rows = cur.fetchmany(max_rows + 1) if cur.description else []
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            columns = [d.name for d in cur.description] if cur.description else []
        conn.rollback()

    truncated = len(rows) > max_rows
    if truncated:
        rows = rows[:max_rows]
    return ReadOnlyResult(columns, rows, len(rows), elapsed_ms, truncated)


def explain_readonly(sql: str, analyze: bool = True) -> dict[str, Any]:
    """Return the JSON query plan for validated SELECT SQL (read-only pool)."""
    settings = get_settings()
    opts = "ANALYZE, BUFFERS, VERBOSE, TIMING, FORMAT JSON" if analyze else "VERBOSE, FORMAT JSON"
    with ro_pool.connection() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = %s", (settings.explain_timeout_ms,))
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"EXPLAIN ({opts}) {sql}")
            plan = cur.fetchone()
        conn.rollback()
    # dict_row -> {'QUERY PLAN': [ ... ]}
    value = next(iter(plan.values())) if plan else None
    return value[0] if isinstance(value, list) and value else value
