"""AI Analyst endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from ..models import AskRequest
from ..services import ai_analyst

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/ask")
def ask(req: AskRequest) -> dict:
    return ai_analyst.answer(req.question, execute=req.execute)


@router.get("/examples")
def examples() -> dict:
    return {
        "examples": [
            "What is our repeat purchase rate?",
            "Show monthly revenue for the last 6 months",
            "Which campaigns have the best return on ad spend?",
            "How do customers break down by RFM segment?",
            "Which acquisition channel has the worst repeat rate?",
            "How much revenue is at risk from lapsing high-value customers?",
            "What is our average order value?",
            "Revenue by product category",
        ]
    }
