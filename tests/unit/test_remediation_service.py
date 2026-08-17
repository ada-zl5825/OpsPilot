from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from opspilot.domain.remediation import ProposalStatus, RemediationActionType
from opspilot.remediation.clock import FrozenClock
from opspilot.remediation.errors import RemediationError
from opspilot.remediation.service import ControlPlane


def _plane(clock: FrozenClock | None = None) -> ControlPlane:
    return ControlPlane(clock=clock or FrozenClock(datetime(2026, 8, 17, 12, 0, tzinfo=UTC)))


def _propose(plane: ControlPlane, **kwargs: object):
    payload = {
        "incident_run_id": uuid4(),
        "action_type": RemediationActionType.RESTART_WORKLOAD,
        "service": "checkout",
        "rationale": "restart after error-rate evidence",
        "expected_effect": "checkout returns 200",
    }
    payload.update(kwargs)
    return plane.propose(**payload)  # type: ignore[arg-type]


def _approve(plane: ControlPlane, record):
    return plane.approve(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )


def test_happy_path_propose_dry_run_approve_execute_verify_rollback() -> None:
    plane = _plane()
    plane.cluster.inject_fault("checkout")
    record = _propose(
        plane,
        action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
        parameters={"to_revision": "1.4.1"},
    )
    assert record.status is ProposalStatus.AWAITING_APPROVAL
    assert plane.write_count() == 0
    dry = plane.dry_run(record.proposal.proposal_id)
    assert dry.allowed is True
    assert plane.write_count() == 0
    _approve(plane, record)
    assert plane.write_count() == 0
    attempt = plane.execute(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    assert attempt.status == "succeeded"
    assert plane.write_count() == 1
    report = plane.verify(record.proposal.proposal_id, service="checkout")
    assert report.passed is True
    rolled = plane.rollback_execution(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    assert rolled.status == "rolled_back"
    assert plane.write_count() == 2


def test_unapproved_execute_does_not_write() -> None:
    plane = _plane()
    record = _propose(plane)
    with pytest.raises(RemediationError, match="not approved"):
        plane.execute(
            record.proposal.proposal_id,
            actor_id="sre-1",
            actor_role="sre",
            proposal_digest_value=record.digest,
        )
    assert plane.write_count() == 0


def test_agent_cannot_approve_or_execute() -> None:
    plane = _plane()
    record = _propose(plane)
    with pytest.raises(RemediationError, match="system agent"):
        plane.approve(
            record.proposal.proposal_id,
            actor_id="holmes",
            actor_role="sre",
            proposal_digest_value=record.digest,
        )
    with pytest.raises(RemediationError, match="system agent"):
        plane.execute(
            record.proposal.proposal_id,
            actor_id="agent",
            actor_role="agent",
            proposal_digest_value=record.digest,
        )
    assert plane.write_count() == 0


def test_reject_cannot_be_overridden() -> None:
    plane = _plane()
    record = _propose(plane)
    plane.reject(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    with pytest.raises(RemediationError, match="cannot be approved"):
        _approve(plane, record)
    with pytest.raises(RemediationError, match="rejected"):
        plane.execute(
            record.proposal.proposal_id,
            actor_id="sre-1",
            actor_role="sre",
            proposal_digest_value=record.digest,
        )
    assert plane.write_count() == 0


def test_update_config_is_policy_rejected() -> None:
    plane = _plane()
    record = _propose(
        plane,
        action_type=RemediationActionType.UPDATE_CONFIG,
        parameters={"key": "DB_POOL_MAX", "value": "20"},
    )
    assert record.status is ProposalStatus.POLICY_REJECTED
    with pytest.raises(RemediationError):
        _approve(plane, record)
    assert plane.write_count() == 0


def test_idempotent_execute_writes_once() -> None:
    plane = _plane()
    record = _propose(plane)
    _approve(plane, record)
    first = plane.execute(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    second = plane.execute(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    assert first.execution_id == second.execution_id
    assert plane.write_count() == 1


def test_expired_proposal_cannot_execute() -> None:
    clock = FrozenClock(datetime(2026, 8, 17, 12, 0, tzinfo=UTC))
    plane = _plane(clock)
    record = _propose(plane, expires_in_seconds=60)
    _approve(plane, record)
    clock.advance(timedelta(minutes=5))
    with pytest.raises(RemediationError, match="expired"):
        plane.execute(
            record.proposal.proposal_id,
            actor_id="sre-1",
            actor_role="sre",
            proposal_digest_value=record.digest,
        )
    assert plane.write_count() == 0
