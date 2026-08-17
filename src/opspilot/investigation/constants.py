from __future__ import annotations

PROMPT_VERSION = "phase3-single-agent-v1"
TOOL_CATALOG_VERSION = "phase2-readonly-v1"

PHASE2_READ_TOOLS: tuple[str, ...] = (
    "query_service_metrics",
    "query_service_logs",
    "get_trace_summary",
    "get_recent_deployments",
    "compare_deployments",
    "get_ci_failure_summary",
    "search_runbooks",
)

MUTATE_TOOLS: frozenset[str] = frozenset(
    {
        "execute_approved_proposal",
        "rollback_execution",
        "lab_mutate_probe",
    }
)

TOOL_SOURCE_SYSTEM: dict[str, str] = {
    "query_service_metrics": "prometheus",
    "query_service_logs": "loki",
    "get_trace_summary": "tempo",
    "get_recent_deployments": "deployments",
    "compare_deployments": "deployments",
    "get_ci_failure_summary": "deployments",
    "search_runbooks": "runbooks",
    "lab_status": "lab",
    "lab_echo": "lab",
}

LAB_SERVICES: tuple[str, ...] = (
    "gateway",
    "checkout",
    "payment",
    "inventory",
    "notification",
)
