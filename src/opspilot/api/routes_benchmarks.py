from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(tags=["benchmarks"])


@router.post("/benchmarks/runs", status_code=501)
def create_benchmark_run(
    payload: dict[str, Any],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    _ = payload, idempotency_key
    raise HTTPException(status_code=501, detail="Phase 5: benchmark API is not implemented")


@router.get("/benchmarks/runs/{benchmark_run_id}", status_code=501)
def get_benchmark_run(benchmark_run_id: UUID) -> dict[str, str]:
    _ = benchmark_run_id
    raise HTTPException(status_code=501, detail="Phase 5: benchmark API is not implemented")


@router.get("/benchmarks/runs/{benchmark_run_id}/report", status_code=501)
def get_benchmark_report(benchmark_run_id: UUID) -> dict[str, str]:
    _ = benchmark_run_id
    raise HTTPException(status_code=501, detail="Phase 5: benchmark API is not implemented")


@router.get("/benchmarks/baselines")
def list_baselines() -> dict[str, list[Any]]:
    return {"baselines": []}
