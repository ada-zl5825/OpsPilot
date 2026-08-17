from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(tags=["incidents"])


@router.post("/incidents", status_code=501)
def create_incident(
    payload: dict[str, Any],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    _ = payload, idempotency_key
    raise HTTPException(status_code=501, detail="Phase 3: incident intake is not implemented")


@router.get("/incidents/{run_id}", status_code=501)
def get_incident(run_id: UUID) -> dict[str, str]:
    _ = run_id
    raise HTTPException(status_code=501, detail="Phase 3: incident read is not implemented")


@router.get("/incidents/{run_id}/events", status_code=501)
def list_events(run_id: UUID) -> dict[str, str]:
    _ = run_id
    raise HTTPException(status_code=501, detail="Phase 3: event replay is not implemented")


@router.post("/incidents/{run_id}/cancel", status_code=501)
def cancel_incident(
    run_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    _ = run_id, idempotency_key
    raise HTTPException(status_code=501, detail="Phase 3: cancel is not implemented")
