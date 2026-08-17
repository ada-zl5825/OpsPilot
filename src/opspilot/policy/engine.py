from __future__ import annotations

from opspilot.domain.remediation import RemediationProposal
from opspilot.policy.risk import Risk, classify_risk
from opspilot.policy.rules import evaluate_rules


class PolicyDecision:
    def __init__(self, allowed: bool, reasons: list[str], risk: Risk = "medium") -> None:
        self.allowed = allowed
        self.reasons = reasons
        self.risk = risk


class PolicyEngine:
    def evaluate(self, proposal: RemediationProposal) -> PolicyDecision:
        reasons = evaluate_rules(proposal)
        risk = classify_risk(proposal)
        return PolicyDecision(allowed=not reasons, reasons=reasons, risk=risk)
