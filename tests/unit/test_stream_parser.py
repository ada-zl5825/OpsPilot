from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from opspilot.holmes.sse import parse_sse_text
from opspilot.holmes.stream_parser import HolmesStreamParser
from opspilot.telemetry.events import AgentEventType

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "holmes_sse"


def test_parser_accepts_normalized_events() -> None:
    run_id = uuid4()
    raw = [
        {
            "event_id": uuid4(),
            "run_id": run_id,
            "sequence": 1,
            "event_type": "tool_call",
            "timestamp": datetime.now(UTC),
            "payload": {"tool": "query_service_metrics"},
        }
    ]
    events = HolmesStreamParser().parse(raw)
    assert len(events) == 1
    assert events[0].event_type is AgentEventType.TOOL_CALL


def test_parser_maps_holmes_readonly_stream() -> None:
    text = (FIXTURES / "readonly_then_answer.sse").read_text(encoding="utf-8")
    raw = parse_sse_text(text)
    parser = HolmesStreamParser()
    events = parser.parse_holmes_events(raw, run_id=uuid4())
    types = [event.event_type for event in events]
    assert AgentEventType.LLM_START in types
    assert AgentEventType.TOOL_CALL in types
    assert AgentEventType.TOOL_RESULT in types
    assert AgentEventType.LLM_END in types
    tool_result = next(event for event in events if event.event_type is AgentEventType.TOOL_RESULT)
    assert tool_result.payload.get("ok") is True
    assert parser.extract_final_answer(raw) == "Lab is healthy. verification_code=OP-P0-LAB"
    usage = parser.extract_token_usage(raw)
    assert usage.total_tokens == 240


def test_parser_maps_approval_required() -> None:
    text = (FIXTURES / "approval_required.sse").read_text(encoding="utf-8")
    events = HolmesStreamParser().parse_holmes_events(parse_sse_text(text), run_id=uuid4())
    approval = next(
        event for event in events if event.event_type is AgentEventType.APPROVAL_REQUIRED
    )
    assert approval.payload["pending_approvals"][0]["tool_name"] == "lab_mutate_probe"
