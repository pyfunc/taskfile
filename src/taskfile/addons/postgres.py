"""Postgres addon — generates database management tasks.

Generated tasks:
    db-status, db-size, db-migrate, db-backup, db-restore, db-vacuum, db-prune-backups
"""

from __future__ import annotations


def generate_tasks(config: dict) -> dict[str, dict]:
    """Generate PostgreSQL management tasks from addon config."""
    db_name = config.get("db_name", "${DB_NAME}")
    db_user = config.get("db_user", db_name)
    db_host = config.get("db_host", "localhost")
    db_port = config.get("db_port", "5432")
    backup_dir = config.get("backup_dir", "/tmp/db-backups")
    migration_cmd = config.get("migration_cmd", "alembic upgrade head")

    psql = f"psql -h {db_host} -p {db_port} -U {db_user} -d {db_name}"

    return {
        "db-status": {
            "desc": "Check database connectivity and version",
            "tags": ["db", "ops"],
            "silent": True,
            "cmds": [
                f'{psql} -c "SELECT version();" 2>/dev/null && echo "DB OK" || echo "DB FAIL"',
            ],
        },
        "db-size": {
            "desc": "Show database size and largest tables",
            "tags": ["db", "ops"],
            "cmds": [
                f"""{psql} -c "SELECT pg_size_pretty(pg_database_size('{db_name}'));" """,
                f"""{psql} -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;" """,
            ],
        },
        "db-migrate": {
            "desc": "Run database migrations",
            "tags": ["db", "deploy"],
            "condition": "test -d migrations/",
            "cmds": [migration_cmd],
        },
        "db-backup": {
            "desc": "Full database backup (pg_dump custom format)",
            "tags": ["db", "backup"],
            "timeout": 3600,
            "register": "BACKUP_PATH",
            "cmds": [
                f"mkdir -p {backup_dir}",
                f"pg_dump -h {db_host} -p {db_port} -U {db_user} -Fc {db_name} > {backup_dir}/{db_name}_$(date +%Y%m%d_%H%M%S).dump",
                f"ls -lh {backup_dir}/{db_name}_*.dump | tail -1",
            ],
        },
        "db-restore": {
            "desc": "Restore database from backup (--var BACKUP_FILE=path)",
            "tags": ["db", "ops"],
            "cmds": [
                f"pg_restore -h {db_host} -p {db_port} -U {db_user} -d {db_name} --clean --if-exists ${{BACKUP_FILE}}",
                "echo 'Database restored from ${BACKUP_FILE}'",
            ],
        },
        "db-vacuum": {
            "desc": "Run VACUUM ANALYZE on database",
            "tags": ["db", "maintenance"],
            "timeout": 1800,
            "cmds": [
                f'{psql} -c "VACUUM ANALYZE;"',
                "echo 'VACUUM ANALYZE complete'",
            ],
        },
        "db-prune-backups": {
            "desc": "Remove backups older than 30 days",
            "tags": ["db", "backup", "maintenance"],
            "cmds": [
                f'find {backup_dir} -name "*.dump" -mtime +30 -delete',
                "echo 'Old backups pruned'",
            ],
        },
    }
