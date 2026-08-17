from datetime import UTC, datetime
from uuid import uuid4

from opspilot.domain.remediation import (
    RemediationActionType,
    RemediationProposal,
    ResourceRef,
    RollbackPlan,
)
from opspilot.policy.engine import PolicyEngine


def _proposal(
    namespace: str = "lab", parameters: dict[str, str] | None = None
) -> RemediationProposal:
    target = ResourceRef(kind="Deployment", name="checkout", namespace=namespace)
    return RemediationProposal(
        proposal_id=uuid4(),
        incident_run_id=uuid4(),
        action_type=RemediationActionType.RESTART_WORKLOAD,
        target=target,
        parameters=parameters or {},
        rationale="restart",
        expected_effect="recover",
        risk_level="medium",
        rollback_plan=RollbackPlan(
            action_type=RemediationActionType.RESTART_WORKLOAD, target=target
        ),
        idempotency_key="k",
        expires_at=datetime.now(UTC),
    )


def test_allowlisted_namespace_passes() -> None:
    decision = PolicyEngine().evaluate(_proposal())
    assert decision.allowed is True


def test_foreign_namespace_rejected() -> None:
    decision = PolicyEngine().evaluate(_proposal(namespace="prod"))
    assert decision.allowed is False
    assert any("namespace" in reason for reason in decision.reasons)


def test_forbidden_shell_parameter_rejected() -> None:
    decision = PolicyEngine().evaluate(_proposal(parameters={"shell": "rm -rf /"}))
    assert decision.allowed is False
