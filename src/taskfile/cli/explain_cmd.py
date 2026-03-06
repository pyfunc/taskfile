"""CLI 'explain' command — show resolved execution plan for a task."""

from __future__ import annotations

import sys
from pathlib import Path

import clickmd as click

from taskfile.cli.main import console, main, _print_nearby_taskfiles, _check_unknown_tasks
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    load_taskfile,
)


def _format_time_estimate(task) -> str:
    """Estimate execution time from timeout/retries."""
    parts = []
    if task.timeout:
        parts.append(f"timeout: {task.timeout}s")
    if task.retries:
        worst = task.timeout or 30
        total = worst + (task.retries * task.retry_delay)
        parts.append(f"max ~{total}s with retries")
    return ", ".join(parts) if parts else "no limit"


def _collect_requirements(steps, env) -> list[str]:
    """Detect what the execution plan requires."""
    reqs = []
    has_docker = any("docker" in s.expanded for s in steps if not s.skipped)
    has_remote = any(s.cmd_type == "remote" for s in steps if not s.skipped)
    has_python = any(s.cmd_type == "python" for s in steps if not s.skipped)

    if has_docker:
        reqs.append("Docker")
    if has_remote and env.ssh_host:
        reqs.append(f"SSH to {env.ssh_host}")
    if has_python:
        reqs.append("Python")
    return reqs


@main.command()
@click.argument("task_name")
@click.pass_context
def explain(ctx, task_name):
    """**Explain what a task will do** — full execution plan without running.

## Shows

- **Requirements** — Docker, SSH, Python, etc.
- **Time estimate** — based on timeout/retries
- **Step-by-step plan** — deps → commands, with variable expansion
- **Resolved variables** — what values will be used
- **Potential problems** — missing files, placeholders, unknown binaries

## Examples

```bash
# Basic explain
taskfile explain deploy

# Explain with specific environment
taskfile --env prod-eu explain deploy-quadlet

# Explain with variable overrides
taskfile --env prod explain deploy --var TAG=v1.2.3
```
"""
    opts = ctx.obj
    try:
        config = load_taskfile(opts["taskfile_path"])
        _check_unknown_tasks([task_name], config.tasks)

        from taskfile.runner.resolver import TaskResolver
        from taskfile.runner.explainer import TaskExplainer, ExplainReport

        resolver = TaskResolver(
            config,
            env_name=opts["env_name"],
            platform_name=opts["platform_name"],
            var_overrides=opts["var"],
        )

        explainer = TaskExplainer(resolver)
        report = explainer.explain([task_name])

        task = config.tasks[task_name]
        env = resolver.env

        # ── Header ──
        console.print()
        console.print(f"[bold green]📋 {task_name}[/] [dim](env: {resolver.env_name})[/]")
        if task.description:
            console.print(f"   {task.description}")
        console.print()

        # ── Requirements ──
        reqs = _collect_requirements(report.steps, env)
        if reqs:
            console.print(f"  [bold]Requires:[/]  {', '.join(reqs)}")

        # ── Time estimate ──
        console.print(f"  [bold]Time:[/]      {_format_time_estimate(task)}")

        # ── Retries ──
        if task.retries:
            console.print(f"  [bold]Retries:[/]   {task.retries} (delay: {task.retry_delay}s)")

        # ── Tags ──
        if task.tags:
            console.print(f"  [bold]Tags:[/]      {', '.join(task.tags)}")

        console.print()

        # ── Steps ──
        console.print("  [bold]Steps:[/]")
        current_task = None
        step_num = 0

        _TYPE_ICONS = {
            "local": "💻",
            "remote": "🌐",
            "function": "⚡",
            "python": "🐍",
            "script": "📜",
        }

        for step in report.steps:
            # Show task header when it changes (for deps)
            if step.task_name != current_task:
                current_task = step.task_name
                if step.is_dep:
                    console.print(f"    [dim]── dep: {current_task} ──[/]")

            step_num += 1
            icon = _TYPE_ICONS.get(step.cmd_type, "→")

            if step.skipped:
                console.print(f"    [dim]{step_num}. ⏭ {icon} {step.cmd[:80]}[/]")
                console.print(f"       [dim]↳ {step.skip_reason}[/]")
            else:
                console.print(f"    {step_num}. {icon} {step.cmd[:80]}")
                if step.expanded != step.cmd and step.expanded:
                    console.print(f"       [dim]↳ {step.expanded[:100]}[/]")

            for issue in step.issues:
                sev = "[yellow]⚠[/]" if issue.severity == "warning" else "[red]✗[/]"
                console.print(f"       {sev}  {issue.message}")

        # ── Variables ──
        console.print()
        console.print("  [bold]Variables:[/]")
        # Show most relevant variables (filter out empty/internal)
        shown = 0
        for k, v in sorted(resolver.variables.items()):
            if k.startswith("_") or not v:
                continue
            truncated = v[:60] + "..." if len(v) > 60 else v
            console.print(f"    {k}={truncated}")
            shown += 1
            if shown >= 15:
                remaining = len(resolver.variables) - shown
                if remaining > 0:
                    console.print(f"    [dim]... and {remaining} more[/]")
                break

        # ── Problems ──
        if report.issues:
            console.print()
            console.print(f"  [yellow bold]Potential problems ({len(report.issues)}):[/]")
            for i, issue in enumerate(report.issues, 1):
                sev = "⚠" if issue.severity == "warning" else "✗"
                console.print(f"    {i}. {sev} {issue.message}")

        # ── File checks ──
        _check_env_files(config, resolver, task)

        if not report.issues:
            console.print(f"\n  [green]✓ No problems detected — ready to run[/]")

        console.print()
        sys.exit(1 if report.has_errors else 0)

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


def _check_env_files(config, resolver, task) -> None:
    """Check if env_file exists for the resolved environment."""
    if not resolver.env.env_file:
        return
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    env_path = taskfile_dir / resolver.env.env_file
    if not env_path.exists():
        console.print()
        console.print(
            f"  [yellow]⚠  {resolver.env.env_file} does not exist "
            f"— create it or copy from .env.example[/]"
        )
