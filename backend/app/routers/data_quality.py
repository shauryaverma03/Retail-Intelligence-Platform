"""Data Quality endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import data_quality

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/checks")
def checks() -> dict:
    return data_quality.run_all_checks()
