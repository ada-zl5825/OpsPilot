from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from opspilot.domain.remediation import ExecutionAttempt, RemediationProposal
from opspilot.executor.base import Executor
from opspilot.executor.cluster import ClusterBackend
from opspilot.executor.commands import compile_typed_command, docker_argv


class DockerExecutor(Executor):
    """Compiles docker argv lists. Never runs a shell and never calls subprocess."""

    def __init__(self, backend: ClusterBackend) -> None:
        self._backend = backend

    def execute(self, proposal: RemediationProposal) -> ExecutionAttempt:
        started = datetime.now(UTC)
        command = compile_typed_command(proposal)
        plan = docker_argv(command)
        self._backend.apply(command)
        return ExecutionAttempt(
            execution_id=uuid4(),
            proposal_id=proposal.proposal_id,
            status="succeeded",
            command_plan=plan,
            started_at=started,
            ended_at=datetime.now(UTC),
        )
