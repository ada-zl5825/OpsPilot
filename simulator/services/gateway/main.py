from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from simulator.services.common.config import (
    CHECKOUT_URL,
    INVENTORY_URL,
    NOTIFICATION_URL,
    PAYMENT_URL,
    SERVICE_NAME,
)
from simulator.services.common.http import create_service
from simulator.services.common.logging import configure_logging
from simulator.services.common.otel import init_otel, tracer

log = configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_otel(SERVICE_NAME)
    app.state.http = httpx.AsyncClient()
    yield
    await app.state.http.aclose()


app = create_service(lifespan=lifespan)


@app.get("/version")
def version_info() -> dict[str, str]:
    return {"service": "gateway", "version": "1.0.0"}


async def _probe(url: str) -> str:
    try:
        response = await app.state.http.get(f"{url}/healthz", timeout=1.0)
        return "up" if response.status_code == 200 else "degraded"
    except httpx.HTTPError:
        return "unreachable"


@app.get("/api/store/status")
async def store_status() -> dict[str, Any]:
    with tracer().start_as_current_span("gateway.store_status"):
        components = {
            "checkout": await _probe(CHECKOUT_URL),
            "payment": await _probe(PAYMENT_URL),
            "inventory": await _probe(INVENTORY_URL),
            "notification": await _probe(NOTIFICATION_URL),
        }
        overall = "ok" if all(value == "up" for value in components.values()) else "degraded"
        return {"status": overall, "components": components}


@app.api_route("/api/orders", methods=["POST"])
@app.api_route("/api/orders/{order_id}", methods=["GET"])
async def proxy_orders(request: Request, order_id: str | None = None) -> Response:
    suffix = f"/orders/{order_id}" if order_id else "/orders"
    body = await request.body()
    headers = {}
    request_id = request.headers.get("x-request-id")
    if request_id:
        headers["x-request-id"] = request_id
    with tracer().start_as_current_span("gateway.checkout") as span:
        if request_id:
            span.set_attribute("request.id", request_id)
        try:
            upstream = await app.state.http.request(
                request.method,
                f"{CHECKOUT_URL}{suffix}",
                content=body,
                headers=headers,
                timeout=8.0,
            )
        except httpx.TimeoutException:
            log.error("upstream request deadline exceeded", extra={"target": "checkout"})
            return JSONResponse({"error": "upstream timeout"}, status_code=504)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )
