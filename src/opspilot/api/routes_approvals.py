from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from opspilot.api.dependencies import remediation_plane
from opspilot.domain.remediation import RemediationActionType
from opspilot.remediation.errors import HTTP_STATUS_BY_CODE, RemediationError
from opspilot.remediation.models import ProposalRecord
from opspilot.remediation.service import ControlPlane

router = APIRouter(tags=["approvals"])
PlaneDep = Annotated[ControlPlane, Depends(remediation_plane)]


class CreateProposalRequest(BaseModel):
    action_type: RemediationActionType
    service: str = Field(min_length=1, max_length=32)
    namespace: str = "lab"
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=8, max_length=500)
    expected_effect: str = Field(min_length=4, max_length=300)
    idempotency_key: str = Field(default="", max_length=128)


class DigestBoundRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=64)
    actor_role: str = Field(min_length=1, max_length=32)
    proposal_digest: str = Field(min_length=64, max_length=64)
    reason: str | None = Field(default=None, max_length=300)


def _http_error(exc: RemediationError) -> HTTPException:
    return HTTPException(
        status_code=HTTP_STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


def _record_payload(record: ProposalRecord) -> dict[str, Any]:
    return {
        "proposal_id": str(record.proposal.proposal_id),
        "incident_run_id": str(record.proposal.incident_run_id),
        "digest": record.digest,
        "status": record.status.value,
        "action_type": record.proposal.action_type.value,
        "target": record.proposal.target.model_dump(mode="json"),
        "parameters": record.proposal.parameters,
        "risk_level": record.proposal.risk_level,
        "expires_at": record.proposal.expires_at.isoformat(),
        "idempotency_key": record.proposal.idempotency_key,
        "dry_run_result": (
            record.proposal.dry_run_result.model_dump(mode="json")
            if record.proposal.dry_run_result
            else None
        ),
        "approval": record.approval.model_dump(mode="json") if record.approval else None,
        "executions": [item.model_dump(mode="json") for item in record.executions],
        "recovery": record.recovery.model_dump(mode="json") if record.recovery else None,
        "audit": [item.model_dump(mode="json") for item in record.audit],
    }


@router.post("/incidents/{run_id}/proposals", status_code=201)
def create_proposal(
    run_id: UUID,
    payload: CreateProposalRequest,
    plane: PlaneDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        record = plane.propose(
            incident_run_id=run_id,
            action_type=payload.action_type,
            service=payload.service,
            namespace=payload.namespace,
            parameters=payload.parameters,
            rationale=payload.rationale,
            expected_effect=payload.expected_effect,
            idempotency_key=payload.idempotency_key or idempotency_key or "",
        )
    except RemediationError as exc:
        raise _http_error(exc) from exc
    return _record_payload(record)


@router.get("/incidents/{run_id}/proposals")
def list_proposals(run_id: UUID, plane: PlaneDep) -> dict[str, Any]:
    records = plane.list_for_run(run_id)
    return {"run_id": str(run_id), "proposals": [_record_payload(item) for item in records]}


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: UUID, plane: PlaneDep) -> dict[str, Any]:
    try:
        return _record_payload(plane.get(proposal_id))
    except RemediationError as exc:
        raise _http_error(exc) from exc


@router.post("/proposals/{proposal_id}/dry-run")
def dry_run_proposal(proposal_id: UUID, plane: PlaneDep) -> dict[str, Any]:
    try:
        result = plane.dry_run(proposal_id)
    except RemediationError as exc:
        raise _http_error(exc) from exc
    return result.model_dump(mode="json")


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(
    proposal_id: UUID,
    payload: DigestBoundRequest,
    plane: PlaneDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _ = idempotency_key
    try:
        decision = plane.approve(
            proposal_id,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            proposal_digest_value=payload.proposal_digest,
            reason=payload.reason,
        )
    except RemediationError as exc:
        raise _http_error(exc) from exc
    return decision.model_dump(mode="json")


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: UUID,
    payload: DigestBoundRequest,
    plane: PlaneDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _ = idempotency_key
    try:
        decision = plane.reject(
            proposal_id,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            proposal_digest_value=payload.proposal_digest,
            reason=payload.reason,
        )
    except RemediationError as exc:
        raise _http_error(exc) from exc
    return decision.model_dump(mode="json")


@router.post("/proposals/{proposal_id}/execute")
def execute_proposal(
    proposal_id: UUID,
    payload: DigestBoundRequest,
    plane: PlaneDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Control-plane only. Never expose this route to the HolmesGPT Agent tool catalog."""
    _ = idempotency_key
    try:
        attempt = plane.execute(
            proposal_id,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            proposal_digest_value=payload.proposal_digest,
        )
    except RemediationError as exc:
        raise _http_error(exc) from exc
    return attempt.model_dump(mode="json")


@router.post("/proposals/{proposal_id}/rollback")
def rollback_proposal(
    proposal_id: UUID,
    payload: DigestBoundRequest,
    plane: PlaneDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Control-plane only. Never expose this route to the HolmesGPT Agent tool catalog."""
    _ = idempotency_key
    try:
        attempt = plane.rollback_execution(
            proposal_id,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            proposal_digest_value=payload.proposal_digest,
        )
    except RemediationError as exc:
        raise _http_error(exc) from exc
    return attempt.model_dump(mode="json")


@router.post("/proposals/{proposal_id}/verify")
def verify_proposal(proposal_id: UUID, plane: PlaneDep) -> dict[str, Any]:
    try:
        report = plane.verify(proposal_id)
    except RemediationError as exc:
        raise _http_error(exc) from exc
    return report.model_dump(mode="json")
