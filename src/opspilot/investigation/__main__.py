import sys

from opspilot.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["investigate", *sys.argv[1:]]))
