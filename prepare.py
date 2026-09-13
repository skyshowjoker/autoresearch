"""Fixed data-preparation entry point."""

import sys

from autoquant.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["prepare", *sys.argv[1:]]))
