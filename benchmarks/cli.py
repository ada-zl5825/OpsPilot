from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opspilot-benchmark")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print("benchmark harness not implemented (Phase 5)")
        return 0
    print("benchmark harness not implemented (Phase 5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
