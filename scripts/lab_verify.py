from __future__ import annotations

from simulator.harness.verify import run_and_print


def main() -> int:
    return run_and_print(cycles=2)


if __name__ == "__main__":
    raise SystemExit(main())
