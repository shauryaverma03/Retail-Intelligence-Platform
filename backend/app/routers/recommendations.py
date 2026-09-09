"""Business Recommendations endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
def get_recommendations() -> dict:
    return recommendations.all_recommendations()
