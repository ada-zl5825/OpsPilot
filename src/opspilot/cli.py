from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from opspilot import __version__
from opspilot.investigation.constants import PROMPT_VERSION, TOOL_CATALOG_VERSION
from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS
from opspilot.verifier.constants import VERIFIER_PROMPT_VERSION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opspilot", description="OpsPilot Incident Lab")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("health", help="Print local control-plane health payload")
    sub.add_parser("holmes-smoke", help="Check pinned HolmesGPT /healthz")
    sub.add_parser("lab-verify", help="Verify S01-S04 inject/reset and recovery without an LLM")

    investigate = sub.add_parser("investigate", help="Run Phase 3 Single-Agent investigation")
    investigate.add_argument("--scenario", dest="scenarios", action="append", default=[])
    investigate.add_argument("--all", action="store_true", help="Run S01-S04")
    investigate.add_argument(
        "--prompt-only",
        action="store_true",
        help="Print investigation prompts without calling Holmes",
    )
    investigate.add_argument("--artifact-dir", default="artifacts/investigations")

    verify = sub.add_parser("verify", help="Run Phase 6 Investigator + Verifier")
    verify.add_argument("--scenario", dest="scenarios", action="append", default=[])
    verify.add_argument("--all", action="store_true", help="Run S01-S04")
    verify.add_argument(
        "--prompt-only",
        action="store_true",
        help="Print Investigator and Verifier prompts without calling Holmes",
    )
    verify.add_argument("--artifact-dir", default="artifacts/investigations")

    replay = sub.add_parser("replay", help="Replay a stored investigation trajectory")
    replay.add_argument("--run-id", required=True)
    replay.add_argument("--artifact-dir", default="artifacts/investigations")

    benchmark = sub.add_parser("benchmark", help="Run Phase 5 offline benchmark")
    benchmark.add_argument("--offline", action="store_true")
    benchmark.add_argument("--live", action="store_true")
    benchmark.add_argument("--replay", action="store_true")
    benchmark.add_argument("--dry-run", action="store_true")
    benchmark.add_argument("--gate", action="store_true")
    benchmark.add_argument("--split", choices=("eval", "holdout"), default="eval")
    benchmark.add_argument(
        "--condition",
        dest="conditions",
        action="append",
        choices=("deterministic", "single_agent", "verifier"),
        default=[],
    )
    benchmark.add_argument("--scenario", dest="scenarios", action="append", default=[])
    benchmark.add_argument("--run-id")
    benchmark.add_argument("--artifact-dir", default="artifacts/investigations")
    benchmark.add_argument("--out", default="artifacts/benchmarks")

    args = parser.parse_args(argv)

    if args.command == "health":
        print(
            json.dumps(
                {
                    "status": "ok",
                    "phase": "6",
                    "prompt_version": PROMPT_VERSION,
                    "verifier_prompt_version": VERIFIER_PROMPT_VERSION,
                    "tool_catalog_version": TOOL_CATALOG_VERSION,
                }
            )
        )
        return 0
    if args.command == "holmes-smoke":
        from opspilot.holmes.smoke import main as smoke_main

        return smoke_main()
    if args.command == "lab-verify":
        from simulator.harness.verify import run_and_print

        return run_and_print(cycles=2)
    if args.command == "investigate":
        return _investigate(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "replay":
        return _replay(args)
    if args.command == "benchmark":
        from benchmarks.cli import main as benchmark_main

        forwarded: list[str] = []
        if args.offline:
            forwarded.append("--offline")
        if args.live:
            forwarded.append("--live")
        if args.replay:
            forwarded.append("--replay")
        if args.dry_run:
            forwarded.append("--dry-run")
        if args.gate:
            forwarded.append("--gate")
        forwarded.extend(["--split", args.split])
        for condition in args.conditions:
            forwarded.extend(["--condition", condition])
        for scenario_id in args.scenarios:
            forwarded.extend(["--scenario", scenario_id])
        if args.run_id:
            forwarded.extend(["--run-id", args.run_id])
        forwarded.extend(["--artifact-dir", args.artifact_dir, "--out", args.out])
        return benchmark_main(forwarded)

    parser.print_help()
    return 0


def _scenario_ids(args: argparse.Namespace) -> list[str]:
    if args.all:
        return list(REQUIRED_SCENARIO_IDS)
    if args.scenarios:
        return list(args.scenarios)
    raise SystemExit("investigate requires --scenario ID or --all")


def _investigate(args: argparse.Namespace) -> int:
    from opspilot.investigation.budget import ToolBudget
    from opspilot.investigation.prompt import build_investigation_prompt, to_agent_visible
    from opspilot.investigation.safety import assert_no_ground_truth
    from opspilot.lab.scenarios import scenario_by_id

    ids = _scenario_ids(args)
    budget = ToolBudget()
    if args.prompt_only:
        for scenario_id in ids:
            scenario = scenario_by_id(scenario_id)
            prompt = build_investigation_prompt(to_agent_visible(scenario), budget)
            assert_no_ground_truth(prompt, scenario)
            print(f"## {scenario_id}\n{prompt}")
        return 0
    return asyncio.run(_run_live(ids, Path(args.artifact_dir)))


def _verify(args: argparse.Namespace) -> int:
    from opspilot.investigation.budget import BudgetState, ToolBudget
    from opspilot.investigation.prompt import to_agent_visible
    from opspilot.investigation.safety import assert_no_ground_truth
    from opspilot.lab.scenarios import scenario_by_id
    from opspilot.verifier.budget import snapshot_budget
    from opspilot.verifier.prompt import build_followup_prompt, build_verifier_prompt
    from opspilot.verifier.schema import FollowupRequest, InvestigatorBundle

    ids = _scenario_ids(args)
    budget = ToolBudget()
    if args.prompt_only:
        for scenario_id in ids:
            scenario = scenario_by_id(scenario_id)
            visible = to_agent_visible(scenario)
            bundle = InvestigatorBundle(
                scenario_id=scenario.scenario_id,
                incident=visible,
                evidence=[],
                budget=snapshot_budget(BudgetState(), budget),
            )
            verifier_prompt = build_verifier_prompt(bundle)
            followup = build_followup_prompt(
                visible,
                bundle,
                FollowupRequest(reason="collect one more read-only observation"),
                budget,
            )
            assert_no_ground_truth(verifier_prompt, scenario)
            assert_no_ground_truth(followup, scenario)
            print(f"## {scenario_id} verifier\n{verifier_prompt}")
            print(f"## {scenario_id} followup\n{followup}")
        return 0
    return asyncio.run(_run_live_verifier(ids, Path(args.artifact_dir)))


async def _run_live_verifier(scenario_ids: list[str], artifact_dir: Path) -> int:
    import httpx

    from opspilot.holmes.client import HolmesClient
    from opspilot.investigation.store import JsonlInvestigationStore
    from opspilot.settings import get_settings
    from opspilot.verifier.runner import VerifierRunner

    settings = get_settings()
    store = JsonlInvestigationStore(artifact_dir)
    timeout = httpx.Timeout(settings.holmes_timeout_seconds)
    async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=timeout) as http:
        client = HolmesClient(settings, client=http)
        runner = VerifierRunner(client, store, settings=settings)
        failed = 0
        for scenario_id in scenario_ids:
            result = await runner.run(scenario_id, source="benchmark")
            payload = {
                "run_id": str(result.run.run_id),
                "scenario_id": scenario_id,
                "status": result.run.status.value,
                "stop_reason": result.stop_reason.value,
                "successful": result.successful,
                "followup_used": result.followup_used,
                "verdicts": [item.decision for item in result.verdicts],
                "evidence_ids": [str(item.evidence_id) for item in result.evidence],
            }
            print(json.dumps(payload))
            if not result.successful:
                failed += 1
    return 1 if failed else 0


async def _run_live(scenario_ids: list[str], artifact_dir: Path) -> int:
    import httpx

    from opspilot.holmes.client import HolmesClient
    from opspilot.investigation.runner import InvestigationRunner
    from opspilot.investigation.store import JsonlInvestigationStore
    from opspilot.settings import get_settings

    settings = get_settings()
    store = JsonlInvestigationStore(artifact_dir)
    timeout = httpx.Timeout(settings.holmes_timeout_seconds)
    async with httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=timeout) as http:
        client = HolmesClient(settings, client=http)
        runner = InvestigationRunner(client, store, settings=settings)
        failed = 0
        for scenario_id in scenario_ids:
            result = await runner.run(scenario_id, source="benchmark")
            payload = {
                "run_id": str(result.run.run_id),
                "scenario_id": scenario_id,
                "status": result.run.status.value,
                "stop_reason": result.stop_reason.value,
                "successful": result.successful,
                "evidence_ids": [str(item.evidence_id) for item in result.evidence],
            }
            print(json.dumps(payload))
            if not result.successful:
                failed += 1
    return 1 if failed else 0


def _replay(args: argparse.Namespace) -> int:
    from opspilot.investigation.replay import replay_store
    from opspilot.investigation.store import JsonlInvestigationStore

    store = JsonlInvestigationStore(Path(args.artifact_dir))
    result = replay_store(store, UUID(args.run_id))
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "status": result.status.value,
                "stop_reason": result.stop_reason.value,
                "successful": result.successful,
                "event_count": len(result.events),
                "evidence_ids": [str(item.evidence_id) for item in result.evidence],
                "diagnosis": result.diagnosis.model_dump(mode="json") if result.diagnosis else None,
            }
        )
    )
    return 0 if result.successful or result.run.status.value != "diagnosis_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
