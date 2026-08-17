from __future__ import annotations

from opspilot.domain.remediation import ExecutionAttempt, RemediationProposal
from opspilot.executor.base import Executor


class DockerExecutor(Executor):
    async def execute(self, proposal: RemediationProposal) -> ExecutionAttempt:
        _ = proposal
        raise NotImplementedError("Phase 4: docker executor is not implemented")
