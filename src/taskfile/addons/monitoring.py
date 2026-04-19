"""Monitoring addon — generates Prometheus/Grafana management tasks.

Generated tasks:
    mon-status, mon-alerts, mon-metrics, mon-dashboard-export, mon-setup
"""

from __future__ import annotations


def generate_tasks(config: dict) -> dict[str, dict]:
    """Generate monitoring tasks from addon config."""
    grafana_url = config.get("grafana_url", config.get("grafana", "http://grafana:3000"))
    prometheus_url = config.get(
        "prometheus_url", config.get("prometheus", "http://prometheus:9090")
    )
    compose_file = config.get("compose_file", "docker-compose.monitoring.yml")

    return {
        "mon-status": {
            "desc": "Check Prometheus + Grafana health",
            "tags": ["ops", "monitoring"],
            "silent": True,
            "cmds": [
                f'curl -sf {prometheus_url}/-/healthy && echo "Prometheus OK" || echo "Prometheus FAIL"',
                f'curl -sf {grafana_url}/api/health && echo "Grafana OK" || echo "Grafana FAIL"',
            ],
        },
        "mon-alerts": {
            "desc": "List active Prometheus alerts",
            "tags": ["ops", "monitoring"],
            "cmds": [
                f"curl -sf {prometheus_url}/api/v1/alerts | python3 -m json.tool",
            ],
        },
        "mon-metrics": {
            "desc": "Query key application metrics",
            "tags": ["ops", "monitoring"],
            "cmds": [
                f'curl -sf "{prometheus_url}/api/v1/query?query=up" | python3 -m json.tool',
            ],
        },
        "mon-dashboard-export": {
            "desc": "Export Grafana dashboards as JSON backup",
            "tags": ["ops", "monitoring", "backup"],
            "cmds": [
                "mkdir -p backups/grafana",
                f"curl -sf {grafana_url}/api/search?type=dash-db | python3 -c \"import sys,json; [print(d['uid']) for d in json.load(sys.stdin)]\" | while read uid; do curl -sf {grafana_url}/api/dashboards/uid/$uid > backups/grafana/$uid.json; done",
                "echo 'Dashboards exported to backups/grafana/'",
            ],
        },
        "mon-setup": {
            "desc": "Deploy monitoring stack via compose",
            "tags": ["ops", "monitoring", "setup"],
            "timeout": 300,
            "cmds": [
                f"docker compose -f {compose_file} up -d",
                "echo 'Monitoring stack running'",
            ],
        },
    }
