"""Command execution for task runner — run_command, _execute_commands, _execute_script."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console

from taskfile.models import Task
from taskfile.runner.ssh import is_remote_command, wrap_ssh, run_embedded_ssh
from taskfile.runner.functions import run_function, run_inline_python

console = Console()


def _dispatch_special_prefix(runner, expanded: str, task: Task) -> int | None:
    """Check for special command prefixes (@fn, @python, @remote/@ssh).

    Returns the exit code if handled, or None to fall through to local execution.
    """
    stripped = expanded.strip()

    if stripped.startswith("@fn "):
        return run_function(runner, expanded, task)

    if stripped.startswith("@python "):
        return run_inline_python(runner, expanded, task)

    if is_remote_command(expanded) and runner.env.ssh_target:
        if runner.use_embedded_ssh:
            return run_embedded_ssh(runner, expanded, task)
        return _run_local(runner, wrap_ssh(expanded, runner.env), task, remote=True)

    return None


def _run_local(runner, actual_cmd: str, task: Task, remote: bool = False) -> int:
    """Execute a command locally (or a wrapped SSH command). Handles dry-run, capture, timeout."""
    if not task.silent:
        prefix = "[magenta]→ SSH[/]" if remote else "[blue]→[/]"
        console.print(f"  {prefix} {actual_cmd}")

    if runner.dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return 0

    try:
        env = {**os.environ, **runner.variables}
        capture = task.register is not None
        timeout = task.timeout if task.timeout > 0 else None
        result = subprocess.run(
            actual_cmd,
            shell=True,
            cwd=task.working_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=None,
            timeout=timeout,
        )
        if capture and result.stdout:
            if not task.silent:
                sys.stdout.write(result.stdout)
            runner.variables[task.register] = result.stdout.strip()
        return result.returncode
    except subprocess.TimeoutExpired:
        console.print(f"  [red]⏱ Command timed out after {task.timeout}s[/]")
        return 124
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Interrupted[/]")
        return 130


def run_command(runner, cmd: str, task: Task) -> int:
    """Execute a single command, locally or via SSH."""
    expanded = runner.expand_variables(cmd)

    # Try special prefix dispatch first (@fn, @python, @remote/@ssh)
    result = _dispatch_special_prefix(runner, expanded, task)
    if result is not None:
        return result

    # Default: run locally
    return _run_local(runner, expanded, task)


def execute_script(runner, task: Task, task_name: str) -> int:
    """Execute an external script file referenced by task.script.

    The script path is resolved relative to the Taskfile directory.
    Variables are expanded in the script path.
    """
    script_path = runner.expand_variables(task.script)

    if not task.silent:
        console.print(f"  [blue]→ script:[/] {script_path}")

    if runner.dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return 0

    # Resolve relative to working_dir or cwd
    resolved = Path(script_path)
    if not resolved.is_absolute() and task.working_dir:
        resolved = Path(task.working_dir) / resolved

    if not resolved.exists():
        console.print(f"  [red]✗ Script not found: {resolved}[/]")
        return 1

    env = {**os.environ, **runner.variables}
    try:
        timeout = task.timeout if task.timeout > 0 else None
        capture = task.register is not None
        result = subprocess.run(
            f"bash {resolved}",
            shell=True,
            cwd=task.working_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=None,
            timeout=timeout,
        )
        if capture and result.stdout:
            if not task.silent:
                sys.stdout.write(result.stdout)
            runner.variables[task.register] = result.stdout.strip()
        return result.returncode
    except subprocess.TimeoutExpired:
        console.print(f"  [red]⏱ Script timed out after {task.timeout}s[/]")
        return 124
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Interrupted[/]")
        return 130


def _run_with_retries(fn, task: Task) -> int:
    """Run fn() and retry on failure according to task.retries/retry_delay."""
    returncode = fn()
    if returncode != 0 and task.retries > 0:
        for attempt in range(1, task.retries + 1):
            console.print(
                f"  [yellow]↻ Retry {attempt}/{task.retries} "
                f"(waiting {task.retry_delay}s)[/]"
            )
            time.sleep(task.retry_delay)
            returncode = fn()
            if returncode == 0:
                break
    return returncode


def _handle_failure(
    returncode: int, task: Task, task_name: str, start: float, label: str
) -> bool:
    """Handle a non-zero return code. Returns False if execution should stop."""
    if returncode == 0:
        return True
    if task.ignore_errors:
        console.print(f"  [yellow]⚠ {label} failed (ignored)[/]")
        return True
    elapsed = time.time() - start
    console.print(
        f"[red]✗ Task '{task_name}' {label} failed after {elapsed:.1f}s "
        f"(exit code {returncode})[/]"
    )
    return False


def execute_commands(runner, task: Task, task_name: str, start: float) -> bool:
    """Execute all commands in a task. Returns False if any failed (and not ignored).

    Supports retries (Ansible-inspired): when task.retries > 0, failed commands
    are retried up to task.retries times with task.retry_delay seconds between.

    When task.script is set, the external script file is executed first,
    followed by any inline commands.
    """
    # Execute external script if defined
    if task.script:
        rc = _run_with_retries(lambda: execute_script(runner, task, task_name), task)
        if not _handle_failure(rc, task, task_name, start, "script"):
            return False

    for cmd in task.commands:
        rc = _run_with_retries(lambda cmd=cmd: run_command(runner, cmd, task), task)
        if not _handle_failure(rc, task, task_name, start, "command"):
            return False
    return True
