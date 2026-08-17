from __future__ import annotations

from opspilot.domain.remediation import ExecutionAttempt, RemediationProposal


async def rollback(proposal: RemediationProposal) -> ExecutionAttempt:
    _ = proposal
    raise NotImplementedError("Phase 4: rollback is not implemented")
