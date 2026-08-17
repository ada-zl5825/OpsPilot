from __future__ import annotations

from typing import Literal

from pydantic import Field

from mcp_servers.common.schemas import ServiceName, StrictModel, azure_input_schema

MetricName = Literal[
    "request_rate",
    "error_rate",
    "latency_p95",
    "latency_avg",
    "db_pool_checked_out",
    "db_pool_available",
    "db_pool_max",
    "cache_lookup_p95",
    "downstream_p95",
]
Aggregation = Literal["avg", "max", "p95", "rate"]
Severity = Literal["debug", "info", "warn", "error", "all"]


class MetricQueryInput(StrictModel):
    service: ServiceName
    metric: MetricName
    start: str = Field(min_length=10, max_length=40)
    end: str = Field(min_length=10, max_length=40)
    aggregation: Aggregation = "avg"
    path: str = Field(default="", max_length=64)
    limit: int = Field(default=60, ge=1, le=120)


class LogQueryInput(StrictModel):
    service: ServiceName
    start: str = Field(min_length=10, max_length=40)
    end: str = Field(min_length=10, max_length=40)
    severity: Severity = "error"
    contains: str = Field(default="", max_length=128)
    limit: int = Field(default=50, ge=1, le=200)


class TraceSummaryInput(StrictModel):
    start: str = Field(min_length=10, max_length=40)
    end: str = Field(min_length=10, max_length=40)
    service: str = Field(default="", max_length=32)
    trace_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9]*$")
    min_duration_ms: int = Field(default=0, ge=0, le=600000)
    limit: int = Field(default=20, ge=1, le=50)


OBSERVABILITY_INPUT_SCHEMAS = {
    "query_service_metrics": azure_input_schema(MetricQueryInput),
    "query_service_logs": azure_input_schema(LogQueryInput),
    "get_trace_summary": azure_input_schema(TraceSummaryInput),
}
