from __future__ import annotations

from opspilot.executor.cluster import WorkloadSnapshot
from opspilot.executor.commands import TypedAction, TypedCommand


def inverse_command(command: TypedCommand, snapshot: WorkloadSnapshot) -> TypedCommand:
    if command.action is TypedAction.SCALE:
        return TypedCommand(
            action=TypedAction.SCALE,
            name=command.name,
            namespace=command.namespace,
            replicas=snapshot.replicas,
        )
    if command.action is TypedAction.ROLLBACK:
        return TypedCommand(
            action=TypedAction.ROLLBACK,
            name=command.name,
            namespace=command.namespace,
            to_revision=snapshot.revision,
        )
    return TypedCommand(
        action=TypedAction.RESTART,
        name=command.name,
        namespace=command.namespace,
    )
