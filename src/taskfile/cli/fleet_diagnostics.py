"""Fleet diagnostics for remote device health checks."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Callable

import click
from rich.console import Console

console = Console()


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic check."""
    name: str
    passed: bool
    message: str = ""
    problem: str = ""
    fix: str = ""
    value: str = ""


@dataclass
class DiagnosticsReport:
    """Complete diagnostics report for a device."""
    host: str
    env_name: str
    results: list[DiagnosticResult] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)

    @property
    def passed_checks(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_checks(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def is_healthy(self) -> bool:
        return not self.problems


def _safe_ssh(env, cmd: str, timeout: int = 10) -> subprocess.CompletedProcess | None:
    """Execute SSH command safely, returning None on failure."""
    from taskfile.cli.fleet import _ssh_check
    try:
        return _ssh_check(env, cmd, timeout=timeout)
    except Exception:
        return None


def check_ping(host: str, ping_fn: Callable[[str], bool]) -> DiagnosticResult:
    """Check if host is reachable via ping."""
    if ping_fn(host):
        return DiagnosticResult(name="Network", passed=True, message="reachable")
    return DiagnosticResult(
        name="Network",
        passed=False,
        problem="Device unreachable",
        message="device offline or network issue"
    )


def check_ssh(env, ssh_fn: Callable) -> DiagnosticResult:
    """Check SSH connectivity."""
    try:
        r = ssh_fn(env, "echo ok", timeout=5)
        if r and r.returncode == 0 and "ok" in r.stdout:
            return DiagnosticResult(name="SSH", passed=True, message="connected")
        return DiagnosticResult(
            name="SSH",
            passed=False,
            problem="SSH connection failed",
            fix=f"ssh-copy-id {env.ssh_target}"
        )
    except Exception:
        return DiagnosticResult(
            name="SSH",
            passed=False,
            problem="SSH timeout",
            fix=f"Check SSH key and connectivity to {env.ssh_host}"
        )


def check_disk(env, ssh_fn: Callable) -> DiagnosticResult:
    """Check disk usage."""
    r = ssh_fn(env, "df / --output=pcent | tail -1 | tr -d ' %'")
    if not r or not r.stdout.strip().isdigit():
        return DiagnosticResult(name="Disk", passed=False, problem="Disk check failed")

    usage = int(r.stdout.strip())
    if usage > 90:
        return DiagnosticResult(
            name="Disk",
            passed=False,
            problem=f"Disk {usage}% full",
            fix="podman system prune -af && sudo journalctl --vacuum-size=50M && sudo apt-get clean",
            value=f"{usage}%"
        )
    return DiagnosticResult(name="Disk", passed=True, value=f"{usage}% used")


def check_ram(env, ssh_fn: Callable) -> DiagnosticResult:
    """Check RAM usage."""
    r = ssh_fn(env, "free -m | awk '/Mem:/{printf \"%.0f\", $3/$2*100}'")
    if not r or not r.stdout.strip().isdigit():
        return DiagnosticResult(name="RAM", passed=False, problem="RAM check failed")

    mem = int(r.stdout.strip())
    if mem > 90:
        return DiagnosticResult(
            name="RAM",
            passed=False,
            problem=f"RAM {mem}% used",
            value=f"{mem}%"
        )
    return DiagnosticResult(name="RAM", passed=True, value=f"{mem}% used")


def check_temperature(env, ssh_fn: Callable) -> DiagnosticResult:
    """Check CPU temperature."""
    r = ssh_fn(env, "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    if not r or not r.stdout.strip().isdigit():
        return DiagnosticResult(name="Temperature", passed=False)

    temp_c = int(r.stdout.strip()) / 1000
    if temp_c > 80:
        return DiagnosticResult(
            name="Temperature",
            passed=False,
            problem=f"Temperature {temp_c:.0f}°C (throttling!)",
            fix="Check cooling fan / heatsink",
            value=f"{temp_c:.0f}°C"
        )
    elif temp_c > 70:
        return DiagnosticResult(
            name="Temperature",
            passed=False,
            problem=f"Temperature {temp_c:.0f}°C (high)",
            value=f"{temp_c:.0f}°C"
        )
    return DiagnosticResult(name="Temperature", passed=True, value=f"{temp_c:.0f}°C")


def check_podman(env, ssh_fn: Callable) -> DiagnosticResult:
    """Check if Podman is installed and working."""
    r = ssh_fn(env, "podman --version")
    if r and r.returncode == 0:
        return DiagnosticResult(name="Podman", passed=True, value=r.stdout.strip())
    return DiagnosticResult(
        name="Podman",
        passed=False,
        problem="Podman not working",
        fix="sudo apt-get install -y podman"
    )


def check_ntp(env, ssh_fn: Callable) -> DiagnosticResult:
    """Check NTP synchronization status."""
    r = ssh_fn(env, "timedatectl show -p NTPSynchronized --value 2>/dev/null")
    if r and r.stdout.strip() == "yes":
        return DiagnosticResult(name="NTP", passed=True, message="synchronized")
    return DiagnosticResult(
        name="NTP",
        passed=False,
        problem="NTP not synchronized",
        fix="sudo timedatectl set-ntp true"
    )


def run_diagnostics(env, host: str, env_name: str, ping_fn, ssh_fn) -> DiagnosticsReport:
    """Run all diagnostic checks and return a report."""
    report = DiagnosticsReport(host=host, env_name=env_name)

    # Run all checks
    checks = [
        check_ping(host, ping_fn),
        check_ssh(env, ssh_fn),
        check_disk(env, ssh_fn),
        check_ram(env, ssh_fn),
        check_temperature(env, ssh_fn),
        check_podman(env, ssh_fn),
        check_ntp(env, ssh_fn),
    ]

    for result in checks:
        report.results.append(result)
        if not result.passed:
            if result.problem:
                report.problems.append(result.problem)
            if result.fix:
                report.fixes.append(result.fix)

    return report


def print_diagnostics_report(report: DiagnosticsReport) -> None:
    """Print the diagnostics report to console."""
    for result in report.results:
        if result.passed:
            if result.value:
                console.print(f"  [green]✓[/] {result.name}: {result.value}")
            else:
                console.print(f"  [green]✓[/] {result.name}: {result.message or 'ok'}")


def print_diagnostics_summary(report: DiagnosticsReport) -> None:
    """Print summary of diagnostics."""
    console.print()
    if report.is_healthy:
        console.print(f"[bold green]✅ {report.env_name}: healthy — no issues found[/]")
        return

    console.print(f"[yellow]⚠  {report.env_name}: {len(report.problems)} issue(s) found:[/]")
    for p in report.problems:
        console.print(f"  [red]❌[/] {p}")


def apply_fixes(report: DiagnosticsReport, auto_fix: bool) -> bool:
    """Apply fixes interactively or automatically. Returns True if any fixes were applied."""
    if not report.fixes:
        return False

    if not auto_fix and not click.confirm("\nAuto-fix?", default=False):
        console.print("\n[dim]Manual fixes:[/]")
        for fix in report.fixes:
            console.print(f"  $ {fix}")
        return False

    applied = 0
    for fix in report.fixes:
        if fix.startswith("Check") or fix.startswith("ssh-copy-id"):
            console.print(f"  [dim]→ (manual) {fix}[/]")
        else:
            console.print(f"  [blue]→[/] {fix}")
            # Execute via SSH
            from taskfile.cli.fleet import _ssh_check
            try:
                _ssh_check(None, fix, timeout=30)  # env will be handled separately
                applied += 1
            except Exception as e:
                console.print(f"  [red]Failed: {e}[/]")

    if applied > 0:
        console.print(f"[green]✓ Repair complete — re-run to verify[/]")
    return applied > 0
