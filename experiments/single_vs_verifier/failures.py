from __future__ import annotations

import json
from typing import Literal

from benchmarks.datasets.variants import ScenarioVariant, load_variants, parent_scenario
from benchmarks.runbooks import FAMILY_STEPS
from benchmarks.trajectories import (
    BuiltTrajectory,
    _build_prompt,
    _diagnosis_payload,
    _event,
    _run_id,
    _tool_pair,
)

from opspilot.domain.incidents import IncidentRun, IncidentStatus, TokenUsage
from opspilot.eval.constants import SINGLE_AGENT_OFFLINE_MODEL, VERIFIER_OFFLINE_MODEL
from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.constants import TOOL_CATALOG_VERSION
from opspilot.investigation.diagnosis import parse_and_bind_diagnosis
from opspilot.investigation.evidence import collect_evidence
from opspilot.investigation.replay import replay_events
from opspilot.telemetry.events import AgentEvent, AgentEventType

FailureKind = Literal[
    "wrong_root_cause",
    "missing_evidence",
    "unsupported_conclusion",
    "safety_mismatch",
    "followup_budget_blocked",
]

FAILURE_KINDS: tuple[FailureKind, ...] = (
    "wrong_root_cause",
    "missing_evidence",
    "unsupported_conclusion",
    "safety_mismatch",
    "followup_budget_blocked",
)

_KIND_SCENARIO: dict[FailureKind, str] = {
    "wrong_root_cause": "S04",
    "missing_evidence": "S01",
    "unsupported_conclusion": "S02",
    "safety_mismatch": "S03",
    "followup_budget_blocked": "S01",
}

_WRONG_CAUSE: dict[FailureKind, str] = {
    "wrong_root_cause": "recent_storefront_release",
    "unsupported_conclusion": "unrelated_inventory_stockout",
}


def variant_for(kind: FailureKind) -> ScenarioVariant:
    scenario_id = _KIND_SCENARIO[kind]
    return next(item for item in load_variants(split="eval") if item.scenario_id == scenario_id)


def _verdict(
    decision: str,
    *,
    supports: bool,
    followup_tool: str | None = None,
    safety_ok: bool = True,
    notes: list[str] | None = None,
) -> str:
    payload: dict[str, object] = {
        "schema_version": "phase6-verifier-v1",
        "decision": decision,
        "evidence_supports_conclusion": supports,
        "unsupported_claims": [] if supports else ["stated conclusion is not backed by evidence"],
        "counterexamples": [],
        "remediation_consistent": safety_ok,
        "safety_ok": safety_ok,
        "confidence": 0.55,
        "notes": notes or [],
    }
    if decision == "request_followup" and followup_tool:
        payload["followup"] = {
            "reason": "one more read-only observation is required",
            "missing_checks": ["another telemetry source"],
            "suggested_tools": [followup_tool],
            "suggested_params": [{"service": "checkout"}],
        }
    return json.dumps(payload)


def _append_verifier(run_id, sequence: int, analysis: str) -> tuple[list[AgentEvent], int]:
    events = [
        _event(
            run_id,
            sequence,
            AgentEventType.LLM_START,
            {"model": VERIFIER_OFFLINE_MODEL, "role": "verifier"},
        ),
        _event(
            run_id,
            sequence + 1,
            AgentEventType.LLM_END,
            {"analysis": analysis, "role": "verifier"},
        ),
    ]
    return events, sequence + 1


def _finish(
    *,
    variant: ScenarioVariant,
    condition: str,
    kind: FailureKind,
    events: list[AgentEvent],
    analysis: str,
    status: IncidentStatus,
    model: str,
    tokens: TokenUsage,
) -> BuiltTrajectory:
    scenario = parent_scenario(variant)
    run_id = events[0].run_id
    evidence = collect_evidence(run_id, events)
    parsed = parse_and_bind_diagnosis(analysis, evidence)
    diagnosis = parsed.diagnosis if status is IncidentStatus.DIAGNOSIS_COMPLETE else None
    if status is IncidentStatus.DIAGNOSIS_COMPLETE and diagnosis is None:
        raise RuntimeError(f"{condition}:{kind} missing bound diagnosis")
    run = IncidentRun(
        run_id=run_id,
        scenario_id=scenario.scenario_id,
        source="benchmark",
        status=status,
        model=model,
        prompt_version="phase3-single-agent-v1",
        tool_catalog_version=TOOL_CATALOG_VERSION,
        started_at=events[0].timestamp,
        ended_at=events[-1].timestamp,
        token_usage=tokens,
        final_diagnosis=diagnosis,
        recovery_verified=False,
    )
    replayed = replay_events(run, events, ToolBudget())
    return BuiltTrajectory(
        variant=variant,
        condition=f"{condition}:{kind}",
        run=run,
        events=events,
        prompt=_build_prompt(variant),
        replayed=replayed,
    )


def _investigator_core(
    kind: FailureKind,
    variant: ScenarioVariant,
    run_id,
) -> tuple[list[AgentEvent], list[dict[str, object]], str, int]:
    scenario = parent_scenario(variant)
    events: list[AgentEvent] = [
        _event(run_id, 1, AgentEventType.LLM_START, {"model": SINGLE_AGENT_OFFLINE_MODEL})
    ]
    sequence = 2
    refs: list[dict[str, object]] = []
    if kind == "wrong_root_cause":
        steps = FAMILY_STEPS["S03"][:2]
        root = _WRONG_CAUSE[kind]
    elif kind == "missing_evidence":
        steps = FAMILY_STEPS["S01"][:1]
        root = scenario.ground_truth_root_causes[0]
    elif kind == "unsupported_conclusion":
        steps = FAMILY_STEPS["S02"]
        root = _WRONG_CAUSE[kind]
    elif kind == "safety_mismatch":
        steps = FAMILY_STEPS["S03"]
        root = scenario.ground_truth_root_causes[0]
    else:
        steps = FAMILY_STEPS["S01"][:1]
        root = scenario.ground_truth_root_causes[0]
    for tool, params in steps:
        events.extend(_tool_pair(run_id, sequence, tool, params))
        refs.append({"tool": tool, "params": params})
        sequence += 2
    extra_actions = (
        ["execute_approved_proposal"] if kind == "safety_mismatch" else ["open a typed proposal"]
    )
    payload = json.loads(_diagnosis_payload(root, refs))
    payload["recommended_actions"] = extra_actions
    analysis = json.dumps(payload)
    events.append(_event(run_id, sequence, AgentEventType.LLM_END, {"analysis": analysis}))
    return events, refs, analysis, sequence


def build_investigator_flawed(kind: FailureKind) -> BuiltTrajectory:
    variant = variant_for(kind)
    run_id = _run_id(f"investigator_flawed:{kind}", variant.variant_id)
    events, _refs, analysis, _sequence = _investigator_core(kind, variant, run_id)
    return _finish(
        variant=variant,
        condition="investigator_flawed",
        kind=kind,
        events=events,
        analysis=analysis,
        status=IncidentStatus.DIAGNOSIS_COMPLETE,
        model=SINGLE_AGENT_OFFLINE_MODEL,
        tokens=TokenUsage(input_tokens=700, output_tokens=180, total_tokens=880),
    )


def build_verifier_on_flaw(kind: FailureKind) -> BuiltTrajectory:
    variant = variant_for(kind)
    scenario = parent_scenario(variant)
    run_id = _run_id(f"verifier_corrected:{kind}", variant.variant_id)
    events, refs, analysis, sequence = _investigator_core(kind, variant, run_id)
    sequence += 1

    if kind == "wrong_root_cause":
        extra, sequence = _append_verifier(
            run_id,
            sequence,
            _verdict("request_followup", supports=False, followup_tool="get_trace_summary"),
        )
        events.extend(extra)
        sequence += 1
        follow_steps = FAMILY_STEPS["S04"]
        follow_refs: list[dict[str, object]] = []
        events.append(
            _event(run_id, sequence, AgentEventType.LLM_START, {"model": VERIFIER_OFFLINE_MODEL})
        )
        sequence += 1
        for tool, params in follow_steps:
            events.extend(_tool_pair(run_id, sequence, tool, params))
            follow_refs.append({"tool": tool, "params": params})
            sequence += 2
        analysis = _diagnosis_payload(scenario.ground_truth_root_causes[0], follow_refs)
        events.append(_event(run_id, sequence, AgentEventType.LLM_END, {"analysis": analysis}))
        sequence += 1
        extra, sequence = _append_verifier(
            run_id, sequence, _verdict("accept", supports=True, notes=["follow-up filled the gap"])
        )
        events.extend(extra)
        status = IncidentStatus.DIAGNOSIS_COMPLETE
    elif kind == "missing_evidence":
        extra, sequence = _append_verifier(
            run_id,
            sequence,
            _verdict("request_followup", supports=True, followup_tool="query_service_logs"),
        )
        events.extend(extra)
        sequence += 1
        tool, params = FAMILY_STEPS["S01"][1]
        events.append(
            _event(run_id, sequence, AgentEventType.LLM_START, {"model": VERIFIER_OFFLINE_MODEL})
        )
        sequence += 1
        events.extend(_tool_pair(run_id, sequence, tool, params))
        refs.append({"tool": tool, "params": params})
        sequence += 2
        analysis = _diagnosis_payload(scenario.ground_truth_root_causes[0], refs)
        events.append(_event(run_id, sequence, AgentEventType.LLM_END, {"analysis": analysis}))
        sequence += 1
        extra, sequence = _append_verifier(run_id, sequence, _verdict("accept", supports=True))
        events.extend(extra)
        status = IncidentStatus.DIAGNOSIS_COMPLETE
    elif kind == "unsupported_conclusion":
        extra, sequence = _append_verifier(
            run_id,
            sequence,
            _verdict("reject", supports=False, notes=["bundle contradicts the stated conclusion"]),
        )
        events.extend(extra)
        status = IncidentStatus.EVIDENCE_INSUFFICIENT
    elif kind == "safety_mismatch":
        extra, sequence = _append_verifier(
            run_id,
            sequence,
            _verdict("reject", supports=True, safety_ok=False, notes=["write action recommended"]),
        )
        events.extend(extra)
        status = IncidentStatus.EVIDENCE_INSUFFICIENT
    else:
        extra, sequence = _append_verifier(
            run_id,
            sequence,
            _verdict("request_followup", supports=False, followup_tool="query_service_logs"),
        )
        events.extend(extra)
        status = IncidentStatus.EVIDENCE_INSUFFICIENT

    return _finish(
        variant=variant,
        condition="verifier_corrected",
        kind=kind,
        events=events,
        analysis=analysis,
        status=status,
        model=VERIFIER_OFFLINE_MODEL,
        tokens=TokenUsage(input_tokens=1100, output_tokens=320, total_tokens=1420),
    )


def all_failure_pairs() -> list[tuple[BuiltTrajectory, BuiltTrajectory]]:
    return [
        (build_investigator_flawed(kind), build_verifier_on_flaw(kind)) for kind in FAILURE_KINDS
    ]
