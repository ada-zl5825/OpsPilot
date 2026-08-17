from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from simulator.services.common.config import (
    ACTIVE_SCENARIO_KEY,
    FLAG_KEY,
    INJECTED_AT_KEY,
    RELEASED_AT_KEY,
    VERSION_KEY,
)
from simulator.services.common.tokens import CHECKOUT_VERSION_CURRENT, CHECKOUT_VERSION_HEALTHY

SCENARIO_IDS = ("S01", "S02", "S03", "S04")


class RedisLike(Protocol):
    async def hset(self, name: str, key: str, value: str) -> object: ...
    async def hget(self, name: str, key: str) -> str | None: ...
    async def hgetall(self, name: str) -> dict[str, str]: ...
    async def set(self, name: str, value: str) -> object: ...
    async def get(self, name: str) -> str | None: ...
    async def delete(self, name: str) -> object: ...


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


async def inject(redis: RedisLike, scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIO_IDS:
        raise KeyError(scenario_id)
    previous = await redis.hget(FLAG_KEY, scenario_id)
    now = _now()
    await redis.hset(FLAG_KEY, scenario_id, "on")
    await redis.hset(INJECTED_AT_KEY, scenario_id, now)
    await redis.set(ACTIVE_SCENARIO_KEY, scenario_id)
    if scenario_id == "S03":
        await redis.set(VERSION_KEY, CHECKOUT_VERSION_CURRENT)
        await redis.set(RELEASED_AT_KEY, now)
    return {
        "scenario_id": scenario_id,
        "injected": True,
        "already": previous == "on",
        "injected_at": now,
        "updated_at": now,
    }


async def reset(redis: RedisLike, scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIO_IDS:
        raise KeyError(scenario_id)
    previous = await redis.hget(FLAG_KEY, scenario_id)
    now = _now()
    await redis.hset(FLAG_KEY, scenario_id, "off")
    active = await redis.get(ACTIVE_SCENARIO_KEY)
    if active == scenario_id:
        await redis.delete(ACTIVE_SCENARIO_KEY)
    if scenario_id == "S03":
        await redis.set(VERSION_KEY, CHECKOUT_VERSION_HEALTHY)
        await redis.set(RELEASED_AT_KEY, now)
    return {
        "scenario_id": scenario_id,
        "injected": False,
        "already": previous in {None, "off"},
        "updated_at": now,
    }


async def reset_all(redis: RedisLike) -> dict[str, object]:
    results = [await reset(redis, scenario_id) for scenario_id in SCENARIO_IDS]
    await redis.delete(ACTIVE_SCENARIO_KEY)
    return {"reset": results}


async def active(redis: RedisLike) -> dict[str, object]:
    scenario_id = await redis.get(ACTIVE_SCENARIO_KEY)
    if not scenario_id:
        return {"active": False}
    injected_at = await redis.hget(INJECTED_AT_KEY, scenario_id)
    return {
        "active": True,
        "scenario_id": scenario_id,
        "injected_at": injected_at,
    }


async def status(redis: RedisLike, scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIO_IDS:
        raise KeyError(scenario_id)
    flag = await redis.hget(FLAG_KEY, scenario_id)
    payload: dict[str, object] = {
        "scenario_id": scenario_id,
        "injected": flag == "on",
        "injected_at": await redis.hget(INJECTED_AT_KEY, scenario_id),
        "updated_at": _now(),
    }
    if scenario_id == "S03":
        payload["version"] = await redis.get(VERSION_KEY) or CHECKOUT_VERSION_HEALTHY
    return payload
