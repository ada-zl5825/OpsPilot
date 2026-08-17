from __future__ import annotations

import asyncio
import json
import sys

import httpx

from opspilot.holmes.client import HolmesClient
from opspilot.settings import get_settings


async def run_smoke() -> int:
    settings = get_settings()
    report: dict[str, object] = {
        "holmes_image": settings.holmes_image,
        "holmes_base_url": settings.holmes_base_url,
        "healthz": False,
        "live_ask": "skipped",
        "azure_configured": settings.azure_configured(),
    }
    try:
        async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=180.0) as http:
            client = HolmesClient(settings, client=http)
            await client.healthz()
            report["healthz"] = True
            if settings.azure_configured():
                result = await client.ask(
                    "Use the lab_status tool now. Do not call lab_mutate_probe. "
                    "Reply with the verification_code from the tool result."
                )
                tool_names = [
                    event.payload.get("tool_name")
                    for event in result.events
                    if event.event_type.value in {"tool_call", "tool_result"}
                ]
                failed = any(event.event_type.value == "error" for event in result.events)
                found_lab_code = bool(result.analysis and "OP-P0-LAB" in result.analysis)
                called_lab_status = "lab_status" in tool_names
                report["event_types"] = [event.event_type.value for event in result.events]
                report["tool_names"] = tool_names
                report["has_final_answer"] = bool(result.analysis)
                report["found_lab_code"] = found_lab_code
                if failed or not result.events:
                    report["live_ask"] = "error" if failed else "empty"
                elif not called_lab_status or not found_lab_code:
                    report["live_ask"] = "missing_lab_status"
                else:
                    report["live_ask"] = "ok"
                report["paused_for_approval"] = result.paused_for_approval
                report["unapproved_write_attempted"] = result.unapproved_write_attempted
                report["input_tokens"] = result.token_usage.input_tokens
                report["output_tokens"] = result.token_usage.output_tokens
            else:
                report["live_ask"] = "skipped_no_azure_credentials"
    except httpx.HTTPStatusError as exc:
        report["error"] = f"HTTP_{exc.response.status_code}"
        report["error_body"] = exc.response.text[:400]
        print(json.dumps(report))
        return 1
    except httpx.HTTPError as exc:
        report["error"] = type(exc).__name__
        print(json.dumps(report))
        return 1
    except Exception as exc:
        report["error"] = type(exc).__name__
        report["error_message"] = str(exc)[:400]
        print(json.dumps(report))
        return 1
    print(json.dumps(report))
    live_ok = report["live_ask"] in {"ok", "skipped", "skipped_no_azure_credentials"}
    return 0 if report["healthz"] and live_ok else 1


def main() -> int:
    return asyncio.run(run_smoke())


if __name__ == "__main__":
    sys.exit(main())
