from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from simulator.services.common.config import FLAG_KEY, RELEASED_AT_KEY, VERSION_KEY
from simulator.services.common.tokens import CHECKOUT_VERSION_CURRENT, CHECKOUT_VERSION_HEALTHY

SCENARIO_IDS = ("S01", "S02", "S03", "S04")


class RedisLike(Protocol):
    async def hset(self, name: str, key: str, value: str) -> object: ...
    async def hget(self, name: str, key: str) -> str | None: ...
    async def hgetall(self, name: str) -> dict[str, str]: ...
    async def set(self, name: str, value: str) -> object: ...
    async def get(self, name: str) -> str | None: ...


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


async def inject(redis: RedisLike, scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIO_IDS:
        raise KeyError(scenario_id)
    previous = await redis.hget(FLAG_KEY, scenario_id)
    await redis.hset(FLAG_KEY, scenario_id, "on")
    if scenario_id == "S03":
        await redis.set(VERSION_KEY, CHECKOUT_VERSION_CURRENT)
        await redis.set(RELEASED_AT_KEY, _now())
    return {
        "scenario_id": scenario_id,
        "injected": True,
        "already": previous == "on",
        "updated_at": _now(),
    }


async def reset(redis: RedisLike, scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIO_IDS:
        raise KeyError(scenario_id)
    previous = await redis.hget(FLAG_KEY, scenario_id)
    await redis.hset(FLAG_KEY, scenario_id, "off")
    if scenario_id == "S03":
        await redis.set(VERSION_KEY, CHECKOUT_VERSION_HEALTHY)
        await redis.set(RELEASED_AT_KEY, _now())
    return {
        "scenario_id": scenario_id,
        "injected": False,
        "already": previous in {None, "off"},
        "updated_at": _now(),
    }


async def reset_all(redis: RedisLike) -> dict[str, object]:
    results = [await reset(redis, scenario_id) for scenario_id in SCENARIO_IDS]
    return {"reset": results}


async def status(redis: RedisLike, scenario_id: str) -> dict[str, object]:
    if scenario_id not in SCENARIO_IDS:
        raise KeyError(scenario_id)
    flag = await redis.hget(FLAG_KEY, scenario_id)
    payload: dict[str, object] = {
        "scenario_id": scenario_id,
        "injected": flag == "on",
        "updated_at": _now(),
    }
    if scenario_id == "S03":
        payload["version"] = await redis.get(VERSION_KEY) or CHECKOUT_VERSION_HEALTHY
    return payload
