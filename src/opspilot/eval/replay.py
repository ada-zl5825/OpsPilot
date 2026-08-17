from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from opspilot.domain.incidents import IncidentRun, IncidentScenario
from opspilot.eval.models import ScoreCard
from opspilot.eval.scorer import score_trajectory
from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.constants import PROMPT_VERSION, TOOL_CATALOG_VERSION
from opspilot.investigation.replay import ReplayResult, replay_events, replay_store
from opspilot.investigation.store import InvestigationStore
from opspilot.lab.scenarios import scenario_by_id
from opspilot.telemetry.events import AgentEvent


def score_replay(
    result: ReplayResult,
    scenario: IncidentScenario,
    *,
    variant_id: str | None = None,
    condition: str = "single_agent",
    split: str = "eval",
    model: str | None = None,
    prompt: str | None = None,
) -> ScoreCard:
    run = result.run
    return score_trajectory(
        result.events,
        scenario,
        variant_id=variant_id or (run.scenario_id or str(run.run_id)),
        condition=condition,
        split=split,
        model=model or run.model,
        prompt_version=run.prompt_version or PROMPT_VERSION,
        tool_catalog_version=run.tool_catalog_version or TOOL_CATALOG_VERSION,
        diagnosis=result.diagnosis or run.final_diagnosis,
        run=run,
        prompt=prompt,
        stop_reason=result.stop_reason,
    )


def replay_and_score(
    run: IncidentRun,
    events: Sequence[AgentEvent],
    scenario: IncidentScenario,
    *,
    variant_id: str | None = None,
    condition: str = "single_agent",
    split: str = "eval",
    prompt: str | None = None,
    budget: ToolBudget | None = None,
) -> tuple[ReplayResult, ScoreCard]:
    replayed = replay_events(run, events, budget or ToolBudget())
    card = score_replay(
        replayed,
        scenario,
        variant_id=variant_id,
        condition=condition,
        split=split,
        prompt=prompt,
    )
    return replayed, card


def replay_store_and_score(
    store: InvestigationStore,
    run_id: UUID,
    *,
    scenario: IncidentScenario | None = None,
    variant_id: str | None = None,
    condition: str = "single_agent",
    split: str = "eval",
    prompt: str | None = None,
) -> tuple[ReplayResult, ScoreCard]:
    result = replay_store(store, run_id)
    resolved = scenario
    if resolved is None:
        if result.run.scenario_id is None:
            raise ValueError("replay scoring requires a scenario_id")
        resolved = scenario_by_id(result.run.scenario_id)
    return result, score_replay(
        result,
        resolved,
        variant_id=variant_id,
        condition=condition,
        split=split,
        prompt=prompt,
    )
