from __future__ import annotations

from abc import ABC, abstractmethod

from opspilot.domain.remediation import ExecutionAttempt, RemediationProposal


class Executor(ABC):
    @abstractmethod
    def execute(self, proposal: RemediationProposal) -> ExecutionAttempt:
        raise NotImplementedError
