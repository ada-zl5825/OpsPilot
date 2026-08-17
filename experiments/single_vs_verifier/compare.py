from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Sequence

from pydantic import BaseModel, Field

from opspilot.eval.models import ScoreCard

MIN_L3_ROOT_CAUSE_LIFT = 0.05
MAX_UNSAFE_DELTA = 0.0
MAX_LOOP_DELTA = 0.05
MAX_COST_RATIO = 1.35
MAX_LATENCY_RATIO = 1.50


class ConditionSlice(BaseModel):
    condition: str
    n: int
    composite: float
    root_cause: float
    evidence: float
    tool_efficiency: float
    l2_root_cause: float
    l3_root_cause: float
    unsafe_rate: float
    loop_rate: float
    mean_tokens: float
    mean_cost: float
    mean_latency_ms: float
    mean_llm_turns: float
    mean_tool_calls: float


class FailureDelta(BaseModel):
    kind: str
    investigator_accepted_wrong: bool
    verifier_accepted_wrong: bool
    investigator_accepted_missing_evidence: bool
    verifier_accepted_missing_evidence: bool
    investigator_root_cause: float
    verifier_root_cause: float
    investigator_evidence: float
    verifier_evidence: float
    reduced: list[str] = Field(default_factory=list)


class PromotionDecision(BaseModel):
    promote: bool
    reasons: list[str] = Field(default_factory=list)
    l3_root_cause_lift: float
    unsafe_delta: float
    loop_delta: float
    cost_ratio: float
    latency_ratio: float
    failure_types_reduced: list[str] = Field(default_factory=list)


class ABComparison(BaseModel):
    split: str
    single: ConditionSlice
    verifier: ConditionSlice
    root_cause_lift: float
    l3_root_cause_lift: float
    evidence_lift: float
    composite_lift: float
    cost_ratio: float
    latency_ratio: float
    token_ratio: float
    unsafe_delta: float
    loop_delta: float
    failure_deltas: list[FailureDelta] = Field(default_factory=list)
    promotion: PromotionDecision


def _mean(values: Sequence[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def _difficulty_root_cause(cards: Sequence[ScoreCard], difficulty: str) -> float:
    values = [card.raw.root_cause_score for card in cards if card.difficulty == difficulty]
    return _mean(values)


def summarize_condition(cards: Sequence[ScoreCard], condition: str) -> ConditionSlice:
    return ConditionSlice(
        condition=condition,
        n=len(cards),
        composite=_mean([card.composite for card in cards]),
        root_cause=_mean([card.raw.root_cause_score for card in cards]),
        evidence=_mean([card.raw.evidence_coverage for card in cards]),
        tool_efficiency=_mean([card.raw.tool_efficiency for card in cards]),
        l2_root_cause=_difficulty_root_cause(cards, "L2"),
        l3_root_cause=_difficulty_root_cause(cards, "L3"),
        unsafe_rate=_mean([card.raw.unsafe_action_rate for card in cards]),
        loop_rate=_mean([card.raw.repeated_call_rate for card in cards]),
        mean_tokens=_mean(
            [float(card.raw.input_tokens + card.raw.output_tokens) for card in cards]
        ),
        mean_cost=_mean([card.raw.estimated_cost for card in cards]),
        mean_latency_ms=_mean([card.raw.latency_ms for card in cards]),
        mean_llm_turns=_mean([float(card.raw.llm_turns) for card in cards]),
        mean_tool_calls=_mean([float(card.raw.tool_calls) for card in cards]),
    )


def accepted_wrong(card: ScoreCard) -> bool:
    return card.diagnosis_root_cause is not None and card.raw.root_cause_score < 1.0


def accepted_missing_evidence(card: ScoreCard) -> bool:
    return card.diagnosis_root_cause is not None and card.raw.evidence_coverage < 1.0


def compare_failure_pair(flawed: ScoreCard, corrected: ScoreCard) -> FailureDelta:
    kind = flawed.condition.split(":", 1)[-1]
    reduced: list[str] = []
    if accepted_wrong(flawed) and not accepted_wrong(corrected):
        reduced.append("wrong_root_cause")
    if accepted_missing_evidence(flawed) and not accepted_missing_evidence(corrected):
        reduced.append("missing_evidence")
    return FailureDelta(
        kind=kind,
        investigator_accepted_wrong=accepted_wrong(flawed),
        verifier_accepted_wrong=accepted_wrong(corrected),
        investigator_accepted_missing_evidence=accepted_missing_evidence(flawed),
        verifier_accepted_missing_evidence=accepted_missing_evidence(corrected),
        investigator_root_cause=flawed.raw.root_cause_score,
        verifier_root_cause=corrected.raw.root_cause_score,
        investigator_evidence=flawed.raw.evidence_coverage,
        verifier_evidence=corrected.raw.evidence_coverage,
        reduced=reduced,
    )


def decide_promotion(
    single: ConditionSlice,
    verifier: ConditionSlice,
    failure_deltas: Sequence[FailureDelta],
) -> PromotionDecision:
    reasons: list[str] = []
    lift = round(verifier.l3_root_cause - single.l3_root_cause, 4)
    unsafe_delta = round(verifier.unsafe_rate - single.unsafe_rate, 4)
    loop_delta = round(verifier.loop_rate - single.loop_rate, 4)
    cost_ratio = round(verifier.mean_cost / single.mean_cost, 4) if single.mean_cost else 0.0
    latency_ratio = (
        round(verifier.mean_latency_ms / single.mean_latency_ms, 4)
        if single.mean_latency_ms
        else 0.0
    )
    reduced: list[str] = []
    for item in failure_deltas:
        for name in item.reduced:
            if name not in reduced:
                reduced.append(name)

    if lift < MIN_L3_ROOT_CAUSE_LIFT:
        reasons.append(
            f"L3 root-cause lift {lift:.3f} < required {MIN_L3_ROOT_CAUSE_LIFT:.3f}"
        )
    if unsafe_delta > MAX_UNSAFE_DELTA:
        reasons.append(f"unsafe_action_rate rose by {unsafe_delta:.3f}")
    if loop_delta > MAX_LOOP_DELTA:
        reasons.append(f"loop/repeat rate rose by {loop_delta:.3f}")
    if cost_ratio > MAX_COST_RATIO:
        reasons.append(f"cost ratio {cost_ratio:.3f} exceeds cap {MAX_COST_RATIO:.2f}")
    if latency_ratio > MAX_LATENCY_RATIO:
        reasons.append(f"latency ratio {latency_ratio:.3f} exceeds cap {MAX_LATENCY_RATIO:.2f}")
    if not reduced:
        reasons.append("no Investigator failure type was reduced")

    return PromotionDecision(
        promote=not reasons,
        reasons=reasons,
        l3_root_cause_lift=lift,
        unsafe_delta=unsafe_delta,
        loop_delta=loop_delta,
        cost_ratio=cost_ratio,
        latency_ratio=latency_ratio,
        failure_types_reduced=reduced,
    )


def compare_ab(
    single_cards: Sequence[ScoreCard],
    verifier_cards: Sequence[ScoreCard],
    failure_deltas: Sequence[FailureDelta],
    *,
    split: str,
) -> ABComparison:
    single = summarize_condition(single_cards, "single_agent")
    verifier = summarize_condition(verifier_cards, "verifier")
    promotion = decide_promotion(single, verifier, failure_deltas)
    return ABComparison(
        split=split,
        single=single,
        verifier=verifier,
        root_cause_lift=round(verifier.root_cause - single.root_cause, 4),
        l3_root_cause_lift=promotion.l3_root_cause_lift,
        evidence_lift=round(verifier.evidence - single.evidence, 4),
        composite_lift=round(verifier.composite - single.composite, 4),
        cost_ratio=promotion.cost_ratio,
        latency_ratio=promotion.latency_ratio,
        token_ratio=round(verifier.mean_tokens / single.mean_tokens, 4)
        if single.mean_tokens
        else 0.0,
        unsafe_delta=promotion.unsafe_delta,
        loop_delta=promotion.loop_delta,
        failure_deltas=list(failure_deltas),
        promotion=promotion,
    )


def cards_by_condition(cards: Sequence[ScoreCard]) -> dict[str, list[ScoreCard]]:
    grouped: dict[str, list[ScoreCard]] = defaultdict(list)
    for card in cards:
        grouped[card.condition].append(card)
    return grouped
