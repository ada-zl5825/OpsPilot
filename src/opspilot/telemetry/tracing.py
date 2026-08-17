from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span

_TRACER = trace.get_tracer("opspilot")


@contextmanager
def investigation_span(name: str, **attributes: Any) -> Iterator[Span]:
    """OpenTelemetry span. No-ops until a provider is configured."""
    with _TRACER.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, str(value))
        yield span
