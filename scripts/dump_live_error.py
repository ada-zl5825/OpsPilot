import asyncio
import json

import httpx

from opspilot.holmes.client import HolmesClient
from opspilot.settings import get_settings


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=180.0) as http:
        client = HolmesClient(settings, client=http)
        result = await client.ask("Call lab_status and return the verification_code.")
    for event in result.raw_events:
        data = dict(event.data)
        for key in ("api_key", "AZURE_API_KEY", "authorization"):
            data.pop(key, None)
        print(json.dumps({"event": event.event, "data": data}, default=str)[:2000])


if __name__ == "__main__":
    asyncio.run(main())
