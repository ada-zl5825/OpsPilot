from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AzureSchemaIssue(BaseModel):
    tool_name: str
    reason: str
    path: str


class AzureSchemaReport(BaseModel):
    compatible: bool
    issues: list[AzureSchemaIssue] = Field(default_factory=list)


class CatalogCompatibilityReport(BaseModel):
    compatible_tools: list[str] = Field(default_factory=list)
    isolated_incompatible_tools: list[str] = Field(default_factory=list)
    issues: list[AzureSchemaIssue] = Field(default_factory=list)

    @property
    def catalog_usable(self) -> bool:
        return bool(self.compatible_tools)


_UNSUPPORTED_KEYS = frozenset({"oneOf", "anyOf", "allOf", "not", "$ref"})


def validate_tool_schema_for_azure(tool_name: str, schema: dict[str, Any]) -> AzureSchemaReport:
    """Conservative Azure OpenAI strict-tool-schema checks used as a Phase 0 gate."""
    issues: list[AzureSchemaIssue] = []
    _walk(tool_name, schema, "$", issues)
    return AzureSchemaReport(compatible=not issues, issues=issues)


def evaluate_catalog(schemas: dict[str, dict[str, Any]]) -> CatalogCompatibilityReport:
    """A single bad tool is isolated; remaining tools stay loadable."""
    compatible: list[str] = []
    isolated: list[str] = []
    issues: list[AzureSchemaIssue] = []
    for name, schema in schemas.items():
        report = validate_tool_schema_for_azure(name, schema)
        if report.compatible:
            compatible.append(name)
        else:
            isolated.append(name)
            issues.extend(report.issues)
    return CatalogCompatibilityReport(
        compatible_tools=compatible,
        isolated_incompatible_tools=isolated,
        issues=issues,
    )


def _walk(
    tool_name: str,
    node: Any,
    path: str,
    issues: list[AzureSchemaIssue],
) -> None:
    if not isinstance(node, dict):
        return
    for key in node:
        if key in _UNSUPPORTED_KEYS:
            issues.append(
                AzureSchemaIssue(
                    tool_name=tool_name,
                    reason=f"Azure-incompatible keyword: {key}",
                    path=f"{path}.{key}",
                )
            )
    if node.get("type") == "object" and "properties" not in node:
        issues.append(
            AzureSchemaIssue(
                tool_name=tool_name,
                reason="object type must declare properties",
                path=path,
            )
        )
    properties = node.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            _walk(tool_name, child, f"{path}.properties.{name}", issues)
    items = node.get("items")
    if isinstance(items, dict):
        _walk(tool_name, items, f"{path}.items", issues)
