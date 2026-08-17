from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from simulator.services.common.http import create_service, otel_lifespan
from simulator.services.common.logging import configure_logging
from simulator.services.common.otel import tracer

log = configure_logging()
app = create_service(lifespan=otel_lifespan)


class NotifyIn(BaseModel):
    order_id: str
    sku: str


@app.get("/version")
def version_info() -> dict[str, str]:
    return {"service": "notification", "version": "1.0.0"}


@app.post("/notify")
async def notify(body: NotifyIn) -> dict[str, Any]:
    with tracer().start_as_current_span("notification.accept") as span:
        span.set_attribute("order.id", body.order_id)
        log.info("notification accepted", extra={"request_id": body.order_id})
        return {"status": "accepted", "order_id": body.order_id}
