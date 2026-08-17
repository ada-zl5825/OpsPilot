from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.single_vs_verifier.report import run_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="single-vs-verifier")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Score frozen Single vs Verifier A/B",
    )
    parser.add_argument("--split", choices=("eval", "holdout"), default="eval")
    parser.add_argument("--out", default="artifacts/experiments/single_vs_verifier")
    args = parser.parse_args(argv)
    if not args.offline:
        parser.print_help()
        return 0
    report = run_experiment(split=args.split, out_dir=Path(args.out), include_holdout=True)
    print(report.model_dump_json(indent=2))
    artifact = report.extra.get("artifact_dir")
    if artifact:
        print(f"wrote {artifact}/report.json and {artifact}/report.md")
    if report.comparison.promotion.promote:
        print(json.dumps({"promotion": "PROMOTE"}))
        return 0
    print(json.dumps({"promotion": "DO_NOT_PROMOTE"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
