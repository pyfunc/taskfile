#!/usr/bin/env python3
"""migrate.py — Database migration script extracted from Taskfile.yml.

Taskfile calls: python scripts/migrate.py --env prod
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Database migration")
    parser.add_argument("--env", required=True, help="Target environment")
    parser.add_argument("--rollback", action="store_true", help="Rollback last migration")
    args = parser.parse_args()

    app = os.environ.get("APP_NAME", "webapp")
    print(f"=== Database migration for {app} ({args.env}) ===")

    if args.rollback:
        print("→ Rolling back last migration...")
        # alembic downgrade -1
    else:
        print("→ Running pending migrations...")
        # alembic upgrade head

    print(f"✅ Migration complete ({args.env})")


if __name__ == "__main__":
    main()
