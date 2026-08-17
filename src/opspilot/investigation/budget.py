from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from opspilot.domain.incidents import TokenUsage
from opspilot.investigation.evidence import query_fingerprint, tool_name_of, tool_result_succeeded
from opspilot.telemetry.cost import estimate_cost
from opspilot.telemetry.events import AgentEvent, AgentEventType


class BudgetViolation(StrEnum):
    MAX_STEPS = "max_steps"
    MAX_TOOL_CALLS = "max_tool_calls"
    MAX_REPEATS_PER_TOOL = "max_repeats_per_tool"
    MAX_REPEATS_PER_QUERY = "max_repeats_per_query"
    MAX_TOKENS = "max_tokens"
    MAX_COST = "max_cost"


class ToolBudget(BaseModel):
    max_steps: int = Field(default=3, ge=1, le=8)
    max_tool_calls: int = Field(default=16, ge=1, le=64)
    max_repeats_per_tool: int = Field(
        default=3,
        ge=1,
        le=16,
        description=(
            "Max successful repeats of the same tool+query fingerprint. "
            "Distinct services or metrics do not share this counter."
        ),
    )
    max_repeats_per_query: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Max successful repeats of an identical tool+params query.",
    )
    max_no_progress_steps: int = Field(default=3, ge=1, le=16)
    max_total_tokens: int = Field(default=128000, ge=1)
    max_cost_usd: Decimal = Field(default=Decimal("1.50"))


class BudgetState(BaseModel):
    tool_calls: int = 0
    steps: int = 0
    repeats_by_tool: dict[str, int] = Field(default_factory=dict)
    repeats_by_fingerprint: dict[str, int] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: Decimal = Decimal("0")
    violations: list[BudgetViolation] = Field(default_factory=list)

    @property
    def exceeded(self) -> bool:
        return bool(self.violations)


def evaluate_budget(
    events: Sequence[AgentEvent],
    budget: ToolBudget,
    *,
    steps_used: int,
    token_usage: TokenUsage | None = None,
) -> BudgetState:
    tool_names = [
        tool_name_of(event)
        for event in events
        if event.event_type is AgentEventType.TOOL_CALL and tool_name_of(event)
    ]
    successful = [event for event in events if tool_result_succeeded(event)]
    fingerprints = [query_fingerprint(event) for event in successful]
    by_tool = Counter(tool_name_of(event) for event in successful if tool_name_of(event))
    by_fp = Counter(fingerprints)
    usage = token_usage or TokenUsage()
    cost = estimate_cost(usage)
    violations: list[BudgetViolation] = []
    if steps_used > budget.max_steps:
        violations.append(BudgetViolation.MAX_STEPS)
    if len(tool_names) > budget.max_tool_calls:
        violations.append(BudgetViolation.MAX_TOOL_CALLS)
    # Repeat limits are fingerprint-based and ignore failed calls. Cross-service
    # fan-out of the same tool is not a repeat.
    if any(count > budget.max_repeats_per_tool for count in by_fp.values()):
        violations.append(BudgetViolation.MAX_REPEATS_PER_TOOL)
    if any(count > budget.max_repeats_per_query for count in by_fp.values()):
        violations.append(BudgetViolation.MAX_REPEATS_PER_QUERY)
    if usage.total_tokens > budget.max_total_tokens:
        violations.append(BudgetViolation.MAX_TOKENS)
    if cost > budget.max_cost_usd:
        violations.append(BudgetViolation.MAX_COST)
    return BudgetState(
        tool_calls=len(tool_names),
        steps=steps_used,
        repeats_by_tool=dict(by_tool),
        repeats_by_fingerprint=dict(by_fp),
        token_usage=usage,
        estimated_cost=cost,
        violations=violations,
    )


def remaining_tool_calls(state: BudgetState, budget: ToolBudget) -> int:
    return max(0, budget.max_tool_calls - state.tool_calls)
