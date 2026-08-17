from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from opspilot.domain.remediation import RemediationActionType, RemediationProposal
from opspilot.policy.rules import evaluate_rules


class TypedAction(StrEnum):
    ROLLBACK = "rollback"
    RESTART = "restart"
    SCALE = "scale"


ACTION_MAP: dict[RemediationActionType, TypedAction] = {
    RemediationActionType.ROLLBACK_DEPLOYMENT: TypedAction.ROLLBACK,
    RemediationActionType.RESTART_WORKLOAD: TypedAction.RESTART,
    RemediationActionType.SCALE_WORKLOAD: TypedAction.SCALE,
}


class TypedCommand(BaseModel):
    """Compiled allowlisted action. Never a raw shell string."""

    model_config = ConfigDict(extra="forbid")

    action: TypedAction
    kind: Literal["Deployment"] = "Deployment"
    name: str
    namespace: Literal["lab"] = "lab"
    replicas: int | None = Field(default=None, ge=1, le=10)
    to_revision: str | None = None

    @model_validator(mode="after")
    def _action_parameters(self) -> TypedCommand:
        if self.action is TypedAction.SCALE and self.replicas is None:
            raise ValueError("scale requires replicas")
        if self.action is not TypedAction.SCALE:
            object.__setattr__(self, "replicas", None)
        if self.action is not TypedAction.ROLLBACK:
            object.__setattr__(self, "to_revision", None)
        return self

    def argv(self, runtime: Literal["lab", "kubectl", "docker"] = "lab") -> list[str]:
        if runtime == "kubectl":
            return kubectl_argv(self)
        if runtime == "docker":
            return docker_argv(self)
        parts = ["lab", self.action.value, f"deployment/{self.name}", f"namespace={self.namespace}"]
        if self.action is TypedAction.SCALE:
            parts.append(f"replicas={self.replicas}")
        if self.action is TypedAction.ROLLBACK and self.to_revision:
            parts.append(f"revision={self.to_revision}")
        return parts


class CommandCompileError(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def compile_typed_command(proposal: RemediationProposal) -> TypedCommand:
    reasons = evaluate_rules(proposal)
    if reasons:
        raise CommandCompileError(reasons)
    action = ACTION_MAP.get(proposal.action_type)
    if action is None:
        raise CommandCompileError([f"action {proposal.action_type.value} is not a typed command"])
    replicas = proposal.parameters.get("replicas")
    revision = proposal.parameters.get("to_revision") or None
    if isinstance(revision, str) and not revision:
        revision = None
    return TypedCommand(
        action=action,
        kind="Deployment",
        name=proposal.target.name,
        namespace="lab",
        replicas=replicas if isinstance(replicas, int) and not isinstance(replicas, bool) else None,
        to_revision=revision if isinstance(revision, str) else None,
    )


def kubectl_argv(command: TypedCommand) -> list[str]:
    resource = f"deployment/{command.name}"
    namespace = ["-n", command.namespace]
    if command.action is TypedAction.RESTART:
        return ["kubectl", "rollout", "restart", resource, *namespace]
    if command.action is TypedAction.SCALE:
        return [
            "kubectl",
            "scale",
            resource,
            f"--replicas={command.replicas}",
            *namespace,
        ]
    args = ["kubectl", "rollout", "undo", resource, *namespace]
    if command.to_revision:
        args.extend(["--to-revision", command.to_revision])
    return args


def docker_argv(command: TypedCommand) -> list[str]:
    container = f"opspilot-{command.name}-1"
    if command.action is TypedAction.RESTART:
        return ["docker", "restart", container]
    if command.action is TypedAction.SCALE:
        return [
            "docker",
            "compose",
            "up",
            "-d",
            "--no-deps",
            "--scale",
            f"{command.name}={command.replicas}",
        ]
    return ["docker", "compose", "up", "-d", "--no-deps", container]
