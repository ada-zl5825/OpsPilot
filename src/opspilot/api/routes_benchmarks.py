from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from opspilot.eval.constants import BENCHMARK_VERSION

router = APIRouter(tags=["benchmarks"])

_RUNS: dict[UUID, dict[str, Any]] = {}
_IDEMPOTENCY: dict[str, UUID] = {}


class CreateBenchmarkRequest(BaseModel):
    mode: str = "offline"
    split: str = "eval"
    conditions: list[str] = Field(default_factory=lambda: ["deterministic", "single_agent"])
    gate: bool = False


@router.post("/benchmarks/runs", status_code=201)
def create_benchmark_run(
    payload: CreateBenchmarkRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if payload.mode != "offline":
        raise HTTPException(
            status_code=400, detail="only offline benchmark runs are served by the API"
        )
    if idempotency_key and idempotency_key in _IDEMPOTENCY:
        existing = _RUNS[_IDEMPOTENCY[idempotency_key]]
        return existing
    from benchmarks.harness import run_offline

    run_id = uuid4()
    try:
        report = run_offline(
            split=payload.split,
            conditions=payload.conditions,
            gate=payload.gate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = {
        "benchmark_run_id": str(run_id),
        "status": "completed",
        "request": payload.model_dump(),
        "report": report.model_dump(mode="json"),
    }
    _RUNS[run_id] = record
    if idempotency_key:
        _IDEMPOTENCY[idempotency_key] = run_id
    return record


@router.get("/benchmarks/runs/{benchmark_run_id}")
def get_benchmark_run(benchmark_run_id: UUID) -> dict[str, Any]:
    record = _RUNS.get(benchmark_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="benchmark run not found")
    return record


@router.get("/benchmarks/runs/{benchmark_run_id}/report")
def get_benchmark_report(benchmark_run_id: UUID) -> dict[str, Any]:
    record = _RUNS.get(benchmark_run_id)
    report = record.get("report") if record is not None else None
    if not isinstance(report, dict):
        raise HTTPException(status_code=404, detail="benchmark report not found")
    return report


@router.get("/benchmarks/baselines")
def list_baselines() -> dict[str, Any]:
    from benchmarks.gate import load_manifest

    return {"benchmark_version": BENCHMARK_VERSION, "baselines": [load_manifest()]}
