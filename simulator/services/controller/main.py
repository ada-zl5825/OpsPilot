from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException

from simulator.fault_injection.actions import SCENARIO_IDS, active, inject, reset, reset_all, status
from simulator.services.common.config import REDIS_URL, SERVICE_NAME
from simulator.services.common.http import create_service
from simulator.services.common.otel import init_otel

# Controller responses never include ground truth or verification codes.


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_otel(SERVICE_NAME)
    client = redis.from_url(REDIS_URL, decode_responses=True)
    app.state.redis = client
    yield
    await client.aclose()


app = create_service(lifespan=lifespan)


@app.get("/version")
def version_info() -> dict[str, str]:
    return {"service": "controller", "version": "1.0.0"}


@app.get("/v1/scenarios")
def list_scenarios() -> dict[str, object]:
    return {"scenarios": list(SCENARIO_IDS)}


@app.get("/v1/active")
async def active_incident() -> dict[str, object]:
    return await active(app.state.redis)


@app.get("/v1/scenarios/{scenario_id}")
async def scenario_status(scenario_id: str) -> dict[str, object]:
    try:
        return await status(app.state.redis, scenario_id.upper())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown scenario") from exc


@app.post("/v1/scenarios/{scenario_id}/inject")
async def inject_scenario(scenario_id: str) -> dict[str, object]:
    try:
        return await inject(app.state.redis, scenario_id.upper())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown scenario") from exc


@app.post("/v1/scenarios/{scenario_id}/reset")
async def reset_scenario(scenario_id: str) -> dict[str, object]:
    try:
        return await reset(app.state.redis, scenario_id.upper())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown scenario") from exc


@app.post("/v1/reset")
async def reset_lab() -> dict[str, object]:
    return await reset_all(app.state.redis)
