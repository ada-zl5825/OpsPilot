from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from simulator.services.common.config import OTEL_ENDPOINT, SERVICE_NAME, SERVICE_VERSION

_log = logging.getLogger("lab.otel")


def _grpc_endpoint(raw: str) -> str:
    value = raw.strip()
    for prefix in ("http://", "https://"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def init_otel(service_name: str | None = None) -> None:
    name = service_name or SERVICE_NAME
    endpoint = _grpc_endpoint(OTEL_ENDPOINT)
    resource = Resource.create({"service.name": name, "service.version": SERVICE_VERSION})
    try:
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )
        trace.set_tracer_provider(tracer_provider)

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
        )
        set_logger_provider(logger_provider)
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logging.getLogger(name).addHandler(handler)
    except Exception:
        _log.warning("otel exporter not available; continuing without remote export")


def tracer() -> trace.Tracer:
    return trace.get_tracer(SERVICE_NAME)
