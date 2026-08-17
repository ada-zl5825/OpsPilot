from __future__ import annotations

import argparse

from simulator.harness.verify import run_and_print


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="simulator.harness", description="Verify S01-S04 without an LLM"
    )
    parser.add_argument("--cycles", type=int, default=2)
    args = parser.parse_args(argv)
    return run_and_print(cycles=args.cycles)


if __name__ == "__main__":
    raise SystemExit(main())
