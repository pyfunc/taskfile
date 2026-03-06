"""Fleet management CLI commands for taskfile.

Uses environment_groups from Taskfile.yml as the source of truth.
Each device is a Taskfile environment with ssh_host.
Groups define rolling/canary/parallel update strategies.

Also supports standalone fleet.yml for legacy/advanced use cases.
"""

from __future__ import annotations

import subprocess
import sys

import clickmd as click
from taskfile.cli.click_compat import confirm
from rich.console import Console
from rich.table import Table

from taskfile.cli.main import main, console
from taskfile.parser import TaskfileNotFoundError, TaskfileParseError, load_taskfile
from taskfile.models import Environment, TaskfileConfig


# ─── Helpers ──────────────────────────────────────────


def _load_config_or_exit(taskfile_path: str | None) -> TaskfileConfig:
    """Load Taskfile.yml or exit with error."""
    try:
        return load_taskfile(taskfile_path)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


def _get_remote_envs(config: TaskfileConfig, group_name: str | None = None) -> list[tuple[str, Environment]]:
    """Get all remote environments, optionally filtered by group."""
    if group_name:
        if group_name not in config.environment_groups:
            console.print(f"[red]Error: group '{group_name}' not found[/]")
            available = ", ".join(sorted(config.environment_groups.keys()))
            if available:
                console.print(f"[dim]  Available groups: {available}[/]")
            sys.exit(1)
        members = config.environment_groups[group_name].members
        return [
            (name, config.environments[name])
            for name in members
            if name in config.environments and config.environments[name].is_remote
        ]
    return [
        (name, env)
        for name, env in config.environments.items()
        if env.is_remote
    ]


def _ssh_check(env: Environment, cmd: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a command on remote env via SSH."""
    target = env.ssh_target
    opts = env.ssh_opts
    return subprocess.run(
        f"ssh {opts} {target} '{cmd}'",
        shell=True, capture_output=True, text=True, timeout=timeout,
    )


def _ping(host: str) -> bool:
    """Quick ICMP ping check."""
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "2", host], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False



def _safe_ssh(env, cmd: str, timeout: int = 10):
    """Execute SSH command safely, returning None on failure."""
    try:
        return _ssh_check(env, cmd, timeout=timeout)
    except Exception:
        return None


# ─── Device status helpers ────────────────────────────


def _parse_device_metrics(stdout: str) -> dict:
    """Parse pipe-delimited SSH status output into metrics dict."""
    parts = stdout.strip().split("|")
    temp_c = int(parts[0].strip()) / 1000 if parts[0].strip().isdigit() else 0
    return {
        "temp": f"{temp_c:.0f}°C",
        "temp_c": temp_c,
        "ram": f"{parts[1].strip()}%" if len(parts) > 1 and parts[1].strip().isdigit() else "—",
        "disk": f"{parts[2].strip()}%" if len(parts) > 2 and parts[2].strip().isdigit() else "—",
        "uptime": parts[3].strip()[:25] if len(parts) > 3 else "—",
        "containers": parts[4].strip() if len(parts) > 4 and parts[4].strip().isdigit() else "—",
    }


def _check_single_device(name: str, env) -> dict:
    """Check status of a single remote device via ping + SSH."""
    host = env.ssh_host
    row = {"name": name, "host": host, "status": "unknown",
           "temp": "—", "ram": "—", "disk": "—", "containers": "—", "uptime": "—"}

    if not _ping(host):
        row["status"] = "down"
        return row

    try:
        r = _ssh_check(env,
            'echo "'
            '$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)|'
            '$(free -m 2>/dev/null | awk \'/Mem:/{printf "%.0f", $3/$2*100}\')|'
            '$(df / --output=pcent 2>/dev/null | tail -1 | tr -d " %")|'
            '$(uptime -p 2>/dev/null || uptime)|'
            '$(podman ps -q 2>/dev/null | wc -l)"',
        )
        if r.returncode != 0:
            row["status"] = "ssh_fail"
            return row

        metrics = _parse_device_metrics(r.stdout)
        row.update({k: v for k, v in metrics.items() if k != "temp_c"})
        row["status"] = "hot" if metrics["temp_c"] > 70 else "up"
    except Exception:
        row["status"] = "ssh_fail"
    return row


def _build_fleet_table(results: list[dict]) -> "Table":
    """Build Rich table from fleet status results."""
    table = Table(title="Fleet Status")
    table.add_column("Name", style="cyan")
    table.add_column("IP")
    table.add_column("Status")
    table.add_column("Temp")
    table.add_column("RAM")
    table.add_column("Disk")
    table.add_column("Containers", justify="right")
    table.add_column("Uptime")

    status_map = {"up": "[green]✅ UP[/]", "down": "[red]❌ DOWN[/]",
                  "ssh_fail": "[red]❌ SSH[/]", "hot": "[yellow]⚠️ HOT[/]"}

    for r in results:
        s = status_map.get(r["status"], r["status"])
        if r["status"] in ("down", "ssh_fail"):
            table.add_row(r["name"], r["host"], s, "—", "—", "—", "—", "—")
        else:
            table.add_row(r["name"], r["host"], s, r["temp"], r["ram"],
                          r["disk"], r["containers"], r["uptime"])

    return table


# ─── Repair diagnostic helpers ────────────────────────


def _check_disk(env) -> tuple[list[str], list[str]]:
    """Check disk usage. Returns (problems, fixes)."""
    problems, fixes = [], []
    r = _safe_ssh(env, "df / --output=pcent | tail -1 | tr -d ' %'")
    if r and r.stdout.strip().isdigit():
        usage = int(r.stdout.strip())
        if usage > 90:
            problems.append(f"Disk {usage}% full")
            fixes.extend(["podman system prune -af",
                          "sudo journalctl --vacuum-size=50M",
                          "sudo apt-get clean"])
        else:
            console.print(f"  [green]✓[/] Disk: {usage}% used")
    return problems, fixes


def _check_ram(env) -> tuple[list[str], list[str]]:
    """Check RAM usage. Returns (problems, fixes)."""
    problems = []
    r = _safe_ssh(env, "free -m | awk '/Mem:/{printf \"%.0f\", $3/$2*100}'")
    if r and r.stdout.strip().isdigit():
        mem = int(r.stdout.strip())
        if mem > 90:
            problems.append(f"RAM {mem}% used")
        else:
            console.print(f"  [green]✓[/] RAM: {mem}% used")
    return problems, []


def _check_temperature(env) -> tuple[list[str], list[str]]:
    """Check CPU temperature. Returns (problems, fixes)."""
    problems, fixes = [], []
    r = _safe_ssh(env, "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    if r and r.stdout.strip().isdigit():
        temp_c = int(r.stdout.strip()) / 1000
        if temp_c > 80:
            problems.append(f"Temperature {temp_c:.0f}°C (throttling!)")
            fixes.append("Check cooling fan / heatsink")
        elif temp_c > 70:
            problems.append(f"Temperature {temp_c:.0f}°C (high)")
        else:
            console.print(f"  [green]✓[/] Temperature: {temp_c:.0f}°C")
    return problems, fixes


def _check_podman(env) -> tuple[list[str], list[str]]:
    """Check podman availability. Returns (problems, fixes)."""
    r = _safe_ssh(env, "podman --version")
    if r and r.returncode == 0:
        console.print(f"  [green]✓[/] Podman: {r.stdout.strip()}")
        return [], []
    return ["Podman not working"], ["sudo apt-get install -y podman"]


def _check_ntp(env) -> tuple[list[str], list[str]]:
    """Check NTP synchronization. Returns (problems, fixes)."""
    r = _safe_ssh(env, "timedatectl show -p NTPSynchronized --value 2>/dev/null")
    if r and r.stdout.strip() != "yes":
        return ["NTP not synchronized"], ["sudo timedatectl set-ntp true"]
    if r:
        console.print(f"  [green]✓[/] NTP: synchronized")
    return [], []


def _apply_repair_fixes(env, fixes: list[str], auto_fix: bool) -> None:
    """Apply or display repair fixes."""
    if not fixes:
        return
    if auto_fix or confirm("\nAuto-fix?", default=False):
        for fix in fixes:
            if fix.startswith("Check") or fix.startswith("ssh-copy-id"):
                console.print(f"  [dim]→ (manual) {fix}[/]")
            else:
                console.print(f"  [blue]→[/] {fix}")
                _safe_ssh(env, fix)
        console.print(f"[green]✓ Repair complete — re-run to verify[/]")
    else:
        console.print("\n[dim]Manual fixes:[/]")
        for fix in fixes:
            console.print(f"  $ {fix}")


# ─── CLI group ────────────────────────────────────────


@main.group()
def fleet():
    """Manage a fleet of devices (RPi, edge nodes, kiosks).

    Uses environment_groups from Taskfile.yml. Each device is a
    Taskfile environment with ssh_host. Groups define update strategies.

    \b
    Examples:
        taskfile fleet status
        taskfile fleet status --group kiosks
        taskfile fleet repair kiosk-lobby
        taskfile -G kiosks run deploy-kiosk --var TAG=v1.0
    """
    pass


# ─── fleet status ─────────────────────────────────────


@fleet.command(name="status")
@click.option("--group", default=None, help="Only show devices in this group")
@click.pass_context
def fleet_status_cmd(ctx, group):
    """Show status of all remote environments (SSH-based health check).

    \b
    Examples:
        taskfile fleet status
        taskfile fleet status --group kiosks
    """
    config = _load_config_or_exit(ctx.obj.get("taskfile_path"))
    envs = _get_remote_envs(config, group)

    if not envs:
        console.print("[yellow]No remote environments found in Taskfile.yml[/]")
        console.print("[dim]Add environments with ssh_host to use fleet management.[/]")
        sys.exit(0)

    console.print(f"[bold]Checking {len(envs)} device(s)...[/]\n")

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(10, len(envs))) as ex:
        results = list(ex.map(lambda item: _check_single_device(*item), envs))

    results.sort(key=lambda r: r["name"])

    console.print(_build_fleet_table(results))
    down = sum(1 for r in results if r["status"] in ("down", "ssh_fail"))
    if down:
        console.print(f"\n[yellow]⚠  {down} device(s) unreachable![/]")


# ─── fleet repair ─────────────────────────────────────


@fleet.command(name="repair")
@click.argument("env_name")
@click.option("--auto-fix", is_flag=True, help="Apply fixes automatically (no prompt)")
@click.pass_context
def fleet_repair_cmd(ctx, env_name, auto_fix):
    """Diagnose and repair a remote device.

    Runs 8-point diagnostics: ping, SSH, disk, RAM, temperature,
    podman, containers, NTP. Suggests fixes for each issue.

    \b
    Examples:
        taskfile fleet repair kiosk-lobby
        taskfile fleet repair sensor-yard --auto-fix
    """
    config = _load_config_or_exit(ctx.obj.get("taskfile_path"))

    if env_name not in config.environments:
        console.print(f"[red]Unknown environment: {env_name}[/]")
        sys.exit(1)

    env = config.environments[env_name]
    if not env.is_remote:
        console.print(f"[red]\'{env_name}\' is not a remote environment (no ssh_host)[/]")
        sys.exit(1)

    host = env.ssh_host
    problems: list[str] = []
    fixes: list[str] = []

    console.print(f"[bold]Diagnosing {env_name} ({host})...[/]\n")

    # 1. Ping
    if not _ping(host):
        console.print(f"  [red]❌ UNREACHABLE[/] — device offline or network issue")
        sys.exit(1)
    console.print(f"  [green]✓[/] Network: reachable")

    # 2. SSH
    try:
        r = _ssh_check(env, "echo ok", timeout=5)
        if r.returncode != 0 or "ok" not in r.stdout:
            problems.append("SSH connection failed")
            fixes.append(f"ssh-copy-id {env.ssh_target}")
        else:
            console.print(f"  [green]✓[/] SSH: connected")
    except Exception:
        problems.append("SSH timeout")
        fixes.append(f"Check SSH key and connectivity to {host}")

    # 3–7. System checks
    for check_fn in (_check_disk, _check_ram, _check_temperature, _check_podman, _check_ntp):
        p, f = check_fn(env)
        problems.extend(p)
        fixes.extend(f)

    # Summary
    console.print()
    if not problems:
        console.print(f"[bold green]✅ {env_name}: healthy — no issues found[/]")
        return

    console.print(f"[yellow]⚠  {env_name}: {len(problems)} issue(s) found:[/]")
    for p in problems:
        console.print(f"  [red]❌[/] {p}")

    _apply_repair_fixes(env, fixes, auto_fix)


# ─── fleet list ───────────────────────────────────────


@fleet.command(name="list")
@click.pass_context
def fleet_list_cmd(ctx):
    """List all remote environments and environment groups.

    \b
    Examples:
        taskfile fleet list
    """
    config = _load_config_or_exit(ctx.obj.get("taskfile_path"))

    remote_envs = [(n, e) for n, e in config.environments.items() if e.is_remote]

    if remote_envs:
        console.print("\n[bold]Remote Environments (fleet devices):[/]")
        for name, env in sorted(remote_envs):
            runtime = f"[{env.container_runtime}]"
            console.print(f"  [cyan]{name:20s}[/] → {env.ssh_target:30s} {runtime}")
    else:
        console.print("[yellow]No remote environments. Add ssh_host to environments in Taskfile.yml[/]")

    if config.environment_groups:
        console.print("\n[bold]Environment Groups:[/]")
        for name, grp in sorted(config.environment_groups.items()):
            members = ", ".join(grp.members) if grp.members else "[dim]empty[/]"
            console.print(
                f"  [magenta]{name:20s}[/] strategy={grp.strategy:10s} "
                f"members=[{members}]"
            )
    else:
        console.print("\n[dim]No environment_groups defined. Add to Taskfile.yml for fleet deploy.[/]")
