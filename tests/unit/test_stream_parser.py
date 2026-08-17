from datetime import UTC, datetime
from uuid import uuid4

from opspilot.holmes.stream_parser import HolmesStreamParser
from opspilot.telemetry.events import AgentEventType


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
