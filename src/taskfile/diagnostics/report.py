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


def print_report(issues: list[Issue], categorized: bool = True) -> None:
    """Print diagnostic report to console."""
    if not issues:
        console.print(Panel(
            "[bold green]✓ All checks passed![/]\n"
            "Your project is ready to use.",
            border_style="green",
        ))
        return

    if categorized:
        _print_layered_report(issues)
    else:
        _print_flat_report(issues)


def _print_layered_report(issues: list[Issue]) -> None:
    """Print issues grouped by layer (1-5) with category sub-groups."""
    by_layer: dict[int, list[Issue]] = defaultdict(list)
    for iss in issues:
        by_layer[iss.layer].append(iss)

    for layer_num in sorted(by_layer.keys()):
        layer_issues = by_layer[layer_num]
        layer_name = LAYER_NAMES.get(layer_num, f"Layer {layer_num}")
        error_count = sum(1 for i in layer_issues if i.severity == SEVERITY_ERROR)

        header_style = "red" if error_count else "yellow" if layer_issues else "green"
        console.print(f"\n[bold blue]🔍 Layer {layer_num}: {layer_name}[/]")

        # Group by category within layer
        by_cat: dict[IssueCategory, list[Issue]] = defaultdict(list)
        for iss in layer_issues:
            by_cat[iss.category].append(iss)

        for cat in IssueCategory:
            items = by_cat.get(cat)
            if not items:
                continue

            label = CATEGORY_LABELS[cat]
            hint = CATEGORY_HINTS[cat]
            cat_errors = sum(1 for i in items if i.severity == SEVERITY_ERROR)
            style = "red" if cat_errors else "yellow"

            console.print(f"  [{style}]{label}[/] [dim]({len(items)} issue{'s' if len(items) > 1 else ''})[/]")

            for iss in items:
                icon = _severity_icon(iss.severity)
                fix_tag = _fix_tag(iss)
                console.print(f"    {icon} {iss.message}")
                if iss.fix_command:
                    console.print(f"       → FIX: [cyan]{iss.fix_command}[/]")
                elif iss.fix_description:
                    console.print(f"       → {iss.fix_description}")
                if iss.context and iss.context.get("llm_suggestion"):
                    console.print(f"       💡 AI: {iss.context['llm_suggestion']}")

            console.print(f"    [dim]{hint}[/]")


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
