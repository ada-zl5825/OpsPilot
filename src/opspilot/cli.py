from __future__ import annotations

import argparse

from opspilot import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opspilot", description="OpsPilot Incident Lab")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("health", help="Print local control-plane health payload")
    args = parser.parse_args(argv)

    if args.command == "health":
        print('{"status":"ok","phase":"init"}')
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
