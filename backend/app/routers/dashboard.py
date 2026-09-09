"""Business dashboard endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(refresh: bool = Query(default=False)) -> dict:
    return metrics.dashboard_summary(refresh=refresh)
