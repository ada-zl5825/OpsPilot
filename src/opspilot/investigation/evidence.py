from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC
from typing import Any
from uuid import UUID, uuid5

from opspilot.domain.evidence import Evidence
from opspilot.investigation.constants import TOOL_SOURCE_SYSTEM
from opspilot.telemetry.events import AgentEvent, AgentEventType

_FAILURE_STATUSES = frozenset(
    {"error", "failed", "timeout", "denied", "approval_required", "failure"}
)
EVIDENCE_NAMESPACE = UUID("6f1c2a70-3e5d-4b9a-9c11-0f8d2e4a7b31")


def tool_name_of(event: AgentEvent) -> str:
    return str(event.payload.get("tool_name") or event.payload.get("tool") or "")


def params_of(event: AgentEvent) -> dict[str, Any]:
    params = event.payload.get("params")
    return dict(params) if isinstance(params, dict) else {}


def query_fingerprint(event: AgentEvent) -> str:
    return fingerprint_for(tool_name_of(event), params_of(event))


def fingerprint_for(tool_name: str, params: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"tool": tool_name, "params": params},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def content_digest(summary: str) -> str:
    return hashlib.sha256(summary.encode("utf-8")).hexdigest()[:16]


def evidence_id_for(run_id: UUID, fingerprint: str) -> UUID:
    return uuid5(EVIDENCE_NAMESPACE, f"{run_id}:{fingerprint}")


def tool_result_succeeded(event: AgentEvent) -> bool:
    if event.event_type is not AgentEventType.TOOL_RESULT:
        return False
    payload = event.payload
    if payload.get("error"):
        return False
    status = str(payload.get("status") or "").lower()
    if status in _FAILURE_STATUSES:
        return False
    ok = payload.get("ok")
    if ok is False:
        return False
    summary = str(payload.get("result_summary") or "")
    compact = summary.replace(" ", "").lower()
    if '"ok":false' in compact:
        return False
    if status and status != "success":
        return False
    return bool(ok is True or status == "success")


def collect_evidence(run_id: UUID, events: Sequence[AgentEvent]) -> list[Evidence]:
    collected: list[Evidence] = []
    seen: set[UUID] = set()
    for event in events:
        if event.event_type is not AgentEventType.TOOL_RESULT:
            continue
        if not tool_result_succeeded(event):
            continue
        tool_name = tool_name_of(event)
        if not tool_name:
            continue
        fingerprint = query_fingerprint(event)
        evidence_id = evidence_id_for(run_id, fingerprint)
        if evidence_id in seen:
            continue
        summary = str(event.payload.get("result_summary") or tool_name)
        artifact = event.payload.get("artifact_ref")
        collected.append(
            Evidence(
                evidence_id=evidence_id,
                run_id=run_id,
                source_tool=tool_name,
                source_system=TOOL_SOURCE_SYSTEM.get(tool_name, "unknown"),
                captured_at=event.timestamp
                if event.timestamp.tzinfo
                else event.timestamp.replace(tzinfo=UTC),
                query_fingerprint=fingerprint,
                content_digest=content_digest(summary),
                summary=summary[:500],
                raw_artifact_ref=str(artifact) if artifact else None,
            )
        )
        seen.add(evidence_id)
    return collected


def format_evidence_line(evidence: Evidence) -> str:
    preview = evidence.summary[:160]
    return (
        f"{evidence.evidence_id} tool={evidence.source_tool} "
        f"digest={evidence.content_digest} {preview}"
    )
