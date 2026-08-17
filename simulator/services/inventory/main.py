from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from simulator.services.common.http import create_service, otel_lifespan
from simulator.services.common.logging import configure_logging
from simulator.services.common.otel import tracer

log = configure_logging()
app = create_service(lifespan=otel_lifespan)
_stock = {"sku-100": 1_000_000, "sku-200": 500_000}
_lock = asyncio.Lock()


class ReserveIn(BaseModel):
    sku: str
    qty: int = Field(ge=1, le=100)


@app.get("/version")
def version_info() -> dict[str, str]:
    return {"service": "inventory", "version": "1.0.0"}


@app.get("/stock/{sku}")
async def stock(sku: str) -> dict[str, Any]:
    qty = _stock.get(sku)
    if qty is None:
        raise HTTPException(status_code=404, detail="unknown sku")
    return {"sku": sku, "available": qty}


@app.post("/reserve")
async def reserve(body: ReserveIn) -> dict[str, Any]:
    with tracer().start_as_current_span("inventory.reserve") as span:
        span.set_attribute("inventory.sku", body.sku)
        async with _lock:
            available = _stock.get(body.sku, 0)
            if available < body.qty:
                log.info("stock reservation declined", extra={"field": "qty"})
                raise HTTPException(status_code=409, detail="insufficient stock")
            _stock[body.sku] = available - body.qty
        return {"sku": body.sku, "reserved": body.qty, "remaining": _stock[body.sku]}
