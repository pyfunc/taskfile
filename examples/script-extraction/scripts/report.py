#!/usr/bin/env python3
"""report.py — Generate deployment report extracted from Taskfile.yml.

Taskfile calls: python scripts/report.py --app webapp --env prod
"""

import argparse
import json
import os
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Deployment report")
    parser.add_argument("--app", required=True, help="Application name")
    parser.add_argument("--env", required=True, help="Target environment")
    args = parser.parse_args()

    tag = os.environ.get("TAG", "latest")
    domain = os.environ.get("DOMAIN", "unknown")

    report = {
        "app": args.app,
        "env": args.env,
        "tag": tag,
        "domain": domain,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": "deployed",
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
