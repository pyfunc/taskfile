"""## CLI 'info' command for taskfile

Show detailed information about a specific task.

### Overview

The `info` command displays comprehensive task details:
- **Description** - Task description and purpose
- **Commands** - List of commands to execute
- **Environment** - Required environment variables
- **Dependencies** - Task dependencies
- **Platforms** - Supported platforms

### Usage

```bash
# Show info for a task
taskfile info build

# Show info with environment details
taskfile info deploy --env production
```

### Output Format

```
📋 Task: build
━━━━━━━━━━━━━━━━━━━━
Description: Build the application
Commands:
  1. docker build -t app .
  2. docker push app:latest
Environment:
  • TAG - Docker image tag
Dependencies:
  • test
Platforms:
  • linux/amd64
  • linux/arm64
```

### Why clickmd?

Uses `clickmd` for consistent CLI experience and markdown rendering of task info.

### Dependencies

- `clickmd` - CLI framework
- `rich` - Rich console output for formatted task details
"""

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
        console.print(f"\n  [bold]Commands:[/]")
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
