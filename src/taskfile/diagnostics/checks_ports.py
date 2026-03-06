"""Port conflict detection helpers — extracted from checks.py for modularity."""

from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path

import yaml

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_WARNING,
)


def check_ports() -> list[Issue]:
    """Check docker-compose port conflicts and suggest .env fixes."""
    issues: list[Issue] = []
    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        return issues

    try:
        compose = yaml.safe_load(compose_path.read_text()) or {}
    except Exception:
        return issues

    services = (compose or {}).get("services") or {}
    if not isinstance(services, dict):
        return issues

    from taskfile.compose import load_env_file, resolve_variables

    env_path = Path(".env")
    env_vars = load_env_file(env_path) if env_path.exists() else {}
    ctx = {**os.environ, **env_vars}

    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for port_entry in (svc.get("ports") or []):
            if not isinstance(port_entry, str):
                continue
            conflict = _resolve_port_conflict(svc_name, port_entry, ctx)
            if conflict:
                key, resolved_port, suggested = conflict
                pid, process = _who_uses_port(resolved_port)
                issues.append(Issue(
                    category=IssueCategory.RUNTIME_ERROR,
                    message=f"Port {resolved_port} for service '{svc_name}' is in use"
                            + (f" by '{process}' (pid {pid})" if process else ""),
                    fix_strategy=FixStrategy.CONFIRM,
                    severity=SEVERITY_WARNING,
                    fix_command=f"docker stop {process}" if process and _is_docker_process(process) else None,
                    fix_description=f"Set {key}={suggested} in .env or stop the conflicting process",
                    teach=(
                        f"Each service needs a unique port to listen on. Port {resolved_port} is already "
                        "in use by another process. Either stop the existing process or configure a "
                        "different port in your .env file. Use 'lsof -i :<port>' to find what's using it."
                    ),
                    context={"port_fixes": {key: suggested}},
                    layer=3,
                ))
    return issues


def _resolve_port_conflict(
    svc_name: str, port_entry: str, ctx: dict
) -> tuple[str, int, int] | None:
    """Check a single port entry for conflicts. Returns (key, port, suggested) or None."""
    host_port, var_name = _parse_compose_host_port(port_entry)
    if host_port is None:
        return None

    from taskfile.compose import resolve_variables
    expanded = resolve_variables(str(host_port), ctx)
    try:
        resolved = int(expanded)
    except ValueError:
        return None

    if _is_port_free(resolved):
        return None

    suggested = _find_free_port_near(resolved)
    if suggested is None:
        return None

    key = var_name or f"PORT_{svc_name.upper()}"
    return key, resolved, suggested


def _parse_compose_host_port(port_entry: str) -> tuple[str | None, str | None]:
    entry = port_entry.strip()
    if not entry:
        return None, None
    entry = entry.split("/", 1)[0]
    parts = entry.split(":")
    if len(parts) < 2:
        return None, None
    host_port_expr = parts[-2]
    var_name = None
    m = re.match(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)", host_port_expr)
    if m:
        var_name = m.group("name")
    return host_port_expr, var_name


def _is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False


def _find_free_port_near(start: int, span: int = 50) -> int | None:
    for p in range(start, start + span + 1):
        if _is_port_free(p):
            return p
    for p in range(max(1024, start - span), start):
        if _is_port_free(p):
            return p
    return None


def _who_uses_port(port: int) -> tuple[int | None, str | None]:
    """Find pid and process name using a port. Returns (pid, name) or (None, None)."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pid = int(result.stdout.strip().split("\n")[0])
            ps = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                capture_output=True, text=True, timeout=5,
            )
            name = ps.stdout.strip() if ps.returncode == 0 else None
            return pid, name
    except Exception:
        pass
    return None, None


def _is_docker_process(process_name: str | None) -> bool:
    if not process_name:
        return False
    return any(x in (process_name or "").lower() for x in ("docker", "containerd", "podman"))
