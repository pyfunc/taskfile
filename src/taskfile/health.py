"""Health check framework for Taskfile deployments.

Provides endpoint monitoring and service health verification.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    pass

console = Console()

try:
    from fixop.health import (
        check_http_endpoint as _fixop_check_http,
        check_ssh_service as _fixop_check_ssh,
    )

    _HAS_FIXOP_HEALTH = True
except ImportError:
    _HAS_FIXOP_HEALTH = False


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    url: str
    status: str  # "healthy", "unhealthy", "unknown"
    status_code: int | None = None
    response_time_ms: float = 0.0
    error: str | None = None


@dataclass
class HealthReport:
    """Aggregated health check report."""

    overall: str  # "healthy", "degraded", "unhealthy"
    checks: list[HealthCheckResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "healthy")

    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "unhealthy")


def _unhealthy_result(
    name: str, url: str, start: float, error: str, status_code: int | None = None
) -> HealthCheckResult:
    """Build an unhealthy HealthCheckResult."""
    return HealthCheckResult(
        name=name,
        url=url,
        status="unhealthy",
        status_code=status_code,
        response_time_ms=(time.time() - start) * 1000,
        error=error,
    )


def _from_fixop_result(fr) -> HealthCheckResult:
    """Convert fixop HealthCheckResult to taskfile HealthCheckResult."""
    return HealthCheckResult(
        name=fr.name,
        url=fr.url,
        status=fr.status,
        status_code=fr.status_code,
        response_time_ms=fr.response_time_ms,
        error=fr.error,
    )


def check_http_endpoint(
    name: str,
    url: str,
    expected_status: int = 200,
    timeout: int = 10,
    retries: int = 1,
) -> HealthCheckResult:
    """Check HTTP endpoint health.

    Delegates to fixop.health when available.

    Args:
        name: Service name for display
        url: URL to check
        expected_status: Expected HTTP status code
        timeout: Request timeout in seconds
        retries: Number of retry attempts

    Returns:
        HealthCheckResult with status details
    """
    if _HAS_FIXOP_HEALTH:
        return _from_fixop_result(_fixop_check_http(name, url, expected_status, timeout, retries))

    return _check_http_endpoint_legacy(name, url, expected_status, timeout, retries)


def _check_http_endpoint_legacy(
    name: str,
    url: str,
    expected_status: int = 200,
    timeout: int = 10,
    retries: int = 1,
) -> HealthCheckResult:
    """Legacy HTTP check — used when fixop is not available."""
    start = time.time()

    for attempt in range(retries):
        try:
            req = Request(url, method="GET", headers={"User-Agent": "Taskfile-Health-Check/1.0"})
            response = urlopen(req, timeout=timeout)
            (time.time() - start) * 1000

            status_code = response.getcode()
            if status_code == expected_status:
                return HealthCheckResult(
                    name=name,
                    url=url,
                    status="healthy",
                    status_code=status_code,
                    response_time_ms=(time.time() - start) * 1000,
                )
            if attempt == retries - 1:
                return _unhealthy_result(
                    name, url, start, f"Unexpected status: {status_code}", status_code
                )
            time.sleep(1)

        except HTTPError as e:
            if attempt == retries - 1:
                return _unhealthy_result(name, url, start, f"HTTP error: {e.code}", e.code)
            time.sleep(1)

        except URLError as e:
            if attempt == retries - 1:
                reason = str(e.reason) if hasattr(e, "reason") else str(e)
                return _unhealthy_result(name, url, start, f"Connection error: {reason[:50]}")
            time.sleep(1)

        except Exception as e:
            if attempt == retries - 1:
                return _unhealthy_result(name, url, start, f"Error: {str(e)[:50]}")
            time.sleep(1)

    return HealthCheckResult(
        name=name,
        url=url,
        status="unknown",
        error="Unknown error",
    )


def check_ssh_service(
    name: str,
    host: str,
    user: str,
    ssh_key: str | None = None,
    port: int = 22,
    timeout: int = 10,
) -> HealthCheckResult:
    """Check SSH service availability.

    Delegates to fixop.health when available.

    Args:
        name: Service name for display
        host: SSH host
        user: SSH user
        ssh_key: Path to SSH private key
        port: SSH port
        timeout: Connection timeout

    Returns:
        HealthCheckResult with status details
    """
    if _HAS_FIXOP_HEALTH:
        return _from_fixop_result(_fixop_check_ssh(name, host, user, ssh_key, port, timeout))

    return _check_ssh_service_legacy(name, host, user, ssh_key, port, timeout)


def _check_ssh_service_legacy(
    name: str,
    host: str,
    user: str,
    ssh_key: str | None = None,
    port: int = 22,
    timeout: int = 10,
) -> HealthCheckResult:
    """Legacy SSH check — used when fixop is not available."""
    start = time.time()

    opts = f"-p {port}"
    if ssh_key:
        opts += f" -i {ssh_key}"
    opts += " -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5"

    cmd = f"ssh {opts} {user}@{host} 'echo healthy'"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (time.time() - start) * 1000

        if result.returncode == 0 and "healthy" in result.stdout:
            return HealthCheckResult(
                name=name,
                url=f"ssh://{user}@{host}:{port}",
                status="healthy",
                response_time_ms=elapsed,
            )
        else:
            return HealthCheckResult(
                name=name,
                url=f"ssh://{user}@{host}:{port}",
                status="unhealthy",
                response_time_ms=elapsed,
                error=f"SSH failed: {result.stderr[:100]}",
            )
    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start) * 1000
        return HealthCheckResult(
            name=name,
            url=f"ssh://{user}@{host}:{port}",
            status="unhealthy",
            response_time_ms=elapsed,
            error="SSH connection timeout",
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return HealthCheckResult(
            name=name,
            url=f"ssh://{user}@{host}:{port}",
            status="unhealthy",
            response_time_ms=elapsed,
            error=f"SSH error: {str(e)[:50]}",
        )


def check_traefik_dashboard(
    host: str,
    user: str,
    ssh_key: str | None = None,
) -> HealthCheckResult:
    """Check Traefik dashboard via SSH tunnel.

    Args:
        host: SSH host
        user: SSH user
        ssh_key: Path to SSH private key

    Returns:
        HealthCheckResult with status details
    """
    start = time.time()

    opts = ""
    if ssh_key:
        opts += f"-i {ssh_key} "
    opts += "-o StrictHostKeyChecking=accept-new"

    # Check if Traefik ping endpoint responds
    cmd = f"ssh {opts} {user}@{host} 'curl -sf http://localhost:8080/ping && echo OK'"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        elapsed = (time.time() - start) * 1000

        if result.returncode == 0 and "OK" in result.stdout:
            return HealthCheckResult(
                name="Traefik",
                url=f"http://localhost:8080 (via {host})",
                status="healthy",
                response_time_ms=elapsed,
            )
        else:
            return HealthCheckResult(
                name="Traefik",
                url=f"http://localhost:8080 (via {host})",
                status="unhealthy",
                response_time_ms=elapsed,
                error="Traefik ping failed",
            )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return HealthCheckResult(
            name="Traefik",
            url=f"http://localhost:8080 (via {host})",
            status="unhealthy",
            response_time_ms=elapsed,
            error=str(e)[:50],
        )


def run_health_checks(
    domain: str,
    ssh_host: str | None = None,
    ssh_user: str = "deploy",
    ssh_key: str | None = None,
    check_web: bool = True,
    check_landing: bool = True,
    check_api: bool = False,
    api_path: str = "/api/health",
    verbose: bool = False,
) -> HealthReport:
    """Run comprehensive health checks for deployed services.

    Args:
        domain: Main domain name
        ssh_host: SSH host (defaults to domain)
        ssh_user: SSH user for remote checks
        ssh_key: SSH key path
        check_web: Check web app at app.domain
        check_landing: Check landing page
        check_api: Check API endpoint
        api_path: API health endpoint path
        verbose: Print detailed output

    Returns:
        HealthReport with all check results
    """
    checks: list[HealthCheckResult] = []

    # Landing page check
    if check_landing:
        result = check_http_endpoint("Landing", f"https://{domain}")
        checks.append(result)

    # Web app check
    if check_web:
        result = check_http_endpoint("Web App", f"https://app.{domain}")
        checks.append(result)

    # API check
    if check_api:
        result = check_http_endpoint("API", f"https://api.{domain}{api_path}")
        checks.append(result)

    # SSH check
    if ssh_host:
        result = check_ssh_service("SSH", ssh_host, ssh_user, ssh_key)
        checks.append(result)

        # Traefik check (requires SSH)
        result = check_traefik_dashboard(ssh_host, ssh_user, ssh_key)
        checks.append(result)

    # Determine overall status
    unhealthy = sum(1 for c in checks if c.status == "unhealthy")
    healthy = sum(1 for c in checks if c.status == "healthy")

    if unhealthy == 0:
        overall = "healthy"
    elif healthy > unhealthy:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return HealthReport(overall=overall, checks=checks)


def print_health_report(report: HealthReport) -> None:
    """Print formatted health report to console."""
    # Overall status
    status_color = {
        "healthy": "green",
        "degraded": "yellow",
        "unhealthy": "red",
    }.get(report.overall, "white")

    console.print(
        f"\n[bold]Health Status: [{status_color}]{report.overall.upper()}[/{status_color}][/]"
    )
    console.print(f"[dim]{report.healthy_count}/{len(report.checks)} checks passed[/]")

    # Table of checks
    table = Table(show_header=True, header_style="bold")
    table.add_column("Service")
    table.add_column("URL")
    table.add_column("Status")
    table.add_column("Response")
    table.add_column("Error")

    for check in report.checks:
        status_style = {
            "healthy": "green",
            "unhealthy": "red",
            "unknown": "yellow",
        }.get(check.status, "white")

        status_icon = "✓" if check.status == "healthy" else "✗"
        response = (
            f"{check.status_code}" if check.status_code else f"{check.response_time_ms:.0f}ms"
        )

        table.add_row(
            check.name,
            check.url[:40],
            f"[{status_style}]{status_icon} {check.status}[/{status_style}]",
            response,
            check.error or "",
        )

    console.print(table)


def health_check_all(
    domain: str,
    ssh_host: str | None = None,
    ssh_user: str = "deploy",
    ssh_key: str | None = None,
    exit_on_error: bool = True,
) -> bool:
    """Run all health checks and print report.

    Args:
        domain: Domain name
        ssh_host: SSH host
        ssh_user: SSH user
        ssh_key: SSH key path
        exit_on_error: Exit with error code if unhealthy

    Returns:
        True if all checks passed
    """
    report = run_health_checks(
        domain=domain,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_key=ssh_key,
    )

    print_health_report(report)

    success = report.overall == "healthy"
    if not success and exit_on_error:
        sys.exit(1)
    return success
