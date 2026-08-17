from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from simulator.services.common.config import SERVICE_NAME

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests",
    ["service", "method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["service", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)
DB_POOL_CHECKED_OUT = Gauge("checkout_db_pool_checked_out", "Checkout DB pool connections in use")
DB_POOL_MAX = Gauge("checkout_db_pool_max", "Checkout DB pool max size")
DB_POOL_AVAILABLE = Gauge("checkout_db_pool_available", "Checkout DB pool idle connections")
CACHE_LOOKUPS = Counter("cache_lookups_total", "Cache lookups", ["result"])
CACHE_LOOKUP_DURATION = Histogram(
    "cache_lookup_duration_seconds",
    "Cache lookup duration",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
DOWNSTREAM_DURATION = Histogram(
    "downstream_request_duration_seconds",
    "Downstream call duration",
    ["target"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)
APP_INFO = Gauge("app_info", "Build metadata", ["service", "version"])


def _route_label(path: str) -> str:
    parts = [part if not _looks_id(part) else ":id" for part in path.split("/")]
    return "/".join(parts) or "/"


def _looks_id(part: str) -> bool:
    if not part:
        return False
    return (
        len(part) >= 8
        and all(ch.isalnum() or ch in "-_" for ch in part)
        and any(ch.isdigit() for ch in part)
    )


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in {"/metrics", "/healthz"}:
            return await call_next(request)
        started = time.perf_counter()
        response = await call_next(request)
        path = _route_label(request.url.path)
        HTTP_REQUESTS.labels(SERVICE_NAME, request.method, path, str(response.status_code)).inc()
        HTTP_LATENCY.labels(SERVICE_NAME, path).observe(time.perf_counter() - started)
        return response


def mount_metrics(app: FastAPI, version: str) -> None:
    APP_INFO.labels(SERVICE_NAME, version).set(1)
    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
