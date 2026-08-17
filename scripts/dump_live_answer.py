import asyncio
import json

import httpx

from opspilot.holmes.client import HolmesClient
from opspilot.settings import get_settings


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=180.0) as http:
        client = HolmesClient(settings, client=http)
        result = await client.ask(
            "You must call the tool named lab_status. Do not answer until you have called it."
        )
    print(
        json.dumps(
            {
                "event_types": [event.event_type.value for event in result.events],
                "tool_names": [
                    event.payload.get("tool_name")
                    for event in result.events
                    if event.payload.get("tool_name")
                ],
                "analysis": (result.analysis or "")[:400],
                "paused": result.paused_for_approval,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
