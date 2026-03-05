#!/usr/bin/env python3
"""Generate deployment report JSON."""

import json
import os
from datetime import datetime


def main():
    report = {
        "app": os.environ.get("APP_NAME", "unknown"),
        "image": os.environ.get("IMAGE", "unknown"),
        "tag": os.environ.get("TAG", "latest"),
        "environment": os.environ.get("DEPLOY_ENV", "unknown"),
        "timestamp": datetime.now().isoformat(),
        "status": "deployed",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
