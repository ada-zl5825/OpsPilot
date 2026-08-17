from __future__ import annotations

from opspilot.domain.remediation import RemediationProposal

ALLOWED_NAMESPACES = frozenset({"lab"})
FORBIDDEN_PARAM_KEYS = frozenset({"token", "kubeconfig", "as", "command", "shell"})


def evaluate_rules(proposal: RemediationProposal) -> list[str]:
    violations: list[str] = []
    if proposal.target.namespace not in ALLOWED_NAMESPACES:
        violations.append(f"namespace {proposal.target.namespace} is not allowlisted")
    for key in proposal.parameters:
        if key.lower() in FORBIDDEN_PARAM_KEYS:
            violations.append(f"parameter {key} is forbidden")
    return violations
