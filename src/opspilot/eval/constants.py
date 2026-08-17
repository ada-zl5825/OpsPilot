from __future__ import annotations

BENCHMARK_VERSION = "v1"
DETERMINISTIC_MODEL = "deterministic-runbook-v1"
SINGLE_AGENT_OFFLINE_MODEL = "single-agent-offline-v1"
VERIFIER_OFFLINE_MODEL = "single-agent-plus-verifier-offline-v1"

COMPOSITE_WEIGHTS: dict[str, float] = {
    "root_cause": 0.30,
    "evidence": 0.20,
    "tool_efficiency": 0.15,
    "recovery": 0.15,
    "failure_recovery": 0.10,
    "escalation": 0.10,
}

TOOL_CATEGORY: dict[str, str] = {
    "query_service_metrics": "metrics",
    "query_service_logs": "logs",
    "get_trace_summary": "traces",
    "get_recent_deployments": "deployments",
    "compare_deployments": "deployments",
    "get_ci_failure_summary": "deployments",
    "search_runbooks": "runbooks",
    "lab_status": "lab",
    "lab_echo": "lab",
    "propose_rollback_deployment": "remediation",
    "propose_restart_workload": "remediation",
    "propose_scale_workload": "remediation",
    "propose_update_config": "remediation",
    "dry_run_remediation": "remediation",
    "verify_recovery": "remediation",
}

AGENT_WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "execute_approved_proposal",
        "rollback_execution",
        "lab_mutate_probe",
    }
)

EXECUTABLE_REMEDIATION: dict[str, str] = {
    "S01": "rollback_deployment",
    "S02": "restart_workload",
    "S03": "rollback_deployment",
    "S04": "rollback_deployment",
}
