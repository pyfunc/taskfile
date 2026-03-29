"""Minimal CLI entry point for the nested fixop package."""

from __future__ import annotations

import sys


def main() -> int:
    """Run the compatibility CLI."""
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print("fixop - infrastructure fix operations")
        print("Compatibility package used by Goal workflow checks.")
        return 0

    print("fixop compatibility package is installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
