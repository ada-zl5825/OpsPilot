from __future__ import annotations

from collections.abc import Sequence

from opspilot.domain.incidents import Diagnosis, IncidentRun, IncidentScenario
from opspilot.eval.classify import classify_failures
from opspilot.eval.constants import COMPOSITE_WEIGHTS
from opspilot.eval.metrics import collect_raw_metrics
from opspilot.eval.models import HardFail, RawMetrics, ScoreCard
from opspilot.eval.safety import detect_hard_fails
from opspilot.investigation.outcome import StopReason
from opspilot.telemetry.events import AgentEvent


def composite_score(raw: RawMetrics, hard_fails: Sequence[HardFail]) -> float:
    if hard_fails:
        return 0.0
    score = (
        COMPOSITE_WEIGHTS["root_cause"] * raw.root_cause_score
        + COMPOSITE_WEIGHTS["evidence"] * raw.evidence_coverage
        + COMPOSITE_WEIGHTS["tool_efficiency"] * raw.tool_efficiency
        + COMPOSITE_WEIGHTS["recovery"] * raw.recovery_success
        + COMPOSITE_WEIGHTS["failure_recovery"] * raw.failure_recovery
        + COMPOSITE_WEIGHTS["escalation"] * raw.escalation_accuracy
    )
    return round(max(0.0, min(1.0, score)), 4)


def score_trajectory(
    events: Sequence[AgentEvent],
    scenario: IncidentScenario,
    *,
    variant_id: str,
    condition: str,
    split: str,
    model: str,
    prompt_version: str,
    tool_catalog_version: str,
    diagnosis: Diagnosis | None = None,
    run: IncidentRun | None = None,
    prompt: str | None = None,
    stop_reason: StopReason | None = None,
) -> ScoreCard:
    hard_fails = detect_hard_fails(events, scenario, run=run, prompt=prompt)
    raw = collect_raw_metrics(
        events,
        scenario,
        diagnosis=diagnosis,
        run=run,
        hard_fails=hard_fails,
    )
    classes = classify_failures(raw, hard_fails, stop_reason=stop_reason)
    return ScoreCard(
        variant_id=variant_id,
        scenario_id=scenario.scenario_id,
        condition=condition,
        split=split,
        difficulty=scenario.difficulty,
        model=model,
        prompt_version=prompt_version,
        tool_catalog_version=tool_catalog_version,
        raw=raw,
        hard_fails=[item.value for item in hard_fails],
        failure_classes=[item.value for item in classes],
        composite=composite_score(raw, hard_fails),
        diagnosis_root_cause=diagnosis.root_cause if diagnosis is not None else None,
    )
