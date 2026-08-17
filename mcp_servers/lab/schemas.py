from __future__ import annotations

from typing import Any, Literal, TypedDict


class LabToolSchema(TypedDict):
    name: str
    permission: Literal["read", "mutate"]
    timeout_seconds: int
    max_result_bytes: int
    agent_visible: bool
    requires_approval: bool
    input_schema: dict[str, Any]


LAB_TOOL_SCHEMAS: list[LabToolSchema] = [
    {
        "name": "lab_status",
        "permission": "read",
        "timeout_seconds": 5,
        "max_result_bytes": 4096,
        "agent_visible": True,
        "requires_approval": False,
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "lab_echo",
        "permission": "read",
        "timeout_seconds": 5,
        "max_result_bytes": 4096,
        "agent_visible": True,
        "requires_approval": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200,
                }
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lab_mutate_probe",
        "permission": "mutate",
        "timeout_seconds": 5,
        "max_result_bytes": 4096,
        "agent_visible": True,
        "requires_approval": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 64,
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        },
    },
]


INCOMPATIBLE_AZURE_EXAMPLE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
    },
}
