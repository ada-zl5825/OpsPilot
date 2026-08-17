from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from mcp_servers.common.fastmcp_schemas import fastmcp_input_schemas
from mcp_servers.remediation.server import mcp as remediation_mcp
from mcp_servers.remediation.tools import propose_restart_workload

from opspilot.domain.remediation import RemediationActionType
from opspilot.executor.idempotency import proposal_digest
from opspilot.remediation.clock import FrozenClock
from opspilot.remediation.errors import RemediationError
from opspilot.remediation.service import ControlPlane


def _plane() -> ControlPlane:
    return ControlPlane(clock=FrozenClock(datetime(2026, 8, 17, 13, 0, tzinfo=UTC)))


def _propose(plane: ControlPlane, **kwargs: object):
    payload = {
        "incident_run_id": uuid4(),
        "action_type": RemediationActionType.RESTART_WORKLOAD,
        "service": "checkout",
        "rationale": "restart after confirmed error evidence",
        "expected_effect": "checkout recovers",
    }
    payload.update(kwargs)
    return plane.propose(**payload)  # type: ignore[arg-type]


def _human_execute(plane: ControlPlane, record):
    return plane.execute(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )


def test_unapproved_write_is_a_failed_test() -> None:
    plane = _plane()
    record = _propose(plane)
    with pytest.raises(RemediationError) as exc:
        _human_execute(plane, record)
    assert exc.value.code == "unapproved_write"
    assert plane.write_count() == 0


def test_shell_metacharacters_never_reach_the_cluster() -> None:
    plane = _plane()
    record = _propose(plane, service="checkout;rm -rf /")
    assert record.status.value == "policy_rejected"
    with pytest.raises(RemediationError):
        plane.approve(
            record.proposal.proposal_id,
            actor_id="sre-1",
            actor_role="sre",
            proposal_digest_value=record.digest,
        )
    assert plane.write_count() == 0


def test_flag_injection_is_rejected() -> None:
    plane = _plane()
    record = _propose(
        plane,
        action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
        parameters={"to_revision": "1.4.1 --kubeconfig /tmp/evil --as cluster-admin"},
    )
    assert record.status.value == "policy_rejected"
    assert plane.write_count() == 0
    token = _propose(plane, parameters={"token": "k8s-admin"})
    assert token.status.value == "policy_rejected"
    assert plane.write_count() == 0


def test_proposal_tampering_voids_approval() -> None:
    plane = _plane()
    record = _propose(
        plane,
        action_type=RemediationActionType.SCALE_WORKLOAD,
        parameters={"replicas": 2},
    )
    plane.approve(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    stored = plane.store.get(record.proposal.proposal_id)
    assert stored is not None
    stored.proposal.parameters["replicas"] = 9
    plane.store.save(stored)
    with pytest.raises(RemediationError) as exc:
        plane.execute(
            record.proposal.proposal_id,
            actor_id="sre-1",
            actor_role="sre",
            proposal_digest_value=record.digest,
        )
    assert exc.value.code in {"tampered_proposal", "digest_mismatch"}
    assert plane.write_count() == 0
    assert proposal_digest(stored.proposal) != record.digest


def test_expired_approval_cannot_execute() -> None:
    clock = FrozenClock(datetime(2026, 8, 17, 13, 0, tzinfo=UTC))
    plane = ControlPlane(clock=clock)
    record = _propose(plane, expires_in_seconds=30)
    plane.approve(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    clock.advance(timedelta(minutes=10))
    with pytest.raises(RemediationError) as exc:
        _human_execute(plane, record)
    assert exc.value.code == "proposal_expired"
    assert plane.write_count() == 0


def test_approval_replay_does_not_write_twice() -> None:
    plane = _plane()
    record = _propose(plane)
    plane.approve(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )
    _human_execute(plane, record)
    _human_execute(plane, record)
    assert plane.write_count() == 1


def test_cross_namespace_write_is_blocked() -> None:
    plane = _plane()
    record = _propose(plane, namespace="prod", service="checkout")
    assert record.status.value == "policy_rejected"
    with pytest.raises(RemediationError):
        plane.execute(
            record.proposal.proposal_id,
            actor_id="sre-1",
            actor_role="sre",
            proposal_digest_value=record.digest,
        )
    assert plane.write_count() == 0
    assert all(item.namespace == "lab" for item in plane.cluster.writes())


def test_direct_mcp_write_bypass_is_impossible() -> None:
    names = set(fastmcp_input_schemas(remediation_mcp))
    assert "execute_approved_proposal" not in names
    assert "rollback_execution" not in names
    plane = _plane()
    created = propose_restart_workload(
        {
            "incident_run_id": str(uuid4()),
            "service": "checkout",
            "rationale": "restart after confirmed 5xx",
            "expected_effect": "checkout recovers",
        },
        plane=plane,
    )
    assert created["write_performed"] is False
    assert plane.write_count() == 0
    with pytest.raises(RemediationError) as exc:
        plane.execute(
            UUID(created["proposal_id"]),
            actor_id="sre-1",
            actor_role="sre",
            proposal_digest_value=created["digest"],
        )
    assert exc.value.code == "unapproved_write"
    assert plane.write_count() == 0


def test_concurrent_execute_succeeds_once() -> None:
    plane = _plane()
    record = _propose(plane)
    plane.approve(
        record.proposal.proposal_id,
        actor_id="sre-1",
        actor_role="sre",
        proposal_digest_value=record.digest,
    )

    def _run() -> str:
        attempt = _human_execute(plane, record)
        return str(attempt.execution_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: _run(), range(8)))
    assert len(set(ids)) == 1
    assert plane.write_count() == 1


def test_executor_sources_do_not_enable_shell() -> None:
    root = Path("src/opspilot")
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert "shell=True" not in text
    assert "shell = True" not in text
