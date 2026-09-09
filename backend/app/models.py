"""Pydantic request/response models for the public API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- SQL Workspace --------------------------------------------------------
class RunQueryRequest(BaseModel):
    sql: str | None = Field(default=None, description="Raw SELECT to validate & run")
    query_id: str | None = Field(default=None, description="Id of a catalog query to run")
    explain: bool = Field(default=True, description="Also return EXPLAIN (ANALYZE, BUFFERS)")


class QueryResult(BaseModel):
    ok: bool
    source: str                       # "catalog" | "custom"
    sql: str
    executed_sql: str
    tables: list[str] = []
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    truncated: bool = False
    execution_ms: float | None = None
    planning_ms: float | None = None
    plan: Any | None = None
    plan_text: str | None = None
    error: str | None = None


# --- AI Analyst --------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    execute: bool = Field(default=True)


class Recommendation(BaseModel):
    finding: str
    evidence: str
    recommendation: str
    expected_impact: str
    next_step: str


class AskResponse(BaseModel):
    ok: bool
    question: str
    engine: str                       # "llm" | "rule-based"
    model: str | None = None
    sql: str | None = None
    sql_valid: bool = False
    validation_error: str | None = None
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    execution_ms: float | None = None
    summary: str | None = None
    recommendation: Recommendation | None = None
    disclaimer: str = (
        "Numbers are computed live from the synthetic XenoPulse database. "
        "No values in this response are estimated or invented."
    )
    error: str | None = None


# --- Performance Lab --------------------------------------------------------
class BenchmarkRequest(BaseModel):
    scenario_id: str


# --- Session --------------------------------------------------------
class TourState(BaseModel):
    completed: bool = True


class PreferencesPatch(BaseModel):
    patch: dict[str, Any] = Field(default_factory=dict)
