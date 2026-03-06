"""Command execution for task runner — run_command, _execute_commands, _execute_script."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from rich.console import Console

try:
    from clickmd import MarkdownRenderer
    _HAS_CLICKMD = True
except ImportError:
    _HAS_CLICKMD = False

from taskfile.models import Task
from taskfile.runner.ssh import is_remote_command, is_local_command, strip_local_prefix, wrap_ssh, run_embedded_ssh
from taskfile.runner.functions import run_function, run_inline_python

console = Console()


def _dispatch_special_prefix(runner, expanded: str, task: Task) -> int | None:
    """Check for special command prefixes (@fn, @python, @local, @remote/@ssh).

    Returns the exit code if handled, or None to fall through to local execution.

    Routing logic:
        @local  → run only when env has NO ssh_host (skip on remote envs)
        @remote → run only when env HAS ssh_host  (skip on local envs)
    """
    stripped = expanded.strip()

    if stripped.startswith("@fn "):
        return run_function(runner, expanded, task)

    if stripped.startswith("@python "):
        return run_inline_python(runner, expanded, task)

    # @local — execute only on local (non-SSH) environments
    if is_local_command(expanded):
        if runner.env.is_remote:
            return 0  # skip @local commands on remote envs
        local_cmd = strip_local_prefix(expanded)
        return _run_local(runner, local_cmd, task)

    # @remote — execute only on remote (SSH) environments
    if is_remote_command(expanded):
        if not runner.env.ssh_target:
            return 0  # skip @remote commands on local envs
        if runner.use_embedded_ssh:
            return run_embedded_ssh(runner, expanded, task)
        return _run_local(runner, wrap_ssh(expanded, runner.env), task, remote=True)

    return None


def _render_output(output: str, task: Task) -> None:
    """Render command output as a markdown codeblock using clickmd."""
    if not output or not output.strip() or task.silent:
        return
    if _HAS_CLICKMD:
        MarkdownRenderer(use_colors=True).codeblock("log", output.rstrip())
    else:
        print(output.rstrip())


def _run_subprocess(runner, cmd_str: str, task: Task, label: str = "Command") -> int:
    """Run a shell command with capture, timeout, and interrupt handling."""
    try:
        env = {**os.environ, **runner.variables}
        timeout = task.timeout if task.timeout > 0 else None
        result = subprocess.run(
            cmd_str,
            shell=True,
            cwd=task.working_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        output = result.stdout or ""
        if task.register and output:
            runner.variables[task.register] = output.strip()
        _render_output(output, task)
        return result.returncode
    except subprocess.TimeoutExpired:
        console.print(f"  [red]⏱ {label} timed out after {task.timeout}s[/]")
        return 124
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Interrupted[/]")
        return 130


def _run_local(runner, actual_cmd: str, task: Task, remote: bool = False) -> int:
    """Execute a command locally (or a wrapped SSH command). Handles dry-run, capture, timeout."""
    if not task.silent:
        prefix = "[magenta]→ SSH[/]" if remote else "[blue]→[/]"
        console.print(f"  {prefix} {actual_cmd}")

    if runner.dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return 0

    return _run_subprocess(runner, actual_cmd, task, label="Command")


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

    # Resolve relative to Taskfile directory (source_path), then working_dir, then cwd
    resolved = Path(script_path)
    if not resolved.is_absolute():
        taskfile_dir = (
            Path(runner.config.source_path).parent
            if runner.config.source_path
            else Path.cwd()
        )
        candidate = taskfile_dir / resolved
        if candidate.exists():
            resolved = candidate
        elif task.working_dir:
            resolved = Path(task.working_dir) / resolved

    if not resolved.exists():
        console.print(f"  [red]✗ Script not found: {resolved.resolve()}[/]")
        # Hint: show nearby scripts
        search_dir = (
            Path(runner.config.source_path).parent
            if runner.config.source_path
            else Path.cwd()
        )
        nearby = sorted(search_dir.rglob("*.sh"))[:5]
        if nearby:
            console.print(f"  [dim]Available scripts in {search_dir}:[/]")
            for p in nearby:
                console.print(f"    [dim]{p.relative_to(search_dir)}[/]")
        return 1

    return _run_subprocess(runner, f"bash {resolved}", task, label="Script")


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


def _classify_exit_code(returncode: int) -> tuple[str, str]:
    """Classify exit code into error category and hint.

    Returns (category_tag, hint) where category_tag is one of:
        runtime  — the executed software failed
        config   — likely a taskfile/env misconfiguration
        infra    — infrastructure problem (network, permissions, etc.)
    """
    if returncode == 126:
        return "config", "Permission denied or not executable — check script permissions"
    if returncode == 127:
        return "config", "Command not found — check task commands or PATH"
    if returncode == 128 + 9:  # SIGKILL
        return "infra", "Process killed (OOM?) — check system resources"
    if returncode == 128 + 15:  # SIGTERM
        return "infra", "Process terminated — check if another process interfered"
    if returncode == 124:
        return "infra", "Command timed out — increase timeout or check network"
    if returncode == 130:
        return "runtime", "Interrupted by user (Ctrl+C)"
    if returncode == 1:
        return "runtime", "Command returned error — check the software's logs above"
    if returncode == 2:
        return "config", "Invalid arguments — check task command syntax"
    return "runtime", f"Exit code {returncode} — check the software's output above"


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
    category, hint = _classify_exit_code(returncode)
    console.print(
        f"[red]✗ Task '{task_name}' {label} failed after {elapsed:.1f}s "
        f"(exit code {returncode}) [{category}][/]"
    )
    console.print(f"  [dim]{hint}[/]")
    if category == "config":
        console.print(f"  [dim]Run 'taskfile doctor' to diagnose configuration issues[/]")
    elif category == "infra":
        console.print(f"  [dim]Run 'taskfile doctor --llm' for AI-assisted troubleshooting[/]")
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
