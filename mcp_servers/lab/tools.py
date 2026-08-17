from __future__ import annotations

from typing import Any


def structured_error(
    tool: str,
    *,
    error_type: str,
    message: str,
    retryable: bool,
    suggested_fix: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "safe_params": params or {},
        "error_type": error_type,
        "message": message,
        "retryable": retryable,
        "suggested_fix": suggested_fix,
    }


def lab_status() -> dict[str, Any]:
    return {
        "ok": True,
        "tool": "lab_status",
        "status": "ok",
        "phase": "0",
        "verification_code": "OP-P0-LAB",
    }


def lab_echo(message: str) -> dict[str, Any]:
    if len(message) > 200:
        return structured_error(
            "lab_echo",
            error_type="validation",
            message="message exceeds maxLength 200",
            retryable=True,
            suggested_fix="shorten message to <= 200 characters",
            params={"message_length": len(message)},
        )
    return {"ok": True, "tool": "lab_echo", "echo": message}


def lab_mutate_probe(target: str) -> dict[str, Any]:
    return structured_error(
        "lab_mutate_probe",
        error_type="approval_required",
        message="mutate probe is control-plane gated and never executes a write",
        retryable=False,
        suggested_fix="create a RemediationProposal and wait for human approval",
        params={"target": target},
    )
