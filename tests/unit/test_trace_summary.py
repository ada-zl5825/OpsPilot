from pathlib import Path

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.observability.fakes import FakeTracesBackend
from mcp_servers.observability.tools import get_trace_summary
from mcp_servers.observability.traces import (
    enrich_longest_traces,
    search_hits_to_summaries,
    summarize_otlp_trace,
)


def _runtime(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(
        timeout_seconds=5,
        max_result_bytes=65536,
        artifacts=ArtifactStore(tmp_path),
    )


def _otlp_payload() -> dict:
    return {
        "batches": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "checkout"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "name": "checkout.order",
                                "startTimeUnixNano": "1000000000",
                                "endTimeUnixNano": "2100000000",
                                "status": {"code": 0},
                            },
                            {
                                "name": "checkout.payment",
                                "startTimeUnixNano": "1100000000",
                                "endTimeUnixNano": "3100000000",
                                "status": {"code": 2},
                                "attributes": [
                                    {
                                        "key": "peer.service",
                                        "value": {"stringValue": "payment"},
                                    }
                                ],
                            },
                        ]
                    }
                ],
            },
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "payment"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "name": "POST /charge",
                                "startTimeUnixNano": "1200000000",
                                "endTimeUnixNano": "3000000000",
                                "status": {"code": 2},
                            }
                        ]
                    }
                ],
            },
        ]
    }


def test_summarize_otlp_trace_counts_errors_and_peers() -> None:
    summary = summarize_otlp_trace("abc", _otlp_payload())
    assert summary["error_count"] == 2
    assert summary["services"] == ["checkout", "payment"]
    assert summary["peer_services"] == ["payment"]
    assert summary["slowest_span"]["name"] == "checkout.payment"
    assert summary["slowest_span"]["peer_service"] == "payment"
    assert summary["slowest_span"]["duration_ms"] == 2000
    assert summary["enriched"] is True


def test_search_hits_do_not_invent_zero_errors() -> None:
    rows = search_hits_to_summaries(
        [
            {
                "traceID": "aa",
                "rootServiceName": "checkout",
                "rootTraceName": "POST /orders",
                "durationMs": 2000,
                "spanSet": {"matched": 4},
            }
        ],
        service="checkout",
        limit=10,
    )
    assert "error_count" not in rows[0]
    assert rows[0]["enriched"] is False
    assert rows[0]["services"] == ["checkout"]


def test_enrich_longest_traces_fills_peers_from_detail() -> None:
    rows = search_hits_to_summaries(
        [
            {"traceID": "slow", "durationMs": 2000, "rootServiceName": "checkout"},
            {"traceID": "fast", "durationMs": 100, "rootServiceName": "checkout"},
        ],
        service="checkout",
        limit=10,
    )
    fetched: list[str] = []

    def fetch(trace_id: str) -> dict:
        fetched.append(trace_id)
        return summarize_otlp_trace(trace_id, _otlp_payload())

    enrich_longest_traces(rows, fetch, limit=1)
    assert fetched == ["slow"]
    slow = next(item for item in rows if item["trace_id"] == "slow")
    assert slow["error_count"] == 2
    assert "payment" in slow["services"]
    assert slow["peer_services"] == ["payment"]
    fast = next(item for item in rows if item["trace_id"] == "fast")
    assert "error_count" not in fast
    assert fast["enriched"] is False


def test_get_trace_summary_exposes_peer_services(tmp_path: Path) -> None:
    result = get_trace_summary(
        {
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "service": "checkout",
            "min_duration_ms": 1000,
            "limit": 10,
        },
        backend=FakeTracesBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert "payment" in result["summary"]["services"]
    assert "payment" in result["summary"]["peer_services"]
    assert result["summary"]["error_traces"] == 1
    assert result["summary"]["slowest_span"]["peer_service"] == "payment"
    assert "mirrored 5xx" in result["suggested_fix"]
