from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mcp_servers.common.null_args import drop_null_arguments

SERVICE_NAMES = ("gateway", "checkout", "payment", "inventory", "notification")
ServiceName = Literal["gateway", "checkout", "payment", "inventory", "notification"]
ServiceOrAll = Literal["all", "gateway", "checkout", "payment", "inventory", "notification"]

_UNSUPPORTED = frozenset({"oneOf", "anyOf", "allOf", "not", "$ref"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_json_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return drop_null_arguments(data)
        return data


def azure_input_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("$schema", None)
    schema.pop("title", None)
    schema.pop("$defs", None)
    if schema.get("type") == "object":
        schema.setdefault("additionalProperties", False)
        schema.setdefault("properties", {})
    _assert_azure_safe(schema, "$")
    return schema


def _assert_azure_safe(node: Any, path: str) -> None:
    if not isinstance(node, dict):
        return
    for key in node:
        if key in _UNSUPPORTED:
            raise ValueError(f"Azure-incompatible keyword {key} at {path}")
    properties = node.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            _assert_azure_safe(child, f"{path}.properties.{name}")
    items = node.get("items")
    if isinstance(items, dict):
        _assert_azure_safe(items, f"{path}.items")


class TimeRangeFields(StrictModel):
    start: str = Field(min_length=10, max_length=40)
    end: str = Field(min_length=10, max_length=40)
