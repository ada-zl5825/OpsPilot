from __future__ import annotations

import time
from typing import Protocol

from simulator.services.common.config import FLAG_KEY, RELEASED_AT_KEY, VERSION_KEY
from simulator.services.common.tokens import CHECKOUT_VERSION_HEALTHY


class RedisLike(Protocol):
    async def hset(self, name: str, key: str, value: str) -> object: ...
    async def hget(self, name: str, key: str) -> str | None: ...
    async def hgetall(self, name: str) -> dict[str, str]: ...
    async def set(self, name: str, value: str) -> object: ...
    async def get(self, name: str) -> str | None: ...


class LabFlags:
    def __init__(self, redis: RedisLike, ttl_sec: float = 0.2) -> None:
        self._redis = redis
        self._ttl_sec = ttl_sec
        self._cache: dict[str, str] = {}
        self._cache_at = 0.0

    async def refresh(self) -> None:
        self._cache = dict(await self._redis.hgetall(FLAG_KEY))
        self._cache_at = time.monotonic()

    async def is_on(self, scenario_id: str) -> bool:
        if time.monotonic() - self._cache_at > self._ttl_sec:
            await self.refresh()
        return self._cache.get(scenario_id) == "on"

    async def checkout_version(self) -> str:
        value = await self._redis.get(VERSION_KEY)
        return value or CHECKOUT_VERSION_HEALTHY

    async def released_at(self) -> str | None:
        return await self._redis.get(RELEASED_AT_KEY)
