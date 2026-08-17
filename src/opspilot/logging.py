from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, cast

import structlog
from structlog.typing import EventDict, FilteringBoundLogger, Processor

from opspilot.policy.redaction import redact_mapping, redact_secrets

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
        "openai_api_key",
        "anthropic_api_key",
    }
)


def _redact_event(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    redacted = redact_mapping(event_dict, sensitive_keys=_SENSITIVE_KEYS)
    if not isinstance(redacted, MutableMapping):
        return event_dict
    message = redacted.get("event")
    if isinstance(message, str):
        redacted["event"] = redact_secrets(message)
    return redacted


def configure_logging() -> None:
    processors: list[Processor] = [
        structlog.processors.add_log_level,
        _redact_event,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(processors=processors)


def get_logger(name: str) -> FilteringBoundLogger:
    configure_logging()
    return cast(FilteringBoundLogger, structlog.get_logger(name))
