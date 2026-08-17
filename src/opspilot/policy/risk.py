from __future__ import annotations

from typing import Literal

from opspilot.domain.remediation import RemediationActionType, RemediationProposal

Risk = Literal["low", "medium", "high", "critical"]

_ACTION_RISK: dict[RemediationActionType, Risk] = {
    RemediationActionType.RESTART_WORKLOAD: "medium",
    RemediationActionType.SCALE_WORKLOAD: "medium",
    RemediationActionType.ROLLBACK_DEPLOYMENT: "high",
    RemediationActionType.UPDATE_CONFIG: "high",
}


def classify_risk(proposal: RemediationProposal) -> Risk:
    return _ACTION_RISK[proposal.action_type]
