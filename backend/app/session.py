"""Anonymous session + cookie handling.

There is no login here. On the first request a random session id is minted,
signed with HMAC-SHA256 (``SESSION_SECRET``) and sent back as an HttpOnly cookie.
The server keeps a small row per session:

  * ``tour_completed``  -- has this visitor finished / dismissed the guided tour
  * ``preferences``     -- free-form JSON for UI state (last page, theme, ...)
  * plus a capped history of the queries run in the SQL Workspace

Nothing personally identifying is stored.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Request, Response

from .config import get_settings
from .db import app_pool, fetch_all, fetch_one

# --------------------------------------------------------------------------
# schema (idempotent -- created on startup, also present in db/schema.sql)
# --------------------------------------------------------------------------
_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    tour_completed  BOOLEAN     NOT NULL DEFAULT FALSE,
    preferences     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    request_count   BIGINT      NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS session_queries (
    id           BIGSERIAL PRIMARY KEY,
    session_id   TEXT        NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    sql          TEXT        NOT NULL,
    source       TEXT        NOT NULL,
    row_count    INTEGER,
    execution_ms DOUBLE PRECISION,
    ok           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_session_queries_session
    ON session_queries (session_id, created_at DESC);
"""


def ensure_tables() -> None:
    with app_pool.connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(_DDL)


def prune_expired() -> int:
    ttl = get_settings().session_ttl_days
    row = fetch_one(
        "DELETE FROM sessions WHERE last_seen_at < now() - make_interval(days => %s) "
        "RETURNING session_id",
        (ttl,),
    )
    return 1 if row else 0


# --------------------------------------------------------------------------
# signing
# --------------------------------------------------------------------------
def _sign(session_id: str) -> str:
    secret = get_settings().session_secret.encode()
    mac = hmac.new(secret, session_id.encode(), hashlib.sha256).hexdigest()
    return f"{session_id}.{mac}"


def _unsign(token: str) -> str | None:
    if not token or token.count(".") != 1:
        return None
    session_id, mac = token.split(".", 1)
    expected = hmac.new(
        get_settings().session_secret.encode(), session_id.encode(), hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(mac, expected):
        return session_id
    return None


# --------------------------------------------------------------------------
# session lifecycle
# --------------------------------------------------------------------------
class Session:
    __slots__ = ("id", "created_at", "last_seen_at", "tour_completed", "preferences",
                 "request_count", "is_new")

    def __init__(self, row: dict[str, Any], is_new: bool):
        self.id = row["session_id"]
        self.created_at = row["created_at"]
        self.last_seen_at = row["last_seen_at"]
        self.tour_completed = row["tour_completed"]
        self.preferences = row["preferences"] or {}
        self.request_count = row["request_count"]
        self.is_new = is_new

    def public(self) -> dict[str, Any]:
        return {
            "session_id": self.id,
            "short_id": self.id[:8],
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "tour_completed": self.tour_completed,
            "preferences": self.preferences,
            "request_count": self.request_count,
            "is_new": self.is_new,
        }


def _set_cookie(response: Response, session_id: str) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.session_cookie_name,
        value=_sign(session_id),
        max_age=s.session_ttl_days * 86400,
        httponly=True,
        samesite=s.session_cookie_samesite,
        secure=s.session_cookie_secure,
        path="/",
    )


def current_session(request: Request, response: Response) -> Session:
    """FastAPI dependency: load-or-create the caller's session, refresh last_seen."""
    s = get_settings()
    token = request.cookies.get(s.session_cookie_name, "")
    session_id = _unsign(token)

    row = None
    if session_id:
        row = fetch_one(
            """
            UPDATE sessions
               SET last_seen_at = now(), request_count = request_count + 1
             WHERE session_id = %s
            RETURNING session_id, created_at, last_seen_at, tour_completed,
                      preferences, request_count
            """,
            (session_id,),
        )

    if row is None:
        session_id = secrets.token_urlsafe(24)
        row = fetch_one(
            """
            INSERT INTO sessions (session_id) VALUES (%s)
            RETURNING session_id, created_at, last_seen_at, tour_completed,
                      preferences, request_count
            """,
            (session_id,),
        )
        _set_cookie(response, session_id)
        return Session(row, is_new=True)

    # refresh the cookie's max-age on every visit
    _set_cookie(response, session_id)
    return Session(row, is_new=False)


# --------------------------------------------------------------------------
# mutations
# --------------------------------------------------------------------------
def set_tour_completed(session_id: str, completed: bool) -> dict[str, Any]:
    return fetch_one(
        "UPDATE sessions SET tour_completed = %s WHERE session_id = %s "
        "RETURNING session_id, tour_completed",
        (completed, session_id),
    ) or {}


def merge_preferences(session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    row = fetch_one(
        "UPDATE sessions SET preferences = preferences || %s::jsonb "
        "WHERE session_id = %s RETURNING preferences",
        (json.dumps(patch), session_id),
    )
    return (row or {}).get("preferences", {})


def reset_session(session_id: str) -> None:
    with app_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))


def record_query(session_id: str, sql: str, source: str,
                 row_count: int | None, execution_ms: float | None, ok: bool) -> None:
    """Append a workspace query to this session's history (best-effort, capped)."""
    keep = get_settings().session_query_history
    try:
        with app_pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO session_queries "
                    "(session_id, sql, source, row_count, execution_ms, ok) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (session_id, sql[:4000], source, row_count, execution_ms, ok),
                )
                cur.execute(
                    """
                    DELETE FROM session_queries
                     WHERE session_id = %s
                       AND id NOT IN (
                           SELECT id FROM session_queries
                            WHERE session_id = %s
                         ORDER BY id DESC LIMIT %s
                       )
                    """,
                    (session_id, session_id, keep),
                )
    except Exception:  # noqa: BLE001 - history is a nicety, never fail the request
        pass


def recent_queries(session_id: str, limit: int = 25) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT id, sql, source, row_count, execution_ms, ok, created_at "
        "FROM session_queries WHERE session_id = %s ORDER BY id DESC LIMIT %s",
        (session_id, limit),
    )
