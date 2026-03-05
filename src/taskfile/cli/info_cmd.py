"""CLI 'info' command — show detailed info about a specific task."""

from __future__ import annotations

import sys

import click

from taskfile.cli.main import console, main, _print_nearby_taskfiles
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    load_taskfile,
)


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
        if task.deps:
            console.print(f"  [dim]Dependencies:[/] {', '.join(task.deps)}")
        if task.env_filter:
            console.print(f"  [dim]Environments:[/] {', '.join(task.env_filter)}")
        if task.platform_filter:
            console.print(f"  [dim]Platforms:[/] {', '.join(task.platform_filter)}")
        if task.condition:
            console.print(f"  [dim]Condition:[/] {task.condition}")
        if task.parallel:
            console.print(f"  [dim]Parallel:[/] yes (deps run concurrently)")
        if task.ignore_errors:
            console.print(f"  [dim]Ignore errors:[/] yes")
        if task.retries:
            console.print(f"  [dim]Retries:[/] {task.retries} (delay: {task.retry_delay}s)")
        if task.timeout:
            console.print(f"  [dim]Timeout:[/] {task.timeout}s")
        if task.tags:
            console.print(f"  [dim]Tags:[/] {', '.join(task.tags)}")
        if task.register:
            console.print(f"  [dim]Register:[/] {task.register}")
        if task.script:
            console.print(f"  [dim]Script:[/] {task.script}")

        if task.script:
            console.print(f"\n  [bold]Script:[/] {task.script}")
        if task.commands:
            console.print(f"\n  [bold]Commands:[/]")
            for cmd in task.commands:
                console.print(f"    → {cmd}")

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)
