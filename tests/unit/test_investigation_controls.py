from uuid import uuid4

from tests.unit.investigation_fakes import event, failed_tool_pair, successful_tool_pair

from opspilot.domain.incidents import TokenUsage
from opspilot.investigation.budget import BudgetViolation, ToolBudget, evaluate_budget
from opspilot.investigation.evidence import collect_evidence, tool_result_succeeded
from opspilot.investigation.progress import evaluate_progress
from opspilot.telemetry.events import AgentEventType


def test_failed_tool_result_is_not_success() -> None:
    failed = failed_tool_pair("query_service_metrics", {"service": "checkout"}, sequence=1)[1]
    assert tool_result_succeeded(failed) is False
    evidence = collect_evidence(uuid4(), [failed])
    assert evidence == []


def test_successful_tool_result_becomes_evidence() -> None:
    run_id = uuid4()
    events = successful_tool_pair(
        "query_service_logs",
        {"service": "checkout"},
        "error rate increased",
        sequence=1,
    )
    evidence = collect_evidence(run_id, events)
    assert len(evidence) == 1
    assert evidence[0].source_tool == "query_service_logs"
    assert evidence[0].source_system == "loki"
    assert evidence[0].run_id == run_id


def test_failed_calls_do_not_count_as_query_repeats() -> None:
    params = {"service": "checkout", "metric": "error_rate"}
    events = []
    sequence = 1
    for _ in range(4):
        events.extend(failed_tool_pair("query_service_metrics", params, sequence=sequence))
        sequence += 2
    events.extend(
        successful_tool_pair("query_service_metrics", params, "once", sequence=sequence)
    )
    state = evaluate_budget(
        events,
        ToolBudget(max_repeats_per_query=2, max_repeats_per_tool=3, max_tool_calls=16),
        steps_used=1,
        token_usage=TokenUsage(total_tokens=10),
    )
    assert BudgetViolation.MAX_REPEATS_PER_QUERY not in state.violations
    assert BudgetViolation.MAX_REPEATS_PER_TOOL not in state.violations
    assert state.tool_calls == 5


def test_distinct_service_queries_are_not_repeats() -> None:
    events = []
    sequence = 1
    for service in ("gateway", "checkout", "payment", "inventory", "notification"):
        events.extend(
            successful_tool_pair(
                "query_service_metrics",
                {"service": service, "metric": "latency_p95"},
                f"{service} latency",
                sequence=sequence,
            )
        )
        sequence += 2
    state = evaluate_budget(
        events,
        ToolBudget(max_repeats_per_query=2, max_repeats_per_tool=3, max_tool_calls=16),
        steps_used=1,
        token_usage=TokenUsage(total_tokens=10),
    )
    assert not state.exceeded
    assert state.tool_calls == 5


def test_duplicate_query_hits_repeat_limit() -> None:
    params = {"service": "checkout", "metric": "error_rate"}
    events = []
    sequence = 1
    for _ in range(3):
        events.extend(
            successful_tool_pair("query_service_metrics", params, "same", sequence=sequence)
        )
        sequence += 2
    state = evaluate_budget(
        events,
        ToolBudget(max_repeats_per_query=2, max_repeats_per_tool=5),
        steps_used=1,
        token_usage=TokenUsage(total_tokens=10),
    )
    assert state.exceeded
    assert BudgetViolation.MAX_REPEATS_PER_QUERY in state.violations


def test_no_progress_after_repeated_failures() -> None:
    events = []
    sequence = 1
    for _ in range(3):
        events.extend(
            failed_tool_pair("query_service_metrics", {"service": "checkout"}, sequence=sequence)
        )
        sequence += 2
    progress = evaluate_progress(events, [], ToolBudget(max_no_progress_steps=3))
    assert progress.no_progress is True
    assert collect_evidence(uuid4(), events) == []


def test_identical_digest_does_not_count_as_progress() -> None:
    events = []
    sequence = 1
    for index in range(4):
        events.extend(
            successful_tool_pair(
                "query_service_metrics",
                {"service": "checkout", "call": index},
                "identical observation",
                sequence=sequence,
            )
        )
        sequence += 2
    evidence = collect_evidence(uuid4(), events)
    progress = evaluate_progress(events, evidence, ToolBudget(max_no_progress_steps=3))
    assert progress.no_progress is True


def test_llm_end_without_tool_is_not_successful_evidence() -> None:
    events = [
        event(
            AgentEventType.LLM_END,
            {"analysis": "I guess the database is down"},
            sequence=1,
        )
    ]
    assert collect_evidence(uuid4(), events) == []
