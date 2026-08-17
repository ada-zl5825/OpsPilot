from typing import Literal, TypedDict


class ToolContract(TypedDict):
    name: str
    server: Literal["observability", "deployments", "runbooks", "remediation"]
    permission: Literal["read", "propose", "mutate"]
    timeout_seconds: int
    max_result_bytes: int
    agent_visible: bool


TOOL_CATALOG: list[ToolContract] = [
    {
        "name": "query_service_metrics",
        "server": "observability",
        "permission": "read",
        "timeout_seconds": 15,
        "max_result_bytes": 65536,
        "agent_visible": True,
    },
    {
        "name": "query_service_logs",
        "server": "observability",
        "permission": "read",
        "timeout_seconds": 15,
        "max_result_bytes": 65536,
        "agent_visible": True,
    },
    {
        "name": "get_trace_summary",
        "server": "observability",
        "permission": "read",
        "timeout_seconds": 15,
        "max_result_bytes": 65536,
        "agent_visible": True,
    },
    {
        "name": "get_recent_deployments",
        "server": "deployments",
        "permission": "read",
        "timeout_seconds": 15,
        "max_result_bytes": 32768,
        "agent_visible": True,
    },
    {
        "name": "compare_deployments",
        "server": "deployments",
        "permission": "read",
        "timeout_seconds": 15,
        "max_result_bytes": 32768,
        "agent_visible": True,
    },
    {
        "name": "get_ci_failure_summary",
        "server": "deployments",
        "permission": "read",
        "timeout_seconds": 20,
        "max_result_bytes": 32768,
        "agent_visible": True,
    },
    {
        "name": "search_runbooks",
        "server": "runbooks",
        "permission": "read",
        "timeout_seconds": 10,
        "max_result_bytes": 32768,
        "agent_visible": True,
    },
    {
        "name": "get_remediation_capabilities",
        "server": "remediation",
        "permission": "read",
        "timeout_seconds": 5,
        "max_result_bytes": 8192,
        "agent_visible": True,
    },
    {
        "name": "dry_run_remediation",
        "server": "remediation",
        "permission": "read",
        "timeout_seconds": 15,
        "max_result_bytes": 16384,
        "agent_visible": True,
    },
    {
        "name": "get_resource_snapshot",
        "server": "remediation",
        "permission": "read",
        "timeout_seconds": 10,
        "max_result_bytes": 32768,
        "agent_visible": True,
    },
    {
        "name": "verify_recovery",
        "server": "remediation",
        "permission": "read",
        "timeout_seconds": 20,
        "max_result_bytes": 16384,
        "agent_visible": True,
    },
    {
        "name": "propose_rollback_deployment",
        "server": "remediation",
        "permission": "propose",
        "timeout_seconds": 10,
        "max_result_bytes": 16384,
        "agent_visible": True,
    },
    {
        "name": "propose_restart_workload",
        "server": "remediation",
        "permission": "propose",
        "timeout_seconds": 10,
        "max_result_bytes": 16384,
        "agent_visible": True,
    },
    {
        "name": "propose_scale_workload",
        "server": "remediation",
        "permission": "propose",
        "timeout_seconds": 10,
        "max_result_bytes": 16384,
        "agent_visible": True,
    },
    {
        "name": "propose_update_config",
        "server": "remediation",
        "permission": "propose",
        "timeout_seconds": 10,
        "max_result_bytes": 16384,
        "agent_visible": True,
    },
    {
        "name": "execute_approved_proposal",
        "server": "remediation",
        "permission": "mutate",
        "timeout_seconds": 60,
        "max_result_bytes": 32768,
        "agent_visible": False,
    },
    {
        "name": "rollback_execution",
        "server": "remediation",
        "permission": "mutate",
        "timeout_seconds": 60,
        "max_result_bytes": 32768,
        "agent_visible": False,
    },
]


def agent_visible_tools() -> list[ToolContract]:
    return [tool for tool in TOOL_CATALOG if tool["agent_visible"]]


def mutate_tools() -> list[ToolContract]:
    return [tool for tool in TOOL_CATALOG if tool["permission"] == "mutate"]
