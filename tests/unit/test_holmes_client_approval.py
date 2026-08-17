from pathlib import Path

import httpx
import pytest

from opspilot.holmes.client import HolmesClient, ToolDecision
from opspilot.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "holmes_sse"


def _transport(sse_name: str) -> httpx.MockTransport:
    body = (FIXTURES / sse_name).read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/api/chat":
            payload = json_loads(request.content)
            assert "tool_decisions" not in payload or all(
                not item.get("approved") for item in payload.get("tool_decisions", [])
            )
            return httpx.Response(
                200,
                text=body,
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def json_loads(content: bytes) -> dict[str, object]:
    import json

    return json.loads(content.decode("utf-8"))


@pytest.mark.asyncio
async def test_ask_pauses_on_approval_and_does_not_auto_approve() -> None:
    settings = Settings(holmes_base_url="http://holmes.test")
    async with httpx.AsyncClient(
        transport=_transport("approval_required.sse"),
        base_url=settings.holmes_base_url,
    ) as http:
        client = HolmesClient(settings, client=http)
        result = await client.ask("please mutate")
    assert result.paused_for_approval is True
    assert result.pending_approvals[0].tool_name == "lab_mutate_probe"
    assert result.unapproved_write_attempted is False


@pytest.mark.asyncio
async def test_client_rejects_approved_decisions() -> None:
    settings = Settings(holmes_base_url="http://holmes.test")
    async with httpx.AsyncClient(
        transport=_transport("approval_required.sse"),
        base_url=settings.holmes_base_url,
    ) as http:
        client = HolmesClient(settings, client=http)
        with pytest.raises(PermissionError, match="control plane"):
            await client.ask(
                "continue",
                tool_decisions=[ToolDecision(tool_call_id="call_mut_1", approved=True)],
            )


def test_auto_approve_constructor_rejected() -> None:
    with pytest.raises(ValueError, match="auto_approve"):
        HolmesClient(Settings(), auto_approve=True)
