from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from simulator.services.common.config import (
    CACHE_DELAY_SEC,
    DATABASE_URL,
    DB_POOL_MAX,
    INVENTORY_URL,
    NOTIFICATION_URL,
    PAYMENT_TIMEOUT_SEC,
    PAYMENT_URL,
    REDIS_URL,
    SERVICE_NAME,
)
from simulator.services.common.flags import LabFlags
from simulator.services.common.http import create_service, error_body
from simulator.services.common.logging import configure_logging
from simulator.services.common.metrics import (
    CACHE_LOOKUP_DURATION,
    CACHE_LOOKUPS,
    DB_POOL_AVAILABLE,
    DB_POOL_CHECKED_OUT,
    DOWNSTREAM_DURATION,
)
from simulator.services.common.metrics import (
    DB_POOL_MAX as DB_POOL_MAX_GAUGE,
)
from simulator.services.common.otel import init_otel, tracer
from simulator.services.common.tokens import (
    CHECKOUT_SHA,
    CHECKOUT_VERSION_CURRENT,
    CHECKOUT_VERSION_HEALTHY,
    SCENARIO_TOKENS,
)

log = configure_logging()
UNIT_CENTS = 1999
BASELINE_RELEASED_AT = "2026-08-10T09:00:00+00:00"


async def _connect_pool() -> asyncpg.Pool:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            return await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=DB_POOL_MAX,
                command_timeout=5,
            )
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1)
    raise RuntimeError("database unavailable") from last_error


async def _init_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shop_orders (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                qty INTEGER NOT NULL,
                amount_cents INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


def _refresh_pool_metrics(pool: asyncpg.Pool) -> None:
    idle = pool.get_idle_size()
    size = pool.get_size()
    DB_POOL_MAX_GAUGE.set(pool.get_max_size())
    DB_POOL_AVAILABLE.set(idle)
    DB_POOL_CHECKED_OUT.set(max(size - idle, 0))


async def _hold_pool(app: FastAPI) -> None:
    held: list[asyncpg.Connection] = []
    flags: LabFlags = app.state.flags
    pool: asyncpg.Pool = app.state.pool
    try:
        while True:
            on = await flags.is_on("S01")
            if on and not held:
                for _ in range(pool.get_max_size()):
                    try:
                        held.append(await pool.acquire(timeout=2))
                    except TimeoutError:
                        break
                _refresh_pool_metrics(pool)
            elif not on and held:
                for conn in held:
                    await pool.release(conn)
                held.clear()
                _refresh_pool_metrics(pool)
            else:
                _refresh_pool_metrics(pool)
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        for conn in held:
            await pool.release(conn)
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_otel(SERVICE_NAME)
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    pool = await _connect_pool()
    await _init_schema(pool)
    app.state.redis = redis_client
    app.state.flags = LabFlags(redis_client)
    app.state.pool = pool
    app.state.http = httpx.AsyncClient()
    holder = asyncio.create_task(_hold_pool(app))
    _refresh_pool_metrics(pool)
    yield
    holder.cancel()
    with suppress(asyncio.CancelledError):
        await holder
    await app.state.http.aclose()
    await pool.close()
    await redis_client.aclose()


app = create_service(version=CHECKOUT_VERSION_HEALTHY, lifespan=lifespan)


class OrderIn(BaseModel):
    sku: str = "sku-100"
    qty: int = Field(default=1, ge=1, le=20)


async def _current_version() -> str:
    flags: LabFlags = app.state.flags
    return await flags.checkout_version()


@app.get("/version")
async def version_info() -> dict[str, str]:
    version = await _current_version()
    build_id = SCENARIO_TOKENS["S03"] if version == CHECKOUT_VERSION_CURRENT else "bld-141-ok"
    return {
        "service": "checkout",
        "version": version,
        "git_sha": CHECKOUT_SHA.get(version, "9e2b110c"),
        "build_id": build_id,
    }


@app.get("/releases")
async def releases() -> dict[str, Any]:
    version = await _current_version()
    released_at = await app.state.flags.released_at() or BASELINE_RELEASED_AT
    previous = (
        {
            "version": CHECKOUT_VERSION_HEALTHY,
            "released_at": BASELINE_RELEASED_AT,
            "git_sha": CHECKOUT_SHA[CHECKOUT_VERSION_HEALTHY],
        }
        if version == CHECKOUT_VERSION_CURRENT
        else {
            "version": "1.3.8",
            "released_at": "2026-07-28T11:00:00+00:00",
            "git_sha": "41aa90d2",
        }
    )
    return {
        "service": "checkout",
        "current": {
            "version": version,
            "released_at": released_at,
            "git_sha": CHECKOUT_SHA.get(version, "9e2b110c"),
        },
        "history": [
            {
                "version": version,
                "released_at": released_at,
                "git_sha": CHECKOUT_SHA.get(version, "9e2b110c"),
            },
            previous,
        ],
        "neighbors": [
            {
                "service": "payment",
                "version": "2.1.0",
                "released_at": "2026-08-17T07:00:00+00:00",
            }
        ],
    }


async def _cache_lookup(sku: str) -> str | None:
    flags: LabFlags = app.state.flags
    started = time.perf_counter()
    key = f"cart:{sku}"
    if await flags.is_on("S02"):
        await asyncio.sleep(CACHE_DELAY_SEC)
        duration = time.perf_counter() - started
        CACHE_LOOKUPS.labels("miss").inc()
        CACHE_LOOKUP_DURATION.observe(duration)
        log.warning(
            "cache lookup exceeded latency budget",
            extra={
                "request_id": SCENARIO_TOKENS["S02"],
                "duration_ms": int(duration * 1000),
                "key_class": "cart",
            },
        )
        async with app.state.pool.acquire(timeout=2) as conn:
            await conn.execute("SELECT 1")
        return None
    value = await app.state.redis.get(key)
    duration = time.perf_counter() - started
    CACHE_LOOKUP_DURATION.observe(duration)
    CACHE_LOOKUPS.labels("hit" if value else "miss").inc()
    if value is None:
        await app.state.redis.set(key, sku, ex=300)
    return value


@app.post("/orders")
async def create_order(body: OrderIn, request: Request) -> Any:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    flags: LabFlags = app.state.flags
    version = await _current_version()
    with tracer().start_as_current_span("checkout.order") as span:
        span.set_attribute("request.id", request_id)
        span.set_attribute("checkout.version", version)
        if await flags.is_on("S03") or version == CHECKOUT_VERSION_CURRENT:
            request_id = SCENARIO_TOKENS["S03"]
            span.set_attribute("request.id", request_id)
            log.error(
                "order total computation failed",
                extra={"request_id": request_id, "field": "currency_scale", "version": version},
            )
            return error_body("unable to price order", request_id, 500)

        if await flags.is_on("S02"):
            request_id = SCENARIO_TOKENS["S02"]
            span.set_attribute("request.id", request_id)

        try:
            async with app.state.pool.acquire(timeout=1.0):
                _refresh_pool_metrics(app.state.pool)
            with tracer().start_as_current_span("checkout.cache_lookup"):
                await _cache_lookup(body.sku)
            with tracer().start_as_current_span("checkout.inventory"):
                started = time.perf_counter()
                reserved = await app.state.http.post(
                    f"{INVENTORY_URL}/reserve",
                    json={"sku": body.sku, "qty": body.qty},
                    timeout=2.0,
                )
                DOWNSTREAM_DURATION.labels("inventory").observe(time.perf_counter() - started)
                reserved.raise_for_status()
            payment_ref = request_id
            if await flags.is_on("S04"):
                payment_ref = SCENARIO_TOKENS["S04"]
            with tracer().start_as_current_span("checkout.payment") as payment_span:
                payment_span.set_attribute("peer.service", "payment")
                payment_span.set_attribute("request.id", payment_ref)
                started = time.perf_counter()
                try:
                    charged = await app.state.http.post(
                        f"{PAYMENT_URL}/charge",
                        json={
                            "order_ref": request_id,
                            "amount_cents": UNIT_CENTS * body.qty,
                            "payment_ref": payment_ref,
                        },
                        timeout=PAYMENT_TIMEOUT_SEC,
                    )
                    charged.raise_for_status()
                except httpx.TimeoutException:
                    request_id = SCENARIO_TOKENS["S04"]
                    log.error(
                        "downstream request deadline exceeded",
                        extra={"request_id": request_id, "target": "payment"},
                    )
                    return error_body("checkout failed", request_id, 504)
                finally:
                    DOWNSTREAM_DURATION.labels("payment").observe(time.perf_counter() - started)
            async with app.state.pool.acquire(timeout=1.0) as conn:
                _refresh_pool_metrics(app.state.pool)
                order_id = str(uuid4())
                await conn.execute(
                    """
                    INSERT INTO shop_orders (id, sku, qty, amount_cents, status)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    order_id,
                    body.sku,
                    body.qty,
                    UNIT_CENTS * body.qty,
                    "confirmed",
                )
            try:
                await app.state.http.post(
                    f"{NOTIFICATION_URL}/notify",
                    json={"order_id": order_id, "sku": body.sku},
                    timeout=1.0,
                )
            except httpx.HTTPError:
                log.info("notification deferred", extra={"request_id": request_id})
            return {
                "order_id": order_id,
                "status": "confirmed",
                "request_id": request_id,
                "amount_cents": UNIT_CENTS * body.qty,
            }
        except TimeoutError:
            request_id = SCENARIO_TOKENS["S01"]
            span.set_attribute("request.id", request_id)
            log.error(
                "database connection wait exceeded request deadline",
                extra={"request_id": request_id, "duration_ms": 1000},
            )
            _refresh_pool_metrics(app.state.pool)
            return error_body("service unavailable", request_id, 503)
        except httpx.HTTPStatusError as exc:
            log.error("downstream rejected request", extra={"request_id": request_id})
            return error_body("checkout failed", request_id, exc.response.status_code)
        finally:
            _refresh_pool_metrics(app.state.pool)


@app.get("/orders/{order_id}")
async def get_order(order_id: str) -> Any:
    async with app.state.pool.acquire(timeout=2) as conn:
        row = await conn.fetchrow(
            "SELECT id, sku, qty, amount_cents, status FROM shop_orders WHERE id=$1", order_id
        )
    if row is None:
        return error_body("order not found", order_id, 404)
        return dict(row)
