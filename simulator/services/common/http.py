from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from simulator.services.common.config import SERVICE_NAME, SERVICE_VERSION
from simulator.services.common.logging import configure_logging
from simulator.services.common.metrics import mount_metrics
from simulator.services.common.otel import init_otel


def error_body(message: str, request_id: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": message, "request_id": request_id},
    )


def create_service(
    *,
    version: str = SERVICE_VERSION,
    lifespan: Any | None = None,
) -> FastAPI:
    configure_logging()
    app = FastAPI(title=SERVICE_NAME, version=version, lifespan=lifespan)
    mount_metrics(app, version)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": SERVICE_NAME}

    return app


@asynccontextmanager
async def otel_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_otel(SERVICE_NAME)
    yield
