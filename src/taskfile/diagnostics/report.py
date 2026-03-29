"""Layer reporting — categorized console output + JSON for CI.

Separates IO concerns from pure check logic.
"""

from __future__ import annotations

import json
from collections import defaultdict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    DoctorReport,
    CATEGORY_LABELS,
    CATEGORY_HINTS,
    SEVERITY_ERROR,
)

console = Console()

# Layer labels for the 5-layer output
LAYER_NAMES = {
    1: "Preflight",
    2: "Validation",
    3: "Diagnostics",
    4: "Algorithmic fix",
    5: "LLM assist",
}


def print_report(issues: list[Issue], categorized: bool = True, show_teach: bool = False) -> None:
    """Print diagnostic report to console."""
    if not issues:
        console.print(Panel(
            "[bold green]✓ All checks passed![/]\n"
            "Your project is ready to use.",
            border_style="green",
        ))
        return

    if categorized:
        _print_layered_report(issues, show_teach=show_teach)
    else:
        _print_flat_report(issues)


def _group_issues_by_layer(issues: list[Issue]) -> dict[str, list[Issue]]:
    """Group issues by logical display layer (Config, Dependencies, Runtime)."""
    DISPLAY_LAYERS = {
        IssueCategory.CONFIG_ERROR: ("Konfiguracja", "⚙️"),
        IssueCategory.TASKFILE_BUG: ("Konfiguracja", "⚙️"),
        IssueCategory.DEPENDENCY_MISSING: ("Zależności", "📦"),
        IssueCategory.RUNTIME_ERROR: ("Runtime", "🔧"),
        IssueCategory.EXTERNAL_ERROR: ("Runtime", "🔧"),
    }
    by_display: dict[str, list[Issue]] = defaultdict(list)
    for iss in issues:
        layer_name = DISPLAY_LAYERS.get(iss.category, ("Inne", "❓"))[0]
        by_display[layer_name].append(iss)
    return by_display


def _print_layer_issues(layer_name: str, layer_issues: list[Issue], show_teach: bool) -> None:
    """Print all issues for a single layer with formatting."""
    icon = {"Konfiguracja": "⚙️", "Zależności": "📦", "Runtime": "🔧"}.get(layer_name, "❓")
    error_count = sum(1 for i in layer_issues if i.severity == SEVERITY_ERROR)
    style = "red" if error_count else "yellow"

    console.print(f"\n[bold blue]{icon} {layer_name}[/]")

    for iss in layer_issues:
        sev_icon = _severity_icon(iss.severity)
        console.print(f"  {sev_icon} {iss.message}")
        if iss.fix_command:
            console.print(f"     → [cyan]{iss.fix_command}[/]")
        elif iss.fix_description:
            console.print(f"     → {iss.fix_description}")
        if show_teach and iss.teach:
            console.print(f"     [dim]ℹ️  {iss.teach}[/]")
        if iss.context and iss.context.get("llm_suggestion"):
            console.print(f"     💡 AI: {iss.context['llm_suggestion']}")


def _build_summary_parts(issues: list[Issue]) -> list[str]:
    """Build the list of summary parts with counts."""
    parts = []
    error_count = sum(1 for i in issues if i.severity == SEVERITY_ERROR)
    warn_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")
    fixable = sum(1 for i in issues if i.auto_fixable)

    if error_count:
        parts.append(f"[red]❌ Errors: {error_count}[/]")
    if warn_count:
        parts.append(f"[yellow]⚠ Warnings: {warn_count}[/]")
    if info_count:
        parts.append(f"[blue]ℹ Info: {info_count}[/]")
    if fixable:
        parts.append(f"[green]🔧 Auto-fixable: {fixable}[/]")
    return parts


def _get_summary_hints(issues: list[Issue], show_teach: bool) -> list[str]:
    """Get help hints for the summary."""
    hints = []
    fixable = sum(1 for i in issues if i.auto_fixable)
    has_teach = any(i.teach for i in issues)

    if fixable:
        hints.append("  [cyan]taskfile doctor --fix[/]    ← napraw automatycznie co się da")
    if not show_teach and has_teach:
        hints.append("  [cyan]taskfile doctor --teach[/]  ← szczegółowe wyjaśnienia")
    return hints


def _print_summary(issues: list[Issue], show_teach: bool) -> None:
    """Print summary footer with counts and hints."""
    parts = _build_summary_parts(issues)
    console.print(f"\n{'  '.join(parts)}")

    for hint in _get_summary_hints(issues, show_teach):
        console.print(hint)


def _print_layered_report(issues: list[Issue], show_teach: bool = False) -> None:
    """Print issues in 3 logical layers: Config, Dependencies, Runtime."""
    by_display = _group_issues_by_layer(issues)

    # Print main layers in order
    layer_order = ["Konfiguracja", "Zależności", "Runtime"]
    for layer_name in layer_order:
        layer_issues = by_display.get(layer_name)
        if layer_issues:
            _print_layer_issues(layer_name, layer_issues, show_teach)

    # Handle any uncategorized issues
    for layer_name, layer_issues in by_display.items():
        if layer_name not in layer_order and layer_issues:
            console.print(f"\n[bold blue]❓ {layer_name}[/]")
            for iss in layer_issues:
                sev_icon = _severity_icon(iss.severity)
                console.print(f"  {sev_icon} {iss.message}")

    # Summary footer
    _print_summary(issues, show_teach)


def _print_flat_report(issues: list[Issue]) -> None:
    """Print flat table of all issues."""
    table = Table(title="Project Diagnostics", box=box.ROUNDED)
    table.add_column("Layer", width=5, justify="center")
    table.add_column("Cat", width=12)
    table.add_column("Issue", style="yellow")
    table.add_column("Severity", width=8)
    table.add_column("Fix", width=8)

    for iss in issues:
        icon = _severity_icon(iss.severity)
        fix_tag = _fix_tag(iss)
        cat_short = iss.category.value.replace("_", " ")[:12]
        table.add_row(
            str(iss.layer), cat_short, iss.message,
            f"{icon} {iss.severity}", fix_tag,
        )

    console.print(table)


def print_report_json(issues: list[Issue]) -> None:
    """Print report as JSON for CI pipelines."""
    report = get_report_dict(issues)
    console.print_json(json.dumps(report, indent=2))


def get_report_dict(issues: list[Issue]) -> dict:
    """Return structured report dict."""
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for iss in issues:
        by_cat[iss.category.value].append(iss.as_dict())

    return {
        "total_issues": len(issues),
        "errors": sum(1 for i in issues if i.severity == SEVERITY_ERROR),
        "warnings": sum(1 for i in issues if i.severity == "warning"),
        "auto_fixable": sum(1 for i in issues if i.auto_fixable),
        "categories": dict(by_cat),
    }


def format_summary(report: DoctorReport) -> str:
    """Format a one-line summary string."""
    parts = []
    if report.fixed:
        parts.append(f"✅ Fixed: {len(report.fixed)}")
    if report.pending:
        parts.append(f"⏳ Pending: {len(report.pending)}")
    if report.external:
        parts.append(f"❌ External: {len(report.external)}")
    if report.llm_suggestions:
        parts.append(f"💡 AI suggestions: {len(report.llm_suggestions)}")
    return "  ".join(parts) if parts else "✅ No issues found"


def _severity_icon(severity: str) -> str:
    return {"error": "[red]✗[/]", "warning": "[yellow]⚠[/]", "info": "[blue]ℹ[/]"}.get(severity, "●")


def _fix_tag(issue: Issue) -> str:
    return {
        FixStrategy.AUTO: "[green]auto[/]",
        FixStrategy.CONFIRM: "[cyan]confirm[/]",
        FixStrategy.MANUAL: "[dim]manual[/]",
        FixStrategy.LLM: "[magenta]AI[/]",
    }.get(issue.fix_strategy, "[dim]?[/]")
