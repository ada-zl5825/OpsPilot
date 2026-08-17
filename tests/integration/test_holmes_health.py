import os

import httpx
import pytest

from opspilot.settings import get_settings

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_holmes_healthz_when_running() -> None:
    if os.environ.get("OPSPILOT_REQUIRE_HOLMES") != "1":
        pytest.skip("set OPSPILOT_REQUIRE_HOLMES=1 after docker compose --profile holmes up")
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=5.0) as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
