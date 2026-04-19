"""CLI 'info' command — show detailed info about a specific task."""

from __future__ import annotations

import sys

import clickmd as click

from taskfile.cli.main import console, main, _print_nearby_taskfiles
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    load_taskfile,
)


def _print_task_attributes(task) -> None:
    """Print task metadata attributes (deps, filters, options)."""
    _ATTR_LABELS = [
        ("deps", "Dependencies", lambda v: ", ".join(v)),
        ("env_filter", "Environments", lambda v: ", ".join(v)),
        ("platform_filter", "Platforms", lambda v: ", ".join(v)),
        ("condition", "Condition", str),
        ("parallel", "Parallel", lambda v: "yes (deps run concurrently)"),
        ("ignore_errors", "Ignore errors", lambda v: "yes"),
        ("retries", "Retries", lambda v: f"{v} (delay: {task.retry_delay}s)"),
        ("timeout", "Timeout", lambda v: f"{v}s"),
        ("tags", "Tags", lambda v: ", ".join(v)),
        ("register", "Register", str),
        ("script", "Script", str),
    ]
    for attr, label, fmt in _ATTR_LABELS:
        value = getattr(task, attr, None)
        if value:
            console.print(f"  [dim]{label}:[/] {fmt(value)}")


def _print_task_body(task) -> None:
    """Print task script and/or commands."""
    if task.script:
        console.print(f"\n  [bold]Script:[/] {task.script}")
    if task.commands:
        console.print("\n  [bold]Commands:[/]")
        for cmd in task.commands:
            console.print(f"    → {cmd}")


@main.command()
@click.argument("task_name")
@click.pass_context
def info(ctx, task_name):
    """Show detailed info about a specific task."""
    opts = ctx.obj
    try:
        config = load_taskfile(opts["taskfile_path"])
        if task_name not in config.tasks:
            console.print(f"[red]Unknown task: {task_name}[/]")
            sys.exit(1)

        task = config.tasks[task_name]
        console.print(f"\n[bold green]{task.name}[/]")
        if task.description:
            console.print(f"  {task.description}")

        _print_task_attributes(task)
        _print_task_body(task)

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)
