from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import httpx

from benchmarks.datasets.variants import ScenarioVariant, load_variants, parent_scenario
from benchmarks.report import build_report, write_report
from opspilot.eval.models import BenchmarkReport, ScoreCard
from opspilot.eval.scorer import score_trajectory
from opspilot.holmes.client import HolmesClient
from opspilot.investigation.runner import InvestigationRunner
from opspilot.investigation.store import JsonlInvestigationStore
from opspilot.settings import get_settings


def run_live(
    *,
    split: str = "eval",
    scenario_ids: Sequence[str] | None = None,
    out_dir: Path | None = None,
) -> BenchmarkReport:
    settings = get_settings()
    if not settings.azure_configured():
        raise RuntimeError("live benchmark requires Azure credentials in .env; not used on PRs")
    variants = load_variants(split=split)
    if scenario_ids:
        wanted = set(scenario_ids)
        variants = [item for item in variants if item.scenario_id in wanted]
    else:
        variants = _one_per_family(variants)
    return asyncio.run(_run(variants, Path(out_dir or "artifacts/benchmarks-live")))


def _one_per_family(variants: Sequence[ScenarioVariant]) -> list[ScenarioVariant]:
    seen: set[str] = set()
    unique: list[ScenarioVariant] = []
    for item in variants:
        if item.scenario_id in seen:
            continue
        seen.add(item.scenario_id)
        unique.append(item)
    return unique


async def _run(variants: Sequence[ScenarioVariant], out_dir: Path) -> BenchmarkReport:
    settings = get_settings()
    store = JsonlInvestigationStore(out_dir / "investigations")
    timeout = httpx.Timeout(settings.holmes_timeout_seconds)
    cards: list[ScoreCard] = []
    async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=timeout) as http:
        client = HolmesClient(settings, client=http)
        runner = InvestigationRunner(client, store, settings=settings)
        for variant in variants:
            result = await runner.run(
                variant.scenario_id,
                source="benchmark",
                user_report=variant.user_report,
            )
            scenario = parent_scenario(variant)
            cards.append(
                score_trajectory(
                    result.events,
                    scenario,
                    variant_id=variant.variant_id,
                    condition="single_agent",
                    split=variant.split,
                    model=result.run.model,
                    prompt_version=result.run.prompt_version,
                    tool_catalog_version=result.run.tool_catalog_version,
                    diagnosis=result.run.final_diagnosis,
                    run=result.run,
                    prompt=result.prompt,
                    stop_reason=result.stop_reason,
                )
            )
    report = build_report(cards, split="eval", conditions=["single_agent"])
    report.extra["mode"] = "live"
    write_report(report, out_dir / str(uuid4()))
    return report
