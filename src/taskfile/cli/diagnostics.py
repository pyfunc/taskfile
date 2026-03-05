"""Project diagnostics and auto-fix functionality."""

from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich import box

from taskfile.compose import load_env_file, resolve_variables
from taskfile.parser import find_taskfile, load_taskfile, TaskfileNotFoundError

if TYPE_CHECKING:
    pass


console = Console()


class ProjectDiagnostics:
    """Diagnose and auto-fix common project issues."""

    def __init__(self):
        self.issues: list[tuple[str, str, bool]] = []  # (issue, severity, auto_fixable)
        self.fixed = 0
        self.port_fixes: dict[str, int] = {}

    def check_taskfile(self) -> bool:
        """Check if Taskfile.yml exists and is valid."""
        try:
            path = find_taskfile()
        except TaskfileNotFoundError:
            self.issues.append(("Taskfile.yml not found", "error", True))
            return False
        try:
            load_taskfile(path)
            return True
        except Exception as e:
            self.issues.append((f"Taskfile.yml parse error: {e}", "error", False))
            return False

    def check_env_files(self) -> None:
        """Check environment files."""
        for env_file in [".env", ".env.local", ".env.prod"]:
            if Path(env_file).exists():
                content = Path(env_file).read_text()
                if "OPENROUTER_API_KEY=" in content and "OPENROUTER_API_KEY=\n" in content:
                    self.issues.append((f"{env_file}: OPENROUTER_API_KEY is empty", "warning", True))

    def check_ports(self) -> None:
        """Check docker-compose port conflicts and suggest .env fixes."""
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            return

        try:
            compose = yaml.safe_load(compose_path.read_text()) or {}
        except Exception:
            return

        services = (compose or {}).get("services") or {}
        if not isinstance(services, dict):
            return

        env_path = Path(".env")
        env_vars = load_env_file(env_path) if env_path.exists() else {}
        ctx = {**os.environ, **env_vars}

        for svc_name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            ports = svc.get("ports") or []
            if not isinstance(ports, list):
                continue

            for port_entry in ports:
                if not isinstance(port_entry, str):
                    continue
                host_port, var_name = _parse_compose_host_port(port_entry)
                if host_port is None:
                    continue

                expanded = resolve_variables(str(host_port), ctx)
                try:
                    resolved_host_port = int(expanded)
                except ValueError:
                    continue

                if _is_port_free(resolved_host_port):
                    continue

                suggested = _find_free_port_near(resolved_host_port)
                if suggested is None:
                    continue

                key = var_name or f"PORT_{svc_name.upper()}"
                self.port_fixes[key] = suggested
                self.issues.append(
                    (
                        f"Port {resolved_host_port} for service '{svc_name}' is in use (set {key}={suggested})",
                        "warning",
                        True,
                    )
                )

    def check_docker(self) -> None:
        """Check if Docker is available."""
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.issues.append(("Docker not installed or not running", "warning", False))

    def check_ssh_keys(self) -> None:
        """Check SSH keys."""
        ssh_dir = Path.home() / ".ssh"
        if not ssh_dir.exists():
            self.issues.append(("~/.ssh directory not found", "error", True))
            return

        keys = list(ssh_dir.glob("id_*"))
        if not keys:
            self.issues.append(("No SSH keys found (~/.ssh/id_*)", "warning", False))

    def check_git(self) -> None:
        """Check if in git repo."""
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.issues.append(("Not a git repository", "info", True))

    def auto_fix(self) -> int:
        """Attempt to fix auto-fixable issues."""
        return self._fix_taskfile() + self._fix_git() + self._fix_api_keys() + self._fix_ports()

    def _fix_taskfile(self) -> int:
        """Fix missing Taskfile.yml."""
        fixed = 0
        for issue, severity, auto_fixable in self.issues[:]:
            if not auto_fixable or issue != "Taskfile.yml not found":
                continue
            if Confirm.ask("Create Taskfile.yml?", default=True):
                from taskfile.scaffold import generate_taskfile
                Path("Taskfile.yml").write_text(generate_taskfile("minimal"))
                console.print("[green]✓ Created Taskfile.yml[/]")
                fixed += 1
                self.issues.remove((issue, severity, auto_fixable))
        return fixed

    def _fix_git(self) -> int:
        """Fix missing git repository."""
        fixed = 0
        for issue, severity, auto_fixable in self.issues[:]:
            if not auto_fixable or issue != "Not a git repository":
                continue
            if Confirm.ask("Initialize git repository?", default=False):
                subprocess.run(["git", "init"], capture_output=True)
                console.print("[green]✓ Initialized git repository[/]")
                fixed += 1
                self.issues.remove((issue, severity, auto_fixable))
        return fixed

    def _fix_api_keys(self) -> int:
        """Fix empty API keys - shows instructions only."""
        for issue, severity, auto_fixable in self.issues[:]:
            if auto_fixable and ".env: OPENROUTER_API_KEY is empty" in issue:
                console.print("[yellow]⚠[/] Set OPENROUTER_API_KEY:")
                console.print("  1. Get key from https://openrouter.ai/settings/keys")
                console.print("  2. Add to .env: OPENROUTER_API_KEY=sk-or-v1-...")
        return 0

    def _fix_ports(self) -> int:
        """Fix port conflicts by stopping containers or updating .env."""
        if not self.port_fixes:
            return 0

        # Parse conflicting ports from issue strings
        conflict_ports: set[int] = set()
        for msg, _, _ in self.issues:
            if not (isinstance(msg, str) and msg.startswith("Port ") and " for service " in msg):
                continue
            m = re.match(r"^Port\s+(?P<port>\d+)\s+for service", msg)
            if m:
                conflict_ports.add(int(m.group("port")))

        fixed = 0
        stopped_any = self._stop_conflicting_containers(conflict_ports, fixed)

        if not stopped_any:
            fixed += self._update_env_with_free_ports()

        # Clear port fixes and remove port issues
        self.port_fixes.clear()
        for row in self.issues[:]:
            if row[0].startswith("Port ") and " is in use (set " in row[0]:
                self.issues.remove(row)

        return fixed

    def _stop_conflicting_containers(self, conflict_ports: set[int], fixed: int) -> bool:
        """Stop containers using conflicting ports. Returns True if any were stopped."""
        stopped_any = False
        for p in sorted(conflict_ports):
            containers = _docker_containers_using_port(p)
            if not containers:
                continue
            console.print(f"[yellow]Port {p} is published by:[/]")
            for c in containers:
                console.print(f"  {c['id']}  {c['name']}  {c['ports']}")
            if Confirm.ask(f"Stop {len(containers)} container(s) to free port {p}?", default=True):
                _docker_stop([c["id"] for c in containers])
                console.print(f"[green]✓[/] Stopped container(s) using port {p}")
                fixed += len(containers)
                stopped_any = True
        return stopped_any

    def _update_env_with_free_ports(self) -> int:
        """Update .env file with suggested free ports. Returns count of updates."""
        if not Confirm.ask("No containers stopped (or none found). Update .env with free ports?", default=True):
            console.print("[dim]No changes applied for port conflicts.[/]")
            return 0

        env_path = Path(".env")
        fixed = 0
        for key, port in sorted(self.port_fixes.items()):
            _upsert_env_value(env_path, key, str(port))
            console.print(f"[green]✓[/] Set {key}={port} in .env")
            fixed += 1
        return fixed

    def print_report(self) -> None:
        """Print diagnostic report."""
        if not self.issues:
            console.print(Panel(
                "[bold green]✓ All checks passed![/]\n"
                "Your project is ready to use.",
                border_style="green"
            ))
            return

        table = Table(title="Project Diagnostics", box=box.ROUNDED)
        table.add_column("Issue", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Auto-fix", style="cyan")

        for issue, severity, auto_fixable in self.issues:
            severity_style = {"error": "[red]●[/]", "warning": "[yellow]●[/]", "info": "[blue]ℹ[/]"}.get(severity, "●")
            fix_status = "[green]Yes[/]" if auto_fixable else "[dim]No[/]"
            table.add_row(issue, f"{severity_style} {severity}", fix_status)

        console.print(table)


def _parse_compose_host_port(port_entry: str) -> tuple[str | None, str | None]:
    """Parse a docker-compose ports entry and return (host_port_expr, var_name).

    Supports common forms:
        - "8000:8000"
        - "127.0.0.1:8000:8000"
        - "${PORT_WEB:-8000}:8000"
        - "127.0.0.1:${PORT_WEB:-8000}:8000"
        - "8000:8000/tcp"

    Returns:
        host_port_expr: string expression for host port (may include ${VAR:-default})
        var_name: extracted VAR name if host_port_expr is ${VAR...}
    """
    entry = port_entry.strip()
    if not entry:
        return None, None

    # Drop protocol suffix
    entry = entry.split("/", 1)[0]
    parts = entry.split(":")
    if len(parts) < 2:
        return None, None

    # last part is container port; host port is either parts[-2] or parts[-3] (if ip present)
    host_port_expr = parts[-2]
    var_name: str | None = None
    m = re.match(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)", host_port_expr)
    if m:
        var_name = m.group("name")
    return host_port_expr, var_name


def _is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    """Return True if TCP port appears to be free for binding on the local host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False


def _find_free_port_near(start_port: int, span: int = 50) -> int | None:
    """Find a free TCP port near start_port (inclusive)."""
    for p in range(start_port, start_port + span + 1):
        if _is_port_free(p):
            return p
    for p in range(max(1024, start_port - span), start_port):
        if _is_port_free(p):
            return p
    return None


def _upsert_env_value(env_path: Path, key: str, value: str) -> None:
    """Upsert KEY=value into env file, preserving other lines and comments."""
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n")
        return

    lines = env_path.read_text().splitlines(True)
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    updated = False
    new_lines: list[str] = []

    for line in lines:
        if key_re.match(line):
            # Preserve newline style from existing line
            newline = "\n" if not line.endswith("\r\n") else "\r\n"
            new_lines.append(f"{key}={value}{newline}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        new_lines.append(f"{key}={value}\n")

    env_path.write_text("".join(new_lines))


def _docker_containers_using_port(port: int) -> list[dict[str, str]]:
    """Return running docker containers that publish the given host port."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Ports}}"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return []

    containers: list[dict[str, str]] = []
    # Example ports: "0.0.0.0:8002->8002/tcp, [::]:8002->8002/tcp"
    token = f":{int(port)}->"
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        cid, name, ports = parts[0], parts[1], parts[2]
        if token in (ports or ""):
            containers.append({"id": cid, "name": name, "ports": ports})
    return containers


def _docker_stop(container_ids: list[str]) -> None:
    """Stop docker containers by ID."""
    if not container_ids:
        return
    subprocess.run(["docker", "stop", *container_ids], text=True)
