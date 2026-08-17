from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Condition(StrEnum):
    DETERMINISTIC = "deterministic"
    SINGLE_AGENT = "single_agent"
    VERIFIER = "verifier"


class Split(StrEnum):
    EVAL = "eval"
    HOLDOUT = "holdout"


class HardFail(StrEnum):
    UNSAFE_ACTION = "unsafe_action"
    UNAPPROVED_WRITE = "unapproved_write"
    CROSS_NAMESPACE_WRITE = "cross_namespace_write"
    SHELL_INJECTION = "shell_injection_success"
    DIGEST_MISMATCH_EXECUTED = "digest_mismatch_executed"
    SECRET_LEAK = "secret_leak"
    RESOLVED_WITHOUT_VERIFY = "resolved_without_recovery_verify"
    PROMPT_INJECTION_POLICY = "prompt_injection_changed_policy"
    GROUND_TRUTH_LEAK = "ground_truth_leak"


class FailureClass(StrEnum):
    WRONG_ROOT_CAUSE = "wrong_root_cause"
    MISSING_EVIDENCE = "missing_evidence"
    REDUNDANT_TOOLS = "redundant_tools"
    LOOP = "loop"
    TOOL_FAILURE_UNRECOVERED = "tool_failure_unrecovered"
    UNSAFE_ACTION = "unsafe_action"
    UNAPPROVED_WRITE = "unapproved_write"
    SECRET_LEAK = "secret_leak"
    FALSE_RESOLVED = "resolved_without_verify"
    INVALID_DIAGNOSIS = "invalid_diagnosis"
    INCORRECT_ESCALATION = "incorrect_escalation"
    BUDGET_EXHAUSTED = "budget_exhausted"


class RawMetrics(BaseModel):
    root_cause_exact: float = 0.0
    root_cause_score: float = 0.0
    root_cause_localization: float = 0.0
    root_cause_identification: float = 0.0
    root_cause_reason: float = 0.0
    evidence_coverage: float = 0.0
    evidence_checkpoint_coverage: float = 0.0
    tool_precision: float = 0.0
    tool_recall: float = 0.0
    tool_efficiency: float = 0.0
    redundant_tool_rate: float = 0.0
    repeated_call_rate: float = 0.0
    failure_recovery: float = 0.0
    recovery_success: float = 0.0
    escalation_accuracy: float = 0.0
    unsafe_action_rate: float = 0.0
    unapproved_write_count: int = 0
    llm_turns: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost: float = 0.0


class ScoreCard(BaseModel):
    variant_id: str
    scenario_id: str
    condition: str
    split: str
    difficulty: str
    model: str
    prompt_version: str
    tool_catalog_version: str
    raw: RawMetrics
    hard_fails: list[str] = Field(default_factory=list)
    failure_classes: list[str] = Field(default_factory=list)
    composite: float
    diagnosis_root_cause: str | None = None


class AggregateMetrics(BaseModel):
    count: int
    mean: float
    median: float
    stddev: float
    min: float
    max: float


class ConditionSummary(BaseModel):
    condition: str
    split: str
    n: int
    composite: AggregateMetrics
    root_cause_score: AggregateMetrics
    evidence_coverage: AggregateMetrics
    tool_efficiency: AggregateMetrics
    recovery_success: AggregateMetrics
    failure_recovery: AggregateMetrics
    escalation_accuracy: AggregateMetrics
    unsafe_action_rate: float
    unapproved_write_count: int
    hard_fail_count: int
    failure_class_counts: dict[str, int] = Field(default_factory=dict)
    by_difficulty: dict[str, float] = Field(default_factory=dict)


class BenchmarkReport(BaseModel):
    benchmark_version: str
    prompt_version: str
    tool_catalog_version: str
    split: str
    conditions: list[str]
    cards: list[ScoreCard] = Field(default_factory=list)
    summaries: list[ConditionSummary] = Field(default_factory=list)
    gate_passed: bool | None = None
    gate_failures: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
