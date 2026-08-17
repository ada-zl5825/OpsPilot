from __future__ import annotations

from typing import Any

from mcp_servers.common.time_range import TimeWindow


class FakeMetricsBackend:
    def __init__(self, points: list[dict[str, Any]] | None = None, sleep_s: float = 0) -> None:
        self.points = points or [
            {"t": 1_700_000_000.0, "v": 0.12},
            {"t": 1_700_000_060.0, "v": 0.18},
        ]
        self.sleep_s = sleep_s
        self.last_query = ""

    def query_range(self, query: str, window: TimeWindow, limit: int) -> list[dict[str, Any]]:
        if self.sleep_s:
            import time

            time.sleep(self.sleep_s)
        self.last_query = query
        _ = window
        return list(self.points[:limit])


class FakeLogsBackend:
    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self.entries = entries or [
            {
                "ts": "1700000000000000000",
                "service": "checkout",
                "severity": "error",
                "message": "checkout failed authorization=Bearer sk-lab-secret",
            },
            {
                "ts": "1700000060000000000",
                "service": "checkout",
                "severity": "error",
                "message": "connection wait exceeded the request deadline",
            },
            {
                "ts": "1700000120000000000",
                "service": "checkout",
                "severity": "info",
                "message": "order accepted",
            },
        ]

    def query_range(
        self,
        service: str,
        window: TimeWindow,
        *,
        severity: str,
        contains: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        _ = window
        rows = [row for row in self.entries if row.get("service") == service]
        if severity != "all":
            rows = [row for row in rows if row.get("severity") == severity]
        if contains:
            needle = contains.lower()
            rows = [row for row in rows if needle in str(row.get("message", "")).lower()]
        return rows[:limit]


class FakeTracesBackend:
    def __init__(self, traces: list[dict[str, Any]] | None = None) -> None:
        self.traces = traces or [
            {
                "trace_id": "aabbccddeeff00112233445566778899",
                "root_service": "checkout",
                "root_name": "POST /orders",
                "duration_ms": 2100,
                "span_count": 6,
                "error_count": 1,
                "services": ["gateway", "checkout", "payment"],
            },
            {
                "trace_id": "11223344556677889900aabbccddeeff",
                "root_service": "payment",
                "root_name": "POST /charge",
                "duration_ms": 180,
                "span_count": 3,
                "error_count": 0,
                "services": ["payment"],
            },
        ]

    def search(
        self,
        window: TimeWindow,
        *,
        service: str,
        trace_id: str,
        min_duration_ms: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        _ = window
        rows = list(self.traces)
        if trace_id:
            rows = [row for row in rows if row["trace_id"] == trace_id]
        if service:
            rows = [row for row in rows if service in row.get("services", [])]
        if min_duration_ms:
            rows = [row for row in rows if int(row.get("duration_ms", 0)) >= min_duration_ms]
        return rows[:limit]
