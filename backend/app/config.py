"""Runtime configuration, loaded from environment variables.

Secrets never live in code. See .env.example at the repo root.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- database -----------------------------------------------------------
    # Owner connection: migrations, dashboards, perf-lab DDL, everything trusted.
    database_url: str = Field(
        default="postgresql://xeno:xeno@db:5432/xenopulse",
        alias="DATABASE_URL",
    )
    # Read-only connection: the ONLY connection user-influenced SQL runs on
    # (SQL Workspace + AI Analyst). Role is created in db/schema.sql.
    database_url_ro: str = Field(
        default="postgresql://xeno_readonly:xeno_readonly_pw@db:5432/xenopulse",
        alias="DATABASE_URL_RO",
    )

    # --- safety limits ----------------------------------------------------
    query_row_limit: int = Field(default=1000, alias="QUERY_ROW_LIMIT")
    statement_timeout_ms: int = Field(default=8000, alias="STATEMENT_TIMEOUT_MS")
    explain_timeout_ms: int = Field(default=30000, alias="EXPLAIN_TIMEOUT_MS")

    # --- AI Analyst -----------------------------------------------------
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    ai_model: str = Field(default="claude-sonnet-5", alias="AI_MODEL")
    ai_max_tokens: int = Field(default=1500, alias="AI_MAX_TOKENS")

    # --- app ------------------------------------------------------------
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    dashboard_cache_ttl_s: int = Field(default=60, alias="DASHBOARD_CACHE_TTL_S")
    query_catalog_dir: str = Field(default="db/queries", alias="QUERY_CATALOG_DIR")

    # --- sessions / cookies -------------------------------------------------
    # Anonymous, HMAC-signed session cookie. No login, no PII -- just enough to
    # remember tour progress, UI preferences and this session's query history.
    session_secret: str = Field(
        default="dev-only-insecure-session-secret-change-me", alias="SESSION_SECRET"
    )
    session_cookie_name: str = Field(default="xeno_session", alias="SESSION_COOKIE_NAME")
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field(default="lax", alias="SESSION_COOKIE_SAMESITE")
    session_ttl_days: int = Field(default=30, alias="SESSION_TTL_DAYS")
    session_query_history: int = Field(default=25, alias="SESSION_QUERY_HISTORY")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
