"""Data Quality endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import data_quality

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/checks")
def checks(refresh: bool = Query(default=False)) -> dict:
    return data_quality.run_all_checks(refresh=refresh)
