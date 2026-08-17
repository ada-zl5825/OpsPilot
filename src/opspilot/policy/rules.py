from __future__ import annotations

import re
from typing import Any

from opspilot.domain.remediation import (
    EXECUTABLE_ACTION_TYPES,
    RemediationActionType,
    RemediationProposal,
)

ALLOWED_NAMESPACES = frozenset({"lab"})
ALLOWED_SERVICES = frozenset({"gateway", "checkout", "payment", "inventory", "notification"})
ALLOWED_KINDS = frozenset({"Deployment"})
FORBIDDEN_PARAM_KEYS = frozenset(
    {
        "token",
        "kubeconfig",
        "as",
        "command",
        "shell",
        "script",
        "kubectl",
        "docker",
        "argv",
    }
)
ALLOWED_PARAM_KEYS: dict[RemediationActionType, frozenset[str]] = {
    RemediationActionType.RESTART_WORKLOAD: frozenset(),
    RemediationActionType.SCALE_WORKLOAD: frozenset({"replicas"}),
    RemediationActionType.ROLLBACK_DEPLOYMENT: frozenset({"to_revision"}),
    RemediationActionType.UPDATE_CONFIG: frozenset({"key", "value"}),
}

RESOURCE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
REVISION_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
SHELL_META_RE = re.compile(r"[;&|`$()<>\\\n\r]")
FORBIDDEN_FLAGS = (
    "--token",
    "--kubeconfig",
    "--as",
    "--context",
    "--user",
    "--certificate-authority",
    "--client-key",
    "--client-certificate",
    "--password",
    "--username",
)


def evaluate_rules(proposal: RemediationProposal) -> list[str]:
    violations: list[str] = []
    if proposal.action_type not in EXECUTABLE_ACTION_TYPES:
        violations.append(f"action {proposal.action_type.value} is not enabled")
    if proposal.target.namespace not in ALLOWED_NAMESPACES:
        violations.append(f"namespace {proposal.target.namespace} is not allowlisted")
    if proposal.target.kind not in ALLOWED_KINDS:
        violations.append(f"kind {proposal.target.kind} is not allowlisted")
    if proposal.target.name not in ALLOWED_SERVICES:
        violations.append(f"service {proposal.target.name} is not allowlisted")
    if proposal.target.service and proposal.target.service not in ALLOWED_SERVICES:
        violations.append(f"service {proposal.target.service} is not allowlisted")
    if not RESOURCE_NAME_RE.match(proposal.target.name):
        violations.append("target name is not a valid resource identifier")
    if not RESOURCE_NAME_RE.match(proposal.target.namespace):
        violations.append("namespace is not a valid resource identifier")

    allowed_keys = ALLOWED_PARAM_KEYS.get(proposal.action_type, frozenset())
    for key, value in proposal.parameters.items():
        lowered = key.lower()
        if lowered in FORBIDDEN_PARAM_KEYS:
            violations.append(f"parameter {key} is forbidden")
        elif key not in allowed_keys:
            violations.append(f"parameter {key} is not allowed for {proposal.action_type.value}")
        violations.extend(_value_violations(f"parameters.{key}", value))

    violations.extend(_value_violations("target.name", proposal.target.name))
    violations.extend(_value_violations("target.namespace", proposal.target.namespace))
    if proposal.action_type is RemediationActionType.SCALE_WORKLOAD:
        violations.extend(_scale_violations(proposal.parameters))
    if proposal.action_type is RemediationActionType.ROLLBACK_DEPLOYMENT:
        violations.extend(_rollback_violations(proposal.parameters))
    return violations


def _scale_violations(parameters: dict[str, Any]) -> list[str]:
    replicas = parameters.get("replicas")
    if not isinstance(replicas, int) or isinstance(replicas, bool):
        return ["scale requires integer replicas between 1 and 10"]
    if replicas < 1 or replicas > 10:
        return ["scale replicas must be between 1 and 10"]
    return []


def _rollback_violations(parameters: dict[str, Any]) -> list[str]:
    revision = parameters.get("to_revision")
    if revision in (None, ""):
        return []
    if not isinstance(revision, str) or not REVISION_RE.match(revision):
        return ["to_revision must be a short alphanumeric version"]
    return []


def _value_violations(path: str, value: Any) -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_PARAM_KEYS:
                violations.append(f"parameter {key} is forbidden")
            violations.extend(_value_violations(f"{path}.{key}", item))
        return violations
    if isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_value_violations(f"{path}[{index}]", item))
        return violations
    if not isinstance(value, str):
        return violations
    if SHELL_META_RE.search(value):
        violations.append(f"{path} contains shell metacharacters")
    lowered = value.lower()
    for flag in FORBIDDEN_FLAGS:
        if flag in lowered:
            violations.append(f"{path} contains forbidden flag {flag}")
            break
    return violations
