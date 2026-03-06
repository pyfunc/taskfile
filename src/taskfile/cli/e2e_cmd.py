"""End-to-end test command for services and IaC validation.

Runs a comprehensive suite of checks against local or remote environments:
1. IaC validation   — Taskfile, compose, quadlet, .env files
2. Service health   — HTTP endpoints respond with expected status
3. Container status — Running containers match expected services
4. SSH connectivity — Remote hosts reachable (for remote envs)
5. Remote health    — Podman, disk space, images on remote

Usage:
    taskfile e2e                          # test local environment
    taskfile e2e --env prod               # test production
    taskfile e2e --check-only             # validate config only (no HTTP)
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

import clickmd as click

from taskfile.cli.main import console, main
from taskfile.parser import TaskfileNotFoundError, TaskfileParseError, load_taskfile


# ─── Test result model ────────────────────────────────────────────


class E2EResult:
    """Single e2e test result."""

    def __init__(self, name: str, passed: bool, detail: str = "", duration_ms: int = 0):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.duration_ms = duration_ms

    @property
    def icon(self) -> str:
        return "✅" if self.passed else "❌"


# ─── Individual checks ───────────────────────────────────────────


def _check_taskfile_valid(config) -> E2EResult:
    """Validate Taskfile.yml structure."""
    from taskfile.parser import validate_taskfile

    warnings = validate_taskfile(config)
    errors = [w for w in warnings if "error" in w.lower()]
    if errors:
        return E2EResult("Taskfile.yml valid", False, f"{len(errors)} error(s)")
    detail = f"{len(warnings)} warning(s)" if warnings else "OK"
    return E2EResult("Taskfile.yml valid", True, detail)


def _check_env_file(env_file: str | None) -> E2EResult:
    """Check .env file exists and has required keys."""
    if not env_file:
        # Try default
        env_file = ".env"
    p = Path(env_file)
    if not p.exists():
        return E2EResult(f".env ({env_file})", False, "file missing")

    from taskfile.deploy_utils import load_env_file

    env = load_env_file(p)
    missing = []
    for key in ("PROD_HOST", "DEPLOY_USER"):
        if not env.get(key):
            missing.append(key)
    if missing:
        return E2EResult(f".env ({env_file})", True, f"warn: {', '.join(missing)} empty")
    return E2EResult(f".env ({env_file})", True, f"{len(env)} vars")


def _check_compose_file(config) -> E2EResult:
    """Check docker-compose.yml exists and is valid YAML."""
    import yaml

    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        return E2EResult("docker-compose.yml", False, "file missing")
    try:
        data = yaml.safe_load(compose_path.read_text())
        services = data.get("services", {}) if data else {}
        return E2EResult("docker-compose.yml", True, f"{len(services)} service(s)")
    except Exception as e:
        return E2EResult("docker-compose.yml", False, str(e)[:60])


def _check_quadlet_files() -> E2EResult:
    """Check quadlet unit files in deploy/quadlet/."""
    quadlet_dir = Path("deploy/quadlet")
    if not quadlet_dir.exists():
        return E2EResult("Quadlet units", True, "no deploy/quadlet/ (skipped)")
    units = list(quadlet_dir.glob("*.container")) + list(quadlet_dir.glob("*.network"))
    if not units:
        return E2EResult("Quadlet units", True, "no .container/.network files")
    # Basic validation: check each file has [Container] or [Network] section
    bad = []
    for u in units:
        content = u.read_text()
        if u.suffix == ".container" and "[Container]" not in content:
            bad.append(u.name)
        if u.suffix == ".network" and "[Network]" not in content:
            bad.append(u.name)
    if bad:
        return E2EResult("Quadlet units", False, f"invalid: {', '.join(bad)}")
    return E2EResult("Quadlet units", True, f"{len(units)} unit(s)")


def _check_local_tools() -> E2EResult:
    """Check docker, docker compose, ssh are available."""
    import shutil

    missing = []
    for tool in ("docker", "ssh"):
        if not shutil.which(tool):
            missing.append(tool)
    # docker compose check
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, timeout=5, check=True,
        )
    except Exception:
        missing.append("docker compose")

    if missing:
        return E2EResult("Local tools", False, f"missing: {', '.join(missing)}")
    return E2EResult("Local tools", True, "docker, compose, ssh")


def _check_http_endpoint(url: str, expected_status: int = 200, timeout: float = 10) -> E2EResult:
    """HTTP GET check on a URL."""
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=timeout)
        ms = int((time.monotonic() - t0) * 1000)
        status = resp.getcode()
        ok = status == expected_status
        return E2EResult(
            f"HTTP {url}",
            ok,
            f"status={status} ({ms}ms)",
            duration_ms=ms,
        )
    except urllib.error.HTTPError as e:
        ms = int((time.monotonic() - t0) * 1000)
        return E2EResult(f"HTTP {url}", False, f"status={e.code} ({ms}ms)", ms)
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return E2EResult(f"HTTP {url}", False, str(e)[:60], ms)


def _check_containers_running(env, config) -> E2EResult:
    """Check expected containers are running (local or remote)."""
    import yaml

    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        return E2EResult("Containers running", True, "no compose file (skipped)")

    try:
        data = yaml.safe_load(compose_path.read_text()) or {}
    except Exception:
        return E2EResult("Containers running", False, "can't parse compose")

    expected = list((data.get("services") or {}).keys())
    if not expected:
        return E2EResult("Containers running", True, "no services defined")

    is_remote = env and hasattr(env, "is_remote") and env.is_remote

    if is_remote:
        from taskfile.deploy_utils import test_ssh_connection

        ssh_ok = test_ssh_connection(env.ssh_host, env.ssh_user, getattr(env, "ssh_port", 22))
        if not ssh_ok.success:
            return E2EResult("Containers running", False, f"SSH to {env.ssh_host} failed")

        runtime = env.container_runtime if env.container_runtime != "docker" else "podman"
        try:
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                 f"{env.ssh_user}@{env.ssh_host}", f"{runtime} ps --format '{{{{.Names}}}}'"],
                capture_output=True, text=True, timeout=15,
            )
            running = set(r.stdout.strip().split("\n")) if r.stdout.strip() else set()
        except Exception as e:
            return E2EResult("Containers running", False, str(e)[:60])
    else:
        try:
            r = subprocess.run(
                ["docker", "compose", "ps", "--format", "{{.Name}}"],
                capture_output=True, text=True, timeout=10,
            )
            running = set(r.stdout.strip().split("\n")) if r.stdout.strip() else set()
        except Exception:
            running = set()

    # Check expected services have at least partial match
    found = []
    missing = []
    for svc in expected:
        if any(svc in name for name in running):
            found.append(svc)
        else:
            missing.append(svc)

    if missing:
        return E2EResult(
            "Containers running", False,
            f"missing: {', '.join(missing)} (running: {', '.join(found) or 'none'})"
        )
    return E2EResult("Containers running", True, f"{len(found)} service(s) up")


def _check_ssh_connectivity(env) -> E2EResult:
    """Test SSH to remote host."""
    if not env or not hasattr(env, "is_remote") or not env.is_remote:
        return E2EResult("SSH connectivity", True, "local env (skipped)")

    from taskfile.deploy_utils import test_ssh_connection

    result = test_ssh_connection(env.ssh_host, env.ssh_user, getattr(env, "ssh_port", 22))
    if result.success:
        return E2EResult("SSH connectivity", True, f"{env.ssh_user}@{env.ssh_host}")
    return E2EResult("SSH connectivity", False, f"failed: {env.ssh_host}")


def _check_remote_podman(env) -> E2EResult:
    """Check podman on remote host."""
    if not env or not hasattr(env, "is_remote") or not env.is_remote:
        return E2EResult("Remote podman", True, "local env (skipped)")

    from taskfile.deploy_utils import check_remote_podman

    ok, ver = check_remote_podman(env.ssh_host, env.ssh_user, getattr(env, "ssh_port", 22))
    if ok:
        return E2EResult("Remote podman", True, ver or "installed")
    return E2EResult("Remote podman", False, "not installed")


def _check_remote_disk(env) -> E2EResult:
    """Check disk space on remote host."""
    if not env or not hasattr(env, "is_remote") or not env.is_remote:
        return E2EResult("Remote disk", True, "local env (skipped)")

    from taskfile.deploy_utils import check_remote_disk

    disk = check_remote_disk(env.ssh_host, env.ssh_user, getattr(env, "ssh_port", 22))
    if not disk or disk == "unknown":
        return E2EResult("Remote disk", False, "could not check")
    return E2EResult("Remote disk", True, f"{disk} free")


# ─── CLI command ─────────────────────────────────────────────────


@main.command(name="e2e")
@click.option("--check-only", is_flag=True, help="Validate config only, skip HTTP/container checks")
@click.option("--url", multiple=True, help="Additional HTTP URL(s) to check")
@click.option("--port-web", type=int, default=None, help="Web app port (default: from .env or 8000)")
@click.option("--port-landing", type=int, default=None, help="Landing port (default: from .env or 3000)")
@click.pass_context
def e2e_cmd(ctx, check_only, url, port_web, port_landing):
    """**🧪 End-to-end tests** for services and IaC.

Validates infrastructure-as-code and tests running services.

## Test layers

| Layer | What is tested |
|-------|----------------|
| IaC | Taskfile.yml, docker-compose.yml, quadlet units, .env |
| Tools | docker, docker compose, ssh available |
| SSH | Remote host connectivity (for remote envs) |
| Remote | Podman installed, disk space (for remote envs) |
| Services | Containers running, HTTP endpoints responding |

## Examples

```bash
# Full e2e test (local)
taskfile e2e

# Test production environment
taskfile --env prod e2e

# Config validation only (no HTTP)
taskfile e2e --check-only

# Test custom URL
taskfile e2e --url http://localhost:8000/health
```
"""
    opts = ctx.ensure_object(dict)
    results: list[E2EResult] = []

    # Load Taskfile
    try:
        config = load_taskfile(opts.get("taskfile_path"))
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    # Resolve target environment
    env_name = opts.get("env") or "local"
    env = config.environments.get(env_name) if config.environments else None
    is_remote = env and hasattr(env, "is_remote") and env.is_remote

    console.print(f"\n[bold]🧪 E2E Tests — {config.name or 'project'} ({env_name})[/]\n")

    # ─── Layer 1: IaC validation ─────────────────────────
    console.print("[bold dim]━━━ IaC Validation ━━━[/]")
    results.append(_check_taskfile_valid(config))
    results.append(_check_compose_file(config))
    results.append(_check_quadlet_files())
    env_file = getattr(env, "env_file", None) if env else None
    results.append(_check_env_file(env_file))

    # ─── Layer 2: Local tools ────────────────────────────
    console.print("[bold dim]━━━ Tools ━━━[/]")
    results.append(_check_local_tools())

    # ─── Layer 3: SSH + Remote ───────────────────────────
    if is_remote:
        console.print("[bold dim]━━━ Remote ━━━[/]")
        results.append(_check_ssh_connectivity(env))
        results.append(_check_remote_podman(env))
        results.append(_check_remote_disk(env))

    # ─── Layer 4: Services (unless --check-only) ─────────
    if not check_only:
        console.print("[bold dim]━━━ Services ━━━[/]")
        results.append(_check_containers_running(env, config))

        # Determine host for HTTP checks
        host = "localhost"
        if is_remote and env:
            host = env.ssh_host

        # Discover ports from .env or defaults
        from taskfile.deploy_utils import load_env_file as _load_env

        env_vars = _load_env(".env")
        web_port = port_web or int(env_vars.get("PORT_WEB", "8000"))
        landing_port = port_landing or int(env_vars.get("PORT_LANDING", "3000"))

        results.append(_check_http_endpoint(f"http://{host}:{web_port}/"))
        results.append(_check_http_endpoint(f"http://{host}:{landing_port}/"))

        # Additional URLs
        for extra_url in url:
            results.append(_check_http_endpoint(extra_url))

    # ─── Print results ───────────────────────────────────
    console.print()
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    for r in results:
        icon = r.icon
        duration = f" [{r.duration_ms}ms]" if r.duration_ms else ""
        console.print(f"  {icon} {r.name}: {r.detail}{duration}")

    console.print()
    if failed == 0:
        console.print(f"[bold green]✅ All {passed} checks passed[/]")
    else:
        console.print(f"[bold red]❌ {failed} failed[/], [green]{passed} passed[/]")
        sys.exit(1)
