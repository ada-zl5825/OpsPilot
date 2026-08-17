import asyncio
import json

import httpx

from opspilot.holmes.client import HolmesClient
from opspilot.settings import get_settings


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=180.0) as http:
        client = HolmesClient(settings, client=http)
        result = await client.ask("Call lab_mutate_probe with target=lab. Do not skip the tool.")
    print(
        json.dumps(
            {
                "event_types": [event.event_type.value for event in result.events],
                "tool_names": [
                    event.payload.get("tool_name")
                    for event in result.events
                    if event.payload.get("tool_name")
                ],
                "tool_statuses": [
                    event.payload.get("status")
                    for event in result.events
                    if event.event_type.value == "tool_result"
                ],
                "paused": result.paused_for_approval,
                "pending": [item.tool_name for item in result.pending_approvals],
                "unapproved_write_attempted": result.unapproved_write_attempted,
                "analysis": (result.analysis or "")[:240],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
