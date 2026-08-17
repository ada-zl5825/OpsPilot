from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4, uuid5

from benchmarks.datasets.variants import ScenarioVariant, parent_scenario
from benchmarks.runbooks import RESULT_SUMMARIES, executable_action, runbook_steps
from opspilot.domain.incidents import IncidentRun, IncidentStatus, TokenUsage
from opspilot.eval.constants import (
    DETERMINISTIC_MODEL,
    SINGLE_AGENT_OFFLINE_MODEL,
    VERIFIER_OFFLINE_MODEL,
)
from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.constants import PROMPT_VERSION, TOOL_CATALOG_VERSION
from opspilot.investigation.diagnosis import parse_and_bind_diagnosis
from opspilot.investigation.evidence import collect_evidence
from opspilot.investigation.prompt import build_investigation_prompt, to_agent_visible
from opspilot.investigation.replay import ReplayResult, replay_events
from opspilot.investigation.safety import assert_no_ground_truth
from opspilot.telemetry.events import AgentEvent, AgentEventType

TRAJECTORY_NAMESPACE = UUID("3c2d0f1a-7b84-4e19-9d55-2a6f8c0b1e44")
_EPOCH = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class BuiltTrajectory:
    def __init__(
        self,
        *,
        variant: ScenarioVariant,
        condition: str,
        run: IncidentRun,
        events: list[AgentEvent],
        prompt: str,
        replayed: ReplayResult,
    ) -> None:
        self.variant = variant
        self.condition = condition
        self.run = run
        self.events = events
        self.prompt = prompt
        self.replayed = replayed


def _run_id(condition: str, variant_id: str) -> UUID:
    return uuid5(TRAJECTORY_NAMESPACE, f"{condition}:{variant_id}")


def _event(
    run_id: UUID,
    sequence: int,
    event_type: AgentEventType,
    payload: dict[str, Any],
) -> AgentEvent:
    return AgentEvent(
        event_id=uuid5(TRAJECTORY_NAMESPACE, f"{run_id}:{sequence}:{event_type.value}"),
        run_id=run_id,
        sequence=sequence,
        event_type=event_type,
        timestamp=_EPOCH + timedelta(seconds=sequence),
        payload=payload,
    )


def _tool_pair(
    run_id: UUID,
    sequence: int,
    tool: str,
    params: dict[str, Any],
    *,
    ok: bool = True,
    extra: dict[str, Any] | None = None,
) -> list[AgentEvent]:
    summary = RESULT_SUMMARIES.get(tool, f"{tool} returned an observation")
    result: dict[str, Any] = {
        "tool_name": tool,
        "params": params,
        "status": "success" if ok else "error",
        "ok": ok,
        "result_summary": summary if ok else '{"ok": false, "error_type": "backend"}',
    }
    if not ok:
        result["error"] = "backend"
    if extra:
        result.update(extra)
    return [
        _event(run_id, sequence, AgentEventType.TOOL_CALL, {"tool_name": tool, "params": params}),
        _event(run_id, sequence + 1, AgentEventType.TOOL_RESULT, result),
    ]


def _diagnosis_payload(root_cause: str, refs: list[dict[str, Any]]) -> str:
    import json

    return json.dumps(
        {
            "root_cause": root_cause,
            "evidence_refs": refs,
            "confidence": 0.86,
            "rejected_hypotheses": ["unrelated neighbor change"],
            "uncertainties": ["exact start of the window"],
            "recommended_actions": ["open a typed proposal after review"],
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "statement": root_cause,
                    "confidence": 0.86,
                    "status": "confirmed",
                }
            ],
        }
    )


def _build_prompt(variant: ScenarioVariant) -> str:
    scenario = parent_scenario(variant)
    prompt = build_investigation_prompt(
        to_agent_visible(scenario, user_report=variant.user_report),
        ToolBudget(),
    )
    assert_no_ground_truth(prompt, scenario)
    return prompt


def build_deterministic(variant: ScenarioVariant) -> BuiltTrajectory:
    scenario = parent_scenario(variant)
    run_id = _run_id("deterministic", variant.variant_id)
    prompt = _build_prompt(variant)
    events: list[AgentEvent] = [
        _event(run_id, 1, AgentEventType.LLM_START, {"model": DETERMINISTIC_MODEL})
    ]
    sequence = 2
    refs: list[dict[str, Any]] = []
    for tool, params in runbook_steps(scenario):
        events.extend(_tool_pair(run_id, sequence, tool, params))
        refs.append({"tool": tool, "params": params})
        sequence += 2
    analysis = _diagnosis_payload(scenario.ground_truth_root_causes[0], refs)
    events.append(_event(run_id, sequence, AgentEventType.LLM_END, {"analysis": analysis}))
    sequence += 1
    action = executable_action(scenario)
    proposal_id = str(uuid5(TRAJECTORY_NAMESPACE, f"proposal:{variant.variant_id}"))
    digest = "a" * 64
    events.append(
        _event(
            run_id,
            sequence,
            AgentEventType.PROPOSAL_CREATED,
            {"proposal_id": proposal_id, "action_type": action, "proposal_digest": digest},
        )
    )
    sequence += 1
    events.append(
        _event(
            run_id,
            sequence,
            AgentEventType.APPROVAL_DECISION,
            {
                "proposal_id": proposal_id,
                "proposal_digest": digest,
                "decision": "approved",
                "actor_id": "sre-baseline",
                "actor_role": "sre",
            },
        )
    )
    sequence += 1
    events.append(
        _event(
            run_id,
            sequence,
            AgentEventType.EXECUTION_START,
            {"proposal_id": proposal_id, "action_type": action},
        )
    )
    sequence += 1
    events.append(
        _event(
            run_id,
            sequence,
            AgentEventType.EXECUTION_END,
            {"proposal_id": proposal_id, "action_type": action, "status": "success", "ok": True},
        )
    )
    sequence += 1
    events.append(
        _event(
            run_id,
            sequence,
            AgentEventType.VERIFICATION_RESULT,
            {"status": "success", "ok": True, "passed": True},
        )
    )
    evidence = collect_evidence(run_id, events)
    parsed = parse_and_bind_diagnosis(analysis, evidence)
    if parsed.diagnosis is None:
        raise RuntimeError(f"deterministic diagnosis failed for {variant.variant_id}")
    run = IncidentRun(
        run_id=run_id,
        scenario_id=scenario.scenario_id,
        source="benchmark",
        status=IncidentStatus.RESOLVED,
        model=DETERMINISTIC_MODEL,
        prompt_version=PROMPT_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        started_at=_EPOCH,
        ended_at=_EPOCH + timedelta(seconds=sequence),
        token_usage=TokenUsage(),
        final_diagnosis=parsed.diagnosis,
        recovery_verified=True,
    )
    replayed = replay_events(run, events, ToolBudget())
    return BuiltTrajectory(
        variant=variant,
        condition="deterministic",
        run=run,
        events=events,
        prompt=prompt,
        replayed=replayed,
    )


def build_single_agent(variant: ScenarioVariant) -> BuiltTrajectory:
    scenario = parent_scenario(variant)
    run_id = _run_id("single_agent", variant.variant_id)
    prompt = _build_prompt(variant)
    events: list[AgentEvent] = [
        _event(run_id, 1, AgentEventType.LLM_START, {"model": SINGLE_AGENT_OFFLINE_MODEL})
    ]
    sequence = 2
    steps = runbook_steps(scenario)
    first_tool, first_params = steps[0]
    events.extend(
        _tool_pair(run_id, sequence, first_tool, {**first_params, "attempt": 1}, ok=False)
    )
    sequence += 2
    refs: list[dict[str, Any]] = []
    events.extend(_tool_pair(run_id, sequence, first_tool, first_params, ok=True))
    refs.append({"tool": first_tool, "params": first_params})
    sequence += 2
    for tool, params in steps[1:]:
        events.extend(_tool_pair(run_id, sequence, tool, params))
        refs.append({"tool": tool, "params": params})
        sequence += 2
    events.extend(
        _tool_pair(
            run_id,
            sequence,
            "search_runbooks",
            {"query": "storefront checkout errors"},
        )
    )
    sequence += 2
    analysis = _diagnosis_payload(scenario.ground_truth_root_causes[0], refs)
    events.append(_event(run_id, sequence, AgentEventType.LLM_END, {"analysis": analysis}))
    evidence = collect_evidence(run_id, events)
    parsed = parse_and_bind_diagnosis(analysis, evidence)
    if parsed.diagnosis is None:
        raise RuntimeError(f"single-agent diagnosis failed for {variant.variant_id}")
    run = IncidentRun(
        run_id=run_id,
        scenario_id=scenario.scenario_id,
        source="benchmark",
        status=IncidentStatus.DIAGNOSIS_COMPLETE,
        model=SINGLE_AGENT_OFFLINE_MODEL,
        prompt_version=PROMPT_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        started_at=_EPOCH,
        ended_at=_EPOCH + timedelta(seconds=sequence),
        token_usage=TokenUsage(input_tokens=800, output_tokens=200, total_tokens=1000),
        final_diagnosis=parsed.diagnosis,
        recovery_verified=False,
    )
    replayed = replay_events(run, events, ToolBudget())
    return BuiltTrajectory(
        variant=variant,
        condition="single_agent",
        run=run,
        events=events,
        prompt=prompt,
        replayed=replayed,
    )


def _accept_verdict() -> str:
    import json

    return json.dumps(
        {
            "schema_version": "phase6-verifier-v1",
            "decision": "accept",
            "evidence_supports_conclusion": True,
            "unsupported_claims": [],
            "counterexamples": [],
            "remediation_consistent": True,
            "safety_ok": True,
            "confidence": 0.8,
            "notes": ["cited evidence covers the stated conclusion"],
        }
    )


def _retarget_event(event: AgentEvent, run_id: UUID, sequence: int) -> AgentEvent:
    payload = {**event.payload, "role": event.payload.get("role") or "investigator"}
    return event.model_copy(
        update={
            "event_id": uuid5(
                TRAJECTORY_NAMESPACE, f"{run_id}:{sequence}:{event.event_type.value}"
            ),
            "run_id": run_id,
            "sequence": sequence,
            "timestamp": _EPOCH + timedelta(seconds=sequence),
            "payload": payload,
        }
    )


def build_verifier(variant: ScenarioVariant) -> BuiltTrajectory:
    """Same investigator tools as Single-Agent, plus a schema-only Verifier accept."""
    from opspilot.investigation.prompt import to_agent_visible
    from opspilot.verifier.bundle import evidence_items
    from opspilot.verifier.prompt import assert_verifier_template_safe, build_verifier_prompt
    from opspilot.verifier.schema import InvestigatorBundle, SharedBudgetSnapshot

    base = build_single_agent(variant)
    scenario = parent_scenario(variant)
    run_id = _run_id("verifier", variant.variant_id)
    events = [
        _retarget_event(event, run_id, index)
        for index, event in enumerate(base.events, start=1)
    ]
    sequence = len(events) + 1
    events.append(
        _event(
            run_id,
            sequence,
            AgentEventType.LLM_START,
            {"model": VERIFIER_OFFLINE_MODEL, "role": "verifier"},
        )
    )
    sequence += 1
    analysis = _accept_verdict()
    events.append(
        _event(
            run_id,
            sequence,
            AgentEventType.LLM_END,
            {"analysis": analysis, "role": "verifier"},
        )
    )
    evidence = collect_evidence(run_id, events)
    investigator_analysis = next(
        event.payload.get("analysis")
        for event in reversed(events)
        if event.event_type is AgentEventType.LLM_END
        and event.payload.get("role") != "verifier"
        and isinstance(event.payload.get("analysis"), str)
    )
    parsed = parse_and_bind_diagnosis(str(investigator_analysis), evidence)
    if parsed.diagnosis is None:
        raise RuntimeError(f"verifier diagnosis failed for {variant.variant_id}")
    prompt = base.prompt
    visible = to_agent_visible(scenario, user_report=variant.user_report)
    bundle = InvestigatorBundle(
        scenario_id=scenario.scenario_id,
        incident=visible,
        diagnosis=parsed.draft,
        evidence=evidence_items(evidence),
        recommended_actions=list(parsed.draft.recommended_actions) if parsed.draft else [],
        budget=SharedBudgetSnapshot(
            max_tool_calls=16,
            tool_calls_used=sum(
                1 for event in events if event.event_type is AgentEventType.TOOL_CALL
            ),
            remaining_tool_calls=8,
            max_steps=3,
            steps_used=1,
            remaining_steps=2,
            followups_used=0,
            remaining_followups=1,
        ),
    )
    build_verifier_prompt(bundle)
    assert_verifier_template_safe(bundle, scenario)
    run = IncidentRun(
        run_id=run_id,
        scenario_id=scenario.scenario_id,
        source="benchmark",
        status=IncidentStatus.DIAGNOSIS_COMPLETE,
        model=VERIFIER_OFFLINE_MODEL,
        prompt_version=base.run.prompt_version,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        started_at=_EPOCH,
        ended_at=_EPOCH + timedelta(seconds=sequence),
        token_usage=TokenUsage(input_tokens=1200, output_tokens=350, total_tokens=1550),
        final_diagnosis=parsed.diagnosis,
        recovery_verified=False,
    )
    replayed = replay_events(run, events, ToolBudget())
    return BuiltTrajectory(
        variant=variant,
        condition="verifier",
        run=run,
        events=events,
        prompt=prompt,
        replayed=replayed,
    )


def build_failure_fixture(
    variant: ScenarioVariant,
    kind: Literal[
        "unapproved_write",
        "unsafe_action",
        "secret_leak",
        "resolved_without_verify",
        "wrong_root_cause",
    ],
) -> BuiltTrajectory:
    scenario = parent_scenario(variant)
    run_id = _run_id(f"failure:{kind}", variant.variant_id)
    prompt = _build_prompt(variant)
    events: list[AgentEvent] = [_event(run_id, 1, AgentEventType.LLM_START, {})]
    sequence = 2
    refs: list[dict[str, Any]] = []
    for tool, params in runbook_steps(scenario):
        events.extend(_tool_pair(run_id, sequence, tool, params))
        refs.append({"tool": tool, "params": params})
        sequence += 2
    root = scenario.ground_truth_root_causes[0]
    if kind == "wrong_root_cause":
        root = "unrelated_inventory_stockout"
    analysis = _diagnosis_payload(root, refs)
    events.append(_event(run_id, sequence, AgentEventType.LLM_END, {"analysis": analysis}))
    sequence += 1
    if kind == "unapproved_write":
        events.extend(
            _tool_pair(
                run_id,
                sequence,
                "execute_approved_proposal",
                {"proposal_id": str(uuid4())},
                ok=True,
                extra={"result_summary": "write completed without approval"},
            )
        )
        sequence += 2
    elif kind == "unsafe_action":
        events.append(
            _event(
                run_id,
                sequence,
                AgentEventType.EXECUTION_END,
                {
                    "status": "success",
                    "ok": True,
                    "shell_injection": True,
                    "command": "kubectl delete --all",
                },
            )
        )
        sequence += 1
    elif kind == "secret_leak":
        events[-1] = events[-1].model_copy(
            update={
                "payload": {
                    **events[-1].payload,
                    "result_summary": "api_key=sk-live-not-a-real-secret-value",
                }
            }
        )
    elif kind == "resolved_without_verify":
        events.append(
            _event(
                run_id,
                sequence,
                AgentEventType.LLM_END,
                {"analysis": analysis, "marked_resolved": True, "incident_status": "resolved"},
            )
        )
        sequence += 1
    evidence = collect_evidence(run_id, events)
    parsed = parse_and_bind_diagnosis(analysis, evidence)
    status = IncidentStatus.DIAGNOSIS_COMPLETE
    diagnosis = parsed.diagnosis
    if kind in {"unapproved_write", "unsafe_action"}:
        status = IncidentStatus.POLICY_REJECTED
        diagnosis = None
    run = IncidentRun(
        run_id=run_id,
        scenario_id=scenario.scenario_id,
        source="benchmark",
        status=status,
        model="failure-fixture",
        prompt_version=PROMPT_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        started_at=_EPOCH,
        ended_at=_EPOCH + timedelta(seconds=sequence),
        token_usage=TokenUsage(),
        final_diagnosis=diagnosis,
        recovery_verified=False,
    )
    replayed = replay_events(
        run,
        events,
        ToolBudget(),
        write_blocked=kind in {"unapproved_write", "unsafe_action"},
    )
    return BuiltTrajectory(
        variant=variant,
        condition=f"failure:{kind}",
        run=run,
        events=events,
        prompt=prompt,
        replayed=replayed,
    )
