from __future__ import annotations

import argparse
import json

from opspilot import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opspilot", description="OpsPilot Incident Lab")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("health", help="Print local control-plane health payload")
    sub.add_parser("holmes-smoke", help="Check pinned HolmesGPT /healthz")
    args = parser.parse_args(argv)

    if args.command == "health":
        print(json.dumps({"status": "ok", "phase": "0"}))
        return 0
    if args.command == "holmes-smoke":
        from opspilot.holmes.smoke import main as smoke_main

        return smoke_main()

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
