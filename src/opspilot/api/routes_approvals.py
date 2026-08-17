from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(tags=["approvals"])


@router.get("/incidents/{run_id}/proposals", status_code=501)
def list_proposals(run_id: UUID) -> dict[str, str]:
    _ = run_id
    raise HTTPException(status_code=501, detail="Phase 4: proposals are not implemented")


@router.get("/proposals/{proposal_id}", status_code=501)
def get_proposal(proposal_id: UUID) -> dict[str, str]:
    _ = proposal_id
    raise HTTPException(status_code=501, detail="Phase 4: proposals are not implemented")


@router.post("/proposals/{proposal_id}/approve", status_code=501)
def approve_proposal(
    proposal_id: UUID,
    payload: dict[str, Any],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    _ = proposal_id, payload, idempotency_key
    raise HTTPException(status_code=501, detail="Phase 4: approval is not implemented")


@router.post("/proposals/{proposal_id}/reject", status_code=501)
def reject_proposal(
    proposal_id: UUID,
    payload: dict[str, Any],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    _ = proposal_id, payload, idempotency_key
    raise HTTPException(status_code=501, detail="Phase 4: approval is not implemented")


@router.post("/proposals/{proposal_id}/execute", status_code=501)
def execute_proposal(
    proposal_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    """Control-plane only. Never expose this route to the HolmesGPT Agent tool catalog."""
    _ = proposal_id, idempotency_key
    raise HTTPException(status_code=501, detail="Phase 4: execute is not implemented")
