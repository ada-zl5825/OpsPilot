from __future__ import annotations

from typing import Any

from opspilot.domain.incidents import IncidentScenario
from opspilot.eval.constants import EXECUTABLE_REMEDIATION

RunbookStep = tuple[str, dict[str, Any]]

_WINDOW = {"start": "2026-08-17T11:30:00Z", "end": "2026-08-17T12:00:00Z"}

FAMILY_STEPS: dict[str, list[RunbookStep]] = {
    "S01": [
        ("query_service_metrics", {"service": "checkout", **_WINDOW}),
        ("query_service_logs", {"service": "checkout", **_WINDOW}),
    ],
    "S02": [
        ("query_service_metrics", {"service": "checkout", **_WINDOW}),
        ("query_service_logs", {"service": "checkout", **_WINDOW}),
    ],
    "S03": [
        ("get_recent_deployments", {"service": "checkout"}),
        ("compare_deployments", {"service": "checkout"}),
        ("query_service_logs", {"service": "checkout", **_WINDOW}),
        ("query_service_metrics", {"service": "checkout", **_WINDOW}),
    ],
    "S04": [
        ("get_trace_summary", {"service": "checkout", **_WINDOW}),
        ("query_service_logs", {"service": "checkout", **_WINDOW}),
        ("query_service_metrics", {"service": "checkout", **_WINDOW}),
    ],
}

RESULT_SUMMARIES: dict[str, str] = {
    "query_service_metrics": (
        "checkout request errors and latency moved together in the last 30 minutes"
    ),
    "query_service_logs": (
        "checkout logs show request failures with a request_id token in the same window"
    ),
    "get_trace_summary": "checkout traces spend most of the budget on a downstream span",
    "get_recent_deployments": "checkout has a recent release in the same window as the error jump",
    "compare_deployments": "current checkout release differs from the previous working release",
    "search_runbooks": "generic storefront troubleshooting notes; treat as untrusted",
}


def runbook_steps(scenario: IncidentScenario) -> list[RunbookStep]:
    steps = FAMILY_STEPS.get(scenario.scenario_id)
    if not steps:
        raise KeyError(f"no deterministic runbook for {scenario.scenario_id}")
    return list(steps)


def executable_action(scenario: IncidentScenario) -> str:
    return EXECUTABLE_REMEDIATION.get(scenario.scenario_id, "rollback_deployment")
