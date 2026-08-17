from __future__ import annotations

from opspilot.domain.remediation import RemediationProposal
from opspilot.policy.risk import classify_risk
from opspilot.policy.rules import evaluate_rules


class PolicyDecision:
    def __init__(self, allowed: bool, reasons: list[str]) -> None:
        self.allowed = allowed
        self.reasons = reasons


class PolicyEngine:
    def evaluate(self, proposal: RemediationProposal) -> PolicyDecision:
        reasons = evaluate_rules(proposal)
        _ = classify_risk(proposal)
        return PolicyDecision(allowed=not reasons, reasons=reasons)
