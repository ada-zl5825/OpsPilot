from __future__ import annotations

import re
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{16,}"),
)

REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "azure_api_key",
        "azure_openai_api_key",
        "authorization",
        "token",
        "password",
        "secret",
        "kubeconfig",
        "deploy_token",
        "github_token",
    }
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                out[key] = REDACTED
            else:
                out[key] = redact_mapping(item)
        return out
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    if isinstance(value, str):
        return redact_secrets(value)
    return value


def safe_params(params: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_mapping(params)
    if not isinstance(redacted, dict):
        return {}
    return redacted
