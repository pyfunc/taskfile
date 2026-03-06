"""Redis addon — generates Redis management tasks.

Generated tasks:
    redis-status, redis-ping, redis-flush, redis-info, redis-monitor
"""

from __future__ import annotations


def generate_tasks(config: dict) -> dict[str, dict]:
    """Generate Redis management tasks from addon config."""
    url = config.get("url", "redis://localhost:6379")
    cli = config.get("cli", "redis-cli")

    # Parse host:port from URL for redis-cli
    # redis://localhost:6379 → -h localhost -p 6379
    host = "localhost"
    port = "6379"
    if "://" in url:
        netloc = url.split("://", 1)[1].rstrip("/")
        if ":" in netloc:
            host, port = netloc.rsplit(":", 1)
        else:
            host = netloc

    cli_args = f"-h {host} -p {port}"

    return {
        "redis-status": {
            "desc": "Check Redis connectivity",
            "tags": ["redis", "ops"],
            "silent": True,
            "cmds": [
                f'{cli} {cli_args} ping 2>/dev/null && echo "Redis OK" || echo "Redis FAIL"',
            ],
        },
        "redis-info": {
            "desc": "Show Redis server info (memory, clients, stats)",
            "tags": ["redis", "ops"],
            "cmds": [
                f"{cli} {cli_args} info memory | head -20",
                f"{cli} {cli_args} info clients | head -10",
                f"{cli} {cli_args} dbsize",
            ],
        },
        "redis-flush": {
            "desc": "Flush all Redis databases (use with caution)",
            "tags": ["redis", "maintenance"],
            "cmds": [
                f"{cli} {cli_args} flushall",
                "echo 'All Redis databases flushed'",
            ],
        },
        "redis-monitor": {
            "desc": "Monitor Redis commands in real-time (Ctrl+C to stop)",
            "tags": ["redis", "ops"],
            "cmds": [
                f"{cli} {cli_args} monitor",
            ],
        },
    }
