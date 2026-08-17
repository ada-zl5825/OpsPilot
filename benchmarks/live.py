from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import httpx
from simulator.harness.client import LabClient

from benchmarks.datasets.variants import ScenarioVariant, load_variants, parent_scenario
from benchmarks.report import build_report, write_report
from opspilot.eval.models import BenchmarkReport, ScoreCard
from opspilot.eval.scorer import score_trajectory
from opspilot.holmes.client import HolmesClient
from opspilot.investigation.runner import InvestigationRunner
from opspilot.investigation.store import JsonlInvestigationStore
from opspilot.logging import get_logger
from opspilot.settings import get_settings
from opspilot.verifier.runner import VerifierRunner

logger = get_logger("opspilot.benchmark.live")


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


def run_live_verifier(
    *,
    split: str = "eval",
    scenario_ids: Sequence[str] | None = None,
    out_dir: Path | None = None,
) -> BenchmarkReport:
    settings = get_settings()
    if not settings.azure_configured():
        raise RuntimeError("live verifier requires Azure credentials in .env; not used on PRs")
    variants = load_variants(split=split)
    if scenario_ids:
        wanted = set(scenario_ids)
        variants = [item for item in variants if item.scenario_id in wanted]
    else:
        variants = _one_per_family(variants)
    return asyncio.run(_run_verifier(variants, Path(out_dir or "artifacts/benchmarks-live-verify")))


def _one_per_family(variants: Sequence[ScenarioVariant]) -> list[ScenarioVariant]:
    seen: set[str] = set()
    unique: list[ScenarioVariant] = []
    for item in variants:
        if item.scenario_id in seen:
            continue
        seen.add(item.scenario_id)
        unique.append(item)
    return unique


def _arm_lab(lab: LabClient, scenario_id: str) -> None:
    lab.reset_all()
    body = lab.inject(scenario_id)
    if not body.get("injected"):
        raise RuntimeError(f"lab inject failed for {scenario_id}")
    for _ in range(3):
        try:
            lab.place_order(timeout=8.0)
        except httpx.HTTPError:
            continue
    lab.wait_until(lab.prometheus_has_recent_checkout_traffic, timeout_sec=20)
    lab.wait_until(lambda: lab.loki_has_recent_service_logs("checkout"), timeout_sec=15)


async def _run(variants: Sequence[ScenarioVariant], out_dir: Path) -> BenchmarkReport:
    settings = get_settings()
    store = JsonlInvestigationStore(out_dir / "investigations")
    timeout = httpx.Timeout(settings.holmes_timeout_seconds)
    lab = LabClient()
    if not lab.controller_healthy():
        lab.close()
        raise RuntimeError("live benchmark requires the lab controller at http://127.0.0.1:8090")
    cards: list[ScoreCard] = []
    try:
        async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=timeout) as http:
            client = HolmesClient(settings, client=http)
            runner = InvestigationRunner(client, store, settings=settings)
            for variant in variants:
                logger.info(
                    "live_variant_start",
                    variant_id=variant.variant_id,
                    scenario_id=variant.scenario_id,
                )
                print(f"live start {variant.variant_id}", flush=True)
                _arm_lab(lab, variant.scenario_id)
                result = await runner.run(
                    variant.scenario_id,
                    source="benchmark",
                    user_report=variant.user_report,
                )
                lab.reset(variant.scenario_id)
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
                logger.info(
                    "live_variant_end",
                    variant_id=variant.variant_id,
                    status=result.run.status.value,
                    composite=cards[-1].composite,
                )
                print(
                    f"live end {variant.variant_id} status={result.run.status.value} "
                    f"composite={cards[-1].composite:.3f}",
                    flush=True,
                )
    finally:
        try:
            lab.reset_all()
        finally:
            lab.close()
    report = build_report(cards, split="eval", conditions=["single_agent"])
    report.extra["mode"] = "live"
    report.extra["lab_injected"] = "true"
    write_report(report, out_dir / str(uuid4()))
    return report


async def _run_verifier(variants: Sequence[ScenarioVariant], out_dir: Path) -> BenchmarkReport:
    settings = get_settings()
    store = JsonlInvestigationStore(out_dir / "investigations")
    timeout = httpx.Timeout(settings.holmes_timeout_seconds)
    lab = LabClient()
    if not lab.controller_healthy():
        lab.close()
        raise RuntimeError("live verifier requires the lab controller at http://127.0.0.1:8090")
    cards: list[ScoreCard] = []
    extras: list[dict[str, str]] = []
    try:
        async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=timeout) as http:
            client = HolmesClient(settings, client=http)
            runner = VerifierRunner(client, store, settings=settings)
            for variant in variants:
                print(f"verify start {variant.variant_id}", flush=True)
                _arm_lab(lab, variant.scenario_id)
                result = await runner.run(
                    variant.scenario_id,
                    source="benchmark",
                    user_report=variant.user_report,
                )
                lab.reset(variant.scenario_id)
                scenario = parent_scenario(variant)
                cards.append(
                    score_trajectory(
                        result.events,
                        scenario,
                        variant_id=variant.variant_id,
                        condition="verifier",
                        split=variant.split,
                        model=result.run.model,
                        prompt_version=result.run.prompt_version,
                        tool_catalog_version=result.run.tool_catalog_version,
                        diagnosis=result.run.final_diagnosis,
                        run=result.run,
                        prompt=result.investigation.prompt,
                        stop_reason=result.stop_reason,
                    )
                )
                extras.append(
                    {
                        "variant_id": variant.variant_id,
                        "status": result.run.status.value,
                        "stop_reason": result.stop_reason.value,
                        "followup_used": str(result.followup_used).lower(),
                        "verdicts": ",".join(item.decision for item in result.verdicts) or "none",
                    }
                )
                print(
                    f"verify end {variant.variant_id} status={result.run.status.value} "
                    f"stop={result.stop_reason.value} followup={result.followup_used} "
                    f"verdicts={[item.decision for item in result.verdicts]} "
                    f"composite={cards[-1].composite:.3f}",
                    flush=True,
                )
    finally:
        try:
            lab.reset_all()
        finally:
            lab.close()
    target = out_dir / str(uuid4())
    report = build_report(cards, split="eval", conditions=["verifier"])
    report.extra["mode"] = "live_verifier"
    report.extra["lab_injected"] = "true"
    report.extra["runs"] = extras
    report.extra["artifact_dir"] = str(target)
    write_report(report, target)
    return report
