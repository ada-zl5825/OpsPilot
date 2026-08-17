from datetime import UTC, datetime
from uuid import uuid4

import pytest

from opspilot.domain.remediation import (
    RemediationActionType,
    RemediationProposal,
    ResourceRef,
    RollbackPlan,
)
from opspilot.executor.cluster import InMemoryCluster
from opspilot.executor.commands import (
    CommandCompileError,
    TypedAction,
    compile_typed_command,
    docker_argv,
    kubectl_argv,
)
from opspilot.executor.kubernetes_executor import KubernetesExecutor


def _proposal(
    action: RemediationActionType = RemediationActionType.RESTART_WORKLOAD,
    *,
    name: str = "checkout",
    namespace: str = "lab",
    parameters: dict[str, object] | None = None,
) -> RemediationProposal:
    target = ResourceRef(kind="Deployment", name=name, namespace=namespace, service=name)
    return RemediationProposal(
        proposal_id=uuid4(),
        incident_run_id=uuid4(),
        action_type=action,
        target=target,
        parameters=parameters or {},
        rationale="restore checkout after evidence review",
        expected_effect="error rate returns to baseline",
        risk_level="medium",
        rollback_plan=RollbackPlan(action_type=action, target=target),
        idempotency_key="typed-1",
        expires_at=datetime.now(UTC),
    )


def test_restart_compiles_to_typed_argv() -> None:
    command = compile_typed_command(_proposal())
    assert command.action is TypedAction.RESTART
    assert command.argv() == ["lab", "restart", "deployment/checkout", "namespace=lab"]
    assert kubectl_argv(command) == [
        "kubectl",
        "rollout",
        "restart",
        "deployment/checkout",
        "-n",
        "lab",
    ]
    assert docker_argv(command) == ["docker", "restart", "opspilot-checkout-1"]


def test_scale_and_rollback_are_typed() -> None:
    scale = compile_typed_command(
        _proposal(RemediationActionType.SCALE_WORKLOAD, parameters={"replicas": 3})
    )
    assert scale.argv()[-1] == "replicas=3"
    rollback = compile_typed_command(
        _proposal(RemediationActionType.ROLLBACK_DEPLOYMENT, parameters={"to_revision": "1.4.1"})
    )
    assert "revision=1.4.1" in rollback.argv()
    assert "--to-revision" in kubectl_argv(rollback)


def test_shell_string_does_not_compile() -> None:
    with pytest.raises(CommandCompileError):
        compile_typed_command(_proposal(parameters={"command": "rm -rf /"}))


def test_update_config_is_not_a_typed_executable() -> None:
    with pytest.raises(CommandCompileError, match="not enabled"):
        compile_typed_command(
            _proposal(
                RemediationActionType.UPDATE_CONFIG,
                parameters={"key": "POOL", "value": "20"},
            )
        )


def test_kubernetes_executor_never_uses_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    cluster = InMemoryCluster()
    executor = KubernetesExecutor(cluster)

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr("subprocess.run", _blocked)
    monkeypatch.setattr("os.system", _blocked)
    attempt = executor.execute(_proposal())
    assert attempt.status == "succeeded"
    assert attempt.command_plan[0] == "kubectl"
    assert cluster.write_count() == 1
