#!/usr/bin/env python3
"""provision.py — Server provisioning with Python SSH logic.

Taskfile calls: python scripts/provision.py --host prod.example.com --user deploy
This demonstrates how complex SSH logic can be extracted to Python
while keeping Taskfile.yml declarative.
"""

import argparse
import subprocess
import sys


def ssh_run(host: str, user: str, cmd: str, check: bool = True) -> int:
    """Run a command on remote host via SSH."""
    full_cmd = f'ssh -o StrictHostKeyChecking=accept-new {user}@{host} "{cmd}"'
    print(f"  → [SSH] {cmd}")
    result = subprocess.run(full_cmd, shell=True)
    if check and result.returncode != 0:
        print(f"  ✗ Failed on {host}: {cmd}")
        if check:
            sys.exit(result.returncode)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Server provisioning")
    parser.add_argument("--host", required=True, help="Target host")
    parser.add_argument("--user", required=True, help="SSH user")
    parser.add_argument("--dry-run", action="store_true", help="Print only")
    args = parser.parse_args()

    steps = [
        "sudo apt-get update -qq",
        "sudo apt-get install -y podman podman-compose",
        "sudo loginctl enable-linger $(whoami)",
        "mkdir -p ~/.config/containers/systemd",
        "podman network create proxy 2>/dev/null || true",
    ]

    print(f"=== Provisioning {args.user}@{args.host} ===\n")

    if args.dry_run:
        for step in steps:
            print(f"  [dry] ssh {args.user}@{args.host} '{step}'")
        return

    for step in steps:
        ssh_run(args.host, args.user, step)

    print(f"\n✅ Server {args.host} provisioned")


if __name__ == "__main__":
    main()
