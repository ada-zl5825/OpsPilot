from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from opspilot.domain.remediation import ExecutionAttempt, RemediationProposal
from opspilot.executor.base import Executor
from opspilot.executor.cluster import ClusterBackend, InMemoryCluster
from opspilot.executor.commands import compile_typed_command


class LabExecutor(Executor):
    def __init__(self, cluster: ClusterBackend | None = None) -> None:
        self.cluster = cluster or InMemoryCluster()

    def execute(self, proposal: RemediationProposal) -> ExecutionAttempt:
        started = datetime.now(UTC)
        command = compile_typed_command(proposal)
        applied = self.cluster.apply(command)
        ended = datetime.now(UTC)
        return ExecutionAttempt(
            execution_id=uuid4(),
            proposal_id=proposal.proposal_id,
            status="succeeded",
            command_plan=applied.argv or command.argv(),
            started_at=started,
            ended_at=ended,
        )
