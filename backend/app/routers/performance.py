"""Query Performance Lab endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import perf_lab

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/scenarios")
def scenarios() -> dict:
    return {"scenarios": perf_lab.list_scenarios()}


@router.post("/scenarios/{scenario_id}/benchmark")
def benchmark(scenario_id: str) -> dict:
    try:
        return perf_lab.run_benchmark(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{scenario_id}'")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/scaling-benchmark")
def scaling() -> dict:
    return perf_lab.scaling_benchmark()
