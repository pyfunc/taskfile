"""Pyqual integration — code quality checks with auto-fix support.

This module bridges pyqual (quality analyzer) with taskfile diagnostics system,
converting pyqual findings into Issue objects with appropriate FixStrategy.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)

if TYPE_CHECKING:
    pass


def _run_pyqual_gates(project_path: Path | None = None) -> dict | None:
    """Run pyqual gates check for quick quality metrics.

    Returns dict with gates status or None if pyqual fails.
    Uses 'gates' command which is fast vs 'run' which analyzes all files.
    """
    try:
        cmd = [sys.executable, "-m", "pyqual", "gates"]
        if project_path:
            cmd.extend(["--path", str(project_path)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Parse the text table output
        # Format: │ Status │ Metric │ Value │ Threshold │
        passed = []
        failed = []
        for line in result.stdout.splitlines():
            parts = line.split("│")
            if len(parts) >= 4:
                status = parts[1].strip()
                metric = parts[2].strip()
                value = parts[3].strip()

                if status in ("✅", "✓"):
                    passed.append(metric)
                elif status in ("❌", "✗"):
                    failed.append({"metric": metric, "value": value})

        return {
            "passed": passed,
            "failed": failed,
            "all_passed": len(failed) == 0,
            "raw_output": result.stdout,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _map_pyqual_severity(pyqual_severity: str) -> str:
    """Map pyqual severity to taskfile severity."""
    mapping = {
        "critical": SEVERITY_ERROR,
        "high": SEVERITY_ERROR,
        "medium": SEVERITY_WARNING,
        "low": SEVERITY_INFO,
    }
    return mapping.get(pyqual_severity.lower(), SEVERITY_WARNING)


def _categorize_pyqual_issue(pyqual_finding: dict) -> IssueCategory:
    """Categorize pyqual finding into IssueCategory."""
    category = pyqual_finding.get("category", "").lower()
    rule = pyqual_finding.get("rule", "").lower()

    if "config" in category or "yaml" in rule:
        return IssueCategory.CONFIG_ERROR
    if "dependency" in category or "import" in rule:
        return IssueCategory.DEPENDENCY_MISSING
    if "runtime" in category or "crash" in rule:
        return IssueCategory.RUNTIME_ERROR

    return IssueCategory.CONFIG_ERROR


def check_pyqual_installed() -> list[Issue]:
    """Check if pyqual is installed and available.

    Returns an Issue if pyqual is missing (installable fix).
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyqual", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # pyqual status returns 0 even if config is missing - it shows status info
        if (
            result.returncode == 0
            or "pyqual" in result.stdout.lower()
            or "metrics" in result.stdout.lower()
        ):
            return []
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return [
            Issue(
                category=IssueCategory.DEPENDENCY_MISSING,
                message="pyqual is not installed — code quality checks unavailable",
                fix_strategy=FixStrategy.AUTO,
                severity=SEVERITY_INFO,
                fix_description="Install pyqual via pip",
                fix_command="pip install pyqual",
                layer=1,
                teach=(
                    "pyqual provides automated code quality analysis. "
                    "Install it to enable quality checks in taskfile doctor."
                ),
            )
        ]


def check_pyqual_quality(project_path: Path | None = None) -> list[Issue]:
    """Run pyqual gates check and convert results to Issues.

    Uses 'pyqual gates' which is fast (seconds) vs 'pyqual run' (minutes).
    Shows quality gate status for key metrics.

    Args:
        project_path: Path to analyze (defaults to cwd)

    Returns:
        List of Issues for failed quality gates
    """
    # First check if pyqual is installed
    install_issues = check_pyqual_installed()
    if install_issues:
        return install_issues

    # Run pyqual gates check (fast)
    gates = _run_pyqual_gates(project_path)
    if gates is None:
        return [
            Issue(
                category=IssueCategory.RUNTIME_ERROR,
                message="pyqual gates check failed — check if pyqual is properly configured",
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_WARNING,
                fix_description="Run 'pyqual init' to create config, then 'pyqual run' for full analysis",
                layer=3,
            )
        ]

    issues: list[Issue] = []

    # Add issues for failed gates
    for fail in gates.get("failed", []):
        metric = fail.get("metric", "unknown")
        value = fail.get("value", "N/A")

        issue = Issue(
            category=IssueCategory.CONFIG_ERROR,
            message=f"Quality gate failed: {metric} = {value}",
            fix_strategy=FixStrategy.LLM,  # Quality issues need LLM or manual fix
            severity=SEVERITY_WARNING,
            fix_description=f"Improve {metric} metric to pass quality gate",
            context={
                "metric": metric,
                "value": value,
                "pyqual_output": gates.get("raw_output", "")[:500],
            },
            layer=3,
            teach=f"Quality gate '{metric}' ensures code quality standards. Review and refactor code to improve this metric.",
        )
        issues.append(issue)

    # Add info issue for summary
    passed_count = len(gates.get("passed", []))
    failed_count = len(gates.get("failed", []))

    if passed_count > 0 and failed_count == 0:
        issues.append(
            Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"All {passed_count} quality gates passed",
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_INFO,
                layer=3,
            )
        )

    return issues


def fix_with_pyqual(project_path: Path | None = None) -> tuple[int, list[str]]:
    """Run pyqual with --fix flag and return results.

    Args:
        project_path: Path to fix (defaults to cwd)

    Returns:
        Tuple of (fixed_count, failed_messages)
    """
    try:
        cmd = [sys.executable, "-m", "pyqual", "run", "--fix"]
        if project_path:
            cmd.extend(["--path", str(project_path)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Parse output for fix results
        fixed = 0
        failed: list[str] = []

        if result.returncode == 0:
            # Try to parse JSON output for fix count
            try:
                data = json.loads(result.stdout)
                fixed = data.get("fixed_count", 0)
            except json.JSONDecodeError:
                # Parse text output
                for line in result.stdout.splitlines():
                    if "fixed" in line.lower() or "applied" in line.lower():
                        try:
                            fixed = int("".join(c for c in line if c.isdigit()))
                        except ValueError:
                            pass
        else:
            failed.append(result.stderr or "pyqual fix failed")

        return fixed, failed

    except subprocess.TimeoutExpired:
        return 0, ["pyqual fix timed out after 120s"]
    except FileNotFoundError:
        return 0, ["pyqual not installed"]


def get_pyqual_summary(project_path: Path | None = None) -> dict:
    """Get a quick summary of pyqual quality gates.

    Returns summary dict with passed/failed gate counts.
    """
    gates = _run_pyqual_gates(project_path)

    if gates is None:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "all_passed": False,
            "error": "pyqual not available",
        }

    passed = len(gates.get("passed", []))
    failed = len(gates.get("failed", []))

    return {
        "total": passed + failed,
        "passed": passed,
        "failed": failed,
        "all_passed": failed == 0,
    }
