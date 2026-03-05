#!/usr/bin/env python3
"""release.py — Full release workflow extracted from Taskfile.yml.

Taskfile calls: python scripts/release.py --tag v1.0.0
Variables APP_NAME, IMAGE come from taskfile runner environment.
"""

import argparse
import os
import subprocess
import sys


def run(cmd: str, check: bool = True) -> int:
    """Run shell command, print it, return exit code."""
    print(f"  → {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"  ✗ Failed: {cmd}")
        sys.exit(result.returncode)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Release workflow")
    parser.add_argument("--tag", required=True, help="Release tag (e.g. v1.0.0)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")
    args = parser.parse_args()

    app = os.environ.get("APP_NAME", "webapp")
    image = os.environ.get("IMAGE", f"ghcr.io/myorg/{app}")
    tag = args.tag

    print(f"=== Release {app}:{tag} ===\n")

    steps = [
        f'git tag -a {tag} -m "Release {tag}"',
        f"git push origin {tag}",
        f"docker build -t {image}:{tag} .",
        f"docker push {image}:{tag}",
    ]

    if args.dry_run:
        print("DRY RUN — commands that would execute:")
        for step in steps:
            print(f"  [dry] {step}")
        return

    for step in steps:
        run(step)

    print(f"\n✅ Released {app}:{tag}")


if __name__ == "__main__":
    main()
