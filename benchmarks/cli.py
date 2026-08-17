from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from opspilot.eval.constants import BENCHMARK_VERSION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opspilot-benchmark")
    parser.add_argument("--offline", action="store_true", help="Score frozen offline baselines")
    parser.add_argument("--live", action="store_true", help="Manual Azure run; never used on PRs")
    parser.add_argument("--replay", action="store_true", help="Score a stored investigation run")
    parser.add_argument("--dry-run", action="store_true", help="List frozen variants and exit")
    parser.add_argument(
        "--gate", action="store_true", help="Compare offline scores to frozen baseline"
    )
    parser.add_argument("--split", choices=("eval", "holdout"), default="eval")
    parser.add_argument(
        "--condition",
        dest="conditions",
        action="append",
        choices=("deterministic", "single_agent", "verifier"),
        default=[],
    )
    parser.add_argument("--scenario", dest="scenarios", action="append", default=[])
    parser.add_argument("--run-id")
    parser.add_argument("--artifact-dir", default="artifacts/investigations")
    parser.add_argument("--out", default="artifacts/benchmarks")
    args = parser.parse_args(argv)

    if args.dry_run:
        return _dry_run(args.split)
    if args.replay:
        return _replay(args)
    if args.live:
        return _live(args)
    if args.offline or args.gate:
        return _offline(args)
    parser.print_help()
    return 0


def _dry_run(split: str) -> int:
    from benchmarks.datasets.check_integrity import check_all
    from benchmarks.datasets.variants import load_variants

    errors = check_all()
    variants = load_variants(split=split)
    payload = {
        "benchmark_version": BENCHMARK_VERSION,
        "split": split,
        "variant_count": len(variants),
        "variant_ids": [item.variant_id for item in variants],
        "integrity_ok": not errors,
        "integrity_errors": errors,
    }
    print(json.dumps(payload, indent=2))
    return 1 if errors else 0


def _offline(args: argparse.Namespace) -> int:
    from benchmarks.harness import CONDITIONS, run_offline

    conditions = tuple(args.conditions) if args.conditions else CONDITIONS
    report = run_offline(
        split=args.split,
        conditions=conditions,
        out_dir=Path(args.out),
        gate=args.gate,
    )
    print(report.model_dump_json(indent=2))
    artifact = report.extra.get("artifact_dir")
    if artifact:
        print(f"wrote {artifact}/report.json and {artifact}/report.md")
    if args.gate and report.gate_passed is False:
        return 1
    return 0


def _replay(args: argparse.Namespace) -> int:
    from opspilot.eval.replay import replay_store_and_score
    from opspilot.investigation.store import JsonlInvestigationStore
    from opspilot.lab.scenarios import scenario_by_id

    if not args.run_id:
        raise SystemExit("--replay requires --run-id")
    store = JsonlInvestigationStore(Path(args.artifact_dir))
    scenario = scenario_by_id(args.scenarios[0]) if args.scenarios else None
    _replayed, card = replay_store_and_score(
        store,
        UUID(args.run_id),
        scenario=scenario,
        condition="single_agent",
        split=args.split,
    )
    print(card.model_dump_json(indent=2))
    return 0 if card.composite > 0 or not card.hard_fails else 1


def _live(args: argparse.Namespace) -> int:
    from benchmarks.live import run_live, run_live_verifier

    if args.conditions == ["verifier"]:
        report = run_live_verifier(
            split=args.split,
            scenario_ids=args.scenarios or None,
            out_dir=Path(args.out),
        )
    else:
        report = run_live(
            split=args.split,
            scenario_ids=args.scenarios or None,
            out_dir=Path(args.out),
        )
    print(report.model_dump_json(indent=2))
    artifact = report.extra.get("artifact_dir")
    if artifact:
        print(f"wrote {artifact}/report.json and {artifact}/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
