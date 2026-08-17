from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import redis.asyncio as redis
from fastapi import FastAPI
from pydantic import BaseModel, Field

from simulator.services.common.config import PAYMENT_HOLD_SEC, REDIS_URL, SERVICE_NAME
from simulator.services.common.flags import LabFlags
from simulator.services.common.http import create_service
from simulator.services.common.logging import configure_logging
from simulator.services.common.otel import init_otel, tracer
from simulator.services.common.tokens import SCENARIO_TOKENS

log = configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_otel(SERVICE_NAME)
    client = redis.from_url(REDIS_URL, decode_responses=True)
    app.state.redis = client
    app.state.flags = LabFlags(client)
    yield
    await client.aclose()


app = create_service(lifespan=lifespan)


class ChargeIn(BaseModel):
    order_ref: str
    amount_cents: int = Field(ge=1)
    payment_ref: str | None = None


@app.get("/version")
def version_info() -> dict[str, str]:
    return {"service": "payment", "version": "2.1.0"}


@app.post("/charge")
async def charge(body: ChargeIn) -> dict[str, Any]:
    flags: LabFlags = app.state.flags
    payment_ref = body.payment_ref or body.order_ref
    with tracer().start_as_current_span("payment.charge") as span:
        if await flags.is_on("S04"):
            payment_ref = SCENARIO_TOKENS["S04"]
            span.set_attribute("request.id", payment_ref)
            span.set_attribute("payment.ref", payment_ref)
            log.info(
                "payment authorization still pending",
                extra={"request_id": payment_ref, "target": "processor"},
            )
            await asyncio.sleep(PAYMENT_HOLD_SEC)
        span.set_attribute("request.id", payment_ref)
        charge_id = str(uuid4())
        return {"status": "captured", "charge_id": charge_id, "payment_ref": payment_ref}
