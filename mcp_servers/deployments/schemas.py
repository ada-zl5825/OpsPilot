from __future__ import annotations

from pydantic import Field

from mcp_servers.common.schemas import ServiceName, ServiceOrAll, StrictModel, azure_input_schema


class RecentDeploymentsInput(StrictModel):
    service: ServiceOrAll = "all"
    start: str = Field(min_length=10, max_length=40)
    end: str = Field(min_length=10, max_length=40)
    limit: int = Field(default=20, ge=1, le=50)


class CompareDeploymentsInput(StrictModel):
    service: ServiceName
    from_version: str = Field(min_length=1, max_length=32)
    to_version: str = Field(min_length=1, max_length=32)
    start: str = Field(min_length=10, max_length=40)
    end: str = Field(min_length=10, max_length=40)


class CiFailureInput(StrictModel):
    service: ServiceName
    start: str = Field(min_length=10, max_length=40)
    end: str = Field(min_length=10, max_length=40)
    workflow: str = Field(default="", max_length=64)
    limit: int = Field(default=10, ge=1, le=30)


DEPLOYMENT_INPUT_SCHEMAS = {
    "get_recent_deployments": azure_input_schema(RecentDeploymentsInput),
    "compare_deployments": azure_input_schema(CompareDeploymentsInput),
    "get_ci_failure_summary": azure_input_schema(CiFailureInput),
}
