"""Business Recommendations endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
def get_recommendations(refresh: bool = Query(default=False)) -> dict:
    return recommendations.all_recommendations(refresh=refresh)
