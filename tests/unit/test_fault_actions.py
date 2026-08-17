import pytest
from simulator.fault_injection.actions import active, inject, reset, reset_all, status


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.values: dict[str, str] = {}

    async def hset(self, name: str, key: str, value: str) -> None:
        self.hashes.setdefault(name, {})[key] = value

    async def hget(self, name: str, key: str) -> str | None:
        return self.hashes.get(name, {}).get(key)

    async def hgetall(self, name: str) -> dict[str, str]:
        return dict(self.hashes.get(name, {}))

    async def set(self, name: str, value: str) -> None:
        self.values[name] = value

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def delete(self, name: str) -> None:
        self.values.pop(name, None)


@pytest.mark.asyncio
async def test_inject_reset_are_idempotent_for_two_cycles() -> None:
    redis = FakeRedis()
    for scenario_id in ("S01", "S02", "S03", "S04"):
        for _ in range(2):
            first = await inject(redis, scenario_id)
            second = await inject(redis, scenario_id)
            assert first["injected"] is True
            assert first["injected_at"]
            assert second["injected"] is True
            assert second["already"] is True
            assert (await active(redis))["scenario_id"] == scenario_id
            assert (await status(redis, scenario_id))["injected"] is True
            first_reset = await reset(redis, scenario_id)
            second_reset = await reset(redis, scenario_id)
            assert first_reset["injected"] is False
            assert second_reset["already"] is True
            assert (await status(redis, scenario_id))["injected"] is False


@pytest.mark.asyncio
async def test_reset_all_clears_every_flag() -> None:
    redis = FakeRedis()
    await inject(redis, "S01")
    await inject(redis, "S04")
    await reset_all(redis)
    assert (await status(redis, "S01"))["injected"] is False
    assert (await status(redis, "S04"))["injected"] is False
    assert (await active(redis))["active"] is False
