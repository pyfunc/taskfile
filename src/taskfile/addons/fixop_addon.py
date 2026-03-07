"""Fixop addon — generates infrastructure health check and drift detection tasks.

Generated tasks:
    fixop-doctor, fixop-drift, fixop-tls, fixop-fix

Usage in Taskfile.yml:
    addons:
      - fixop:
          host: prod.example.com
          domains: ["example.com", "api.example.com"]
          readme: README.md
          source_dir: sandbox/
          auto_fix: false
"""

from __future__ import annotations


def generate_tasks(config: dict) -> dict[str, dict]:
    """Generate fixop tasks from addon config."""
    host = config.get("host", "${SSH_HOST}")
    user = config.get("user", "${SSH_USER}")
    domains = config.get("domains", [])
    containers = config.get("containers", [])
    readme = config.get("readme", "README.md")
    source_dir = config.get("source_dir", "sandbox/")
    auto_fix = config.get("auto_fix", False)

    tasks: dict[str, dict] = {}

    # doctor: full remote infrastructure check
    doctor_args = f"--host {host} --user {user}"
    if domains:
        doctor_args += f" --domains {','.join(domains)}"
    if containers:
        doctor_args += f" --containers {','.join(containers)}"

    tasks["fixop-doctor"] = {
        "desc": "Run infrastructure health checks (fixop)",
        "tags": ["ops", "fixop"],
        "cmds": [f"fixop doctor {doctor_args}"],
    }

    # drift: check README blocks vs disk files
    tasks["fixop-drift"] = {
        "desc": "Check for file drift between README and disk",
        "tags": ["ci", "fixop"],
        "cmds": [f"fixop drift {readme} {source_dir}"],
    }

    # tls: check TLS certificates if domains are specified
    if domains:
        tasks["fixop-tls"] = {
            "desc": "Check TLS certificates for all domains",
            "tags": ["ops", "fixop", "tls"],
            "cmds": [f"fixop check-tls {' '.join(domains)}"],
        }

    # fix: auto-fix if enabled
    if auto_fix:
        tasks["fixop-fix"] = {
            "desc": "Auto-fix infrastructure issues",
            "tags": ["ops", "fixop"],
            "cmds": [f"fixop fix --host {host} --user {user} --auto"],
        }

    return tasks
