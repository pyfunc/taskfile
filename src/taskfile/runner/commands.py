"""Command execution for task runner — run_command, _execute_commands, _execute_script."""

from __future__ import annotations

import glob
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

from rich.console import Console

from taskfile.models import Task
from taskfile.runner.ssh import (
    is_remote_command, is_local_command, strip_local_prefix, strip_remote_prefix,
    wrap_ssh, run_embedded_ssh,
    is_push_command, is_pull_command, strip_push_prefix, strip_pull_prefix,
    wrap_scp_push, wrap_scp_pull,
)
from taskfile.runner.functions import run_function, run_inline_python
from taskfile.runner.classifier import classify_command, CommandType, should_expand_globs, has_glob_pattern
from taskfile.runner.utils.markdown import render_md as _md, _HAS_CLICKMD, render_codeblock

try:
    from clickmd import MarkdownRenderer
except ImportError:
    pass

console = Console()


# ─── Source location tracing (delegated to failure.py) ───────────────────────

from taskfile.runner.failure import _find_task_line, _find_cmd_line, _source_ref  # noqa: E402


# ─── Step-by-step rendering ──────────────────────────────────────────────────

def _render_step_header(
    runner, task_name: str, cmd: str, step: int, total: int, task: Task
) -> None:
    """Render a step header showing config location and command being executed."""
    if task.silent:
        return

    source_path = runner.config.source_path
    cmd_line = _find_cmd_line(source_path, task_name, cmd)
    ref = _source_ref(source_path, cmd_line)

    # Determine command type label
    stripped = cmd.strip()
    if stripped.startswith("@remote "):
        cmd_type = "🌐 remote"
    elif stripped.startswith("@local "):
        cmd_type = "💻 local"
    elif stripped.startswith("@fn "):
        cmd_type = "⚡ function"
    elif stripped.startswith("@python "):
        cmd_type = "🐍 python"
    else:
        cmd_type = "💻 local"

    ref_str = f" `{ref}`" if ref else ""
    header = f"### Step {step}/{total} — {cmd_type}{ref_str}"

    if runner.verbose:
        _md(header + f"\n```yaml\n# task: {task_name}\n- {cmd.strip()}\n```")
    else:
        _md(header)


# ─── Pre-run file validation ─────────────────────────────────────────────────

_FILE_TRANSFER_CMDS = re.compile(r'^(scp|rsync|cp)\b')


def _strip_cmd_prefix(cmd: str) -> str:
    """Strip @remote/@local/@ssh prefix from command."""
    stripped = cmd.strip()
    for prefix in ("@remote ", "@local ", "@ssh "):
        if stripped.startswith(prefix):
            return stripped[len(prefix):]
    return stripped


def _is_flag_or_special(part: str) -> bool:
    """Return True if part is a flag, remote path (host:path), or stdin marker."""
    return part.startswith('-') or ':' in part or part == '-'


def _has_variable(part: str) -> bool:
    """Return True if part contains an unexpanded variable."""
    return '$' in part


def _check_glob_pattern(part: str, base: Path) -> str | None:
    """Check a glob pattern for matches. Returns warning or None."""
    path = Path(part)
    matches = glob.glob(part, root_dir=str(base)) if not path.is_absolute() else glob.glob(part)
    if not matches:
        return (
            f"**No files match** `{part}` — generate them first "
            f"(e.g. `taskfile quadlet generate`)"
        )
    return None


def _check_literal_path(part: str, resolved: Path) -> str | None:
    """Check that a literal file path exists. Returns warning with suggestions or None."""
    if resolved.exists():
        return None
    parent = resolved.parent
    suffix = resolved.suffix
    similar = []
    if parent.exists():
        similar = sorted(p.name for p in parent.iterdir() if p.suffix == suffix)[:5]
    hint = f" Available: `{'`, `'.join(similar)}`" if similar else ""
    return f"**File not found:** `{part}`{hint}"


def _check_file_arg(part: str, base: Path) -> str | None:
    """Check a single file argument from a transfer command. Returns warning or None."""
    if _is_flag_or_special(part) or _has_variable(part):
        return None

    path = Path(part)
    resolved = path if path.is_absolute() else base / part

    if '*' in part or '?' in part:
        return _check_glob_pattern(part, base)
    return _check_literal_path(part, resolved)


def _validate_command_files(cmd: str, cwd: str | Path | None = None) -> list[str]:
    """Check if local files referenced in scp/rsync/cp commands exist.

    Returns list of warning messages for missing files.
    """
    stripped = _strip_cmd_prefix(cmd)

    if not _FILE_TRANSFER_CMDS.match(stripped):
        return []

    try:
        parts = shlex.split(stripped)
    except ValueError:
        return []

    base = Path(cwd) if cwd else Path.cwd()
    warnings = []
    for part in parts[1:]:
        w = _check_file_arg(part, base)
        if w:
            warnings.append(w)
    return warnings


def _validate_all_commands(runner, task: Task, task_name: str) -> list[str]:
    """Validate all commands in a task before execution. Returns list of warnings."""
    all_warnings = []
    for cmd in task.commands:
        expanded = runner.expand_variables(cmd)
        warnings = _validate_command_files(expanded, cwd=task.working_dir)
        if warnings:
            for w in warnings:
                all_warnings.append(f"Task `{task_name}`, cmd `{cmd.strip()[:60]}`: {w}")
    return all_warnings


# ─── Learning tips (delegated to failure.py) ─────────────────────────────────

from taskfile.runner.failure import (  # noqa: E402
    _get_tip_for_command,
    _get_tip_for_failure,
    _TIPS,
)


# Shell operators that must NOT be quoted during glob expansion
_SHELL_OPS = frozenset({
    '&&', '||', ';', '|', '>', '>>', '<', '<<', '2>', '2>>', '&>', '&',
})

# Redirect patterns: 2>/dev/null, 2>&1, &>/dev/null, >/dev/null, etc.
_REDIRECT_RE = re.compile(r'^[0-9]*[<>]+.*')


def _safe_glob_expand(token: str, cwd: str | Path | None = None) -> list[str]:
    """Expand a single token's glob pattern to matching file paths.

    Args:
        token: A single command token potentially containing glob chars
        cwd: Working directory for relative glob resolution

    Returns:
        List of expanded paths (quoted), or [token] if no glob or no matches
    """
    if not ('*' in token or '?' in token or '[' in token):
        return [shlex.quote(token)]

    if cwd and not token.startswith('/'):
        matches = glob.glob(token, root_dir=cwd)
    else:
        matches = glob.glob(token)

    if matches:
        return [shlex.quote(m) for m in sorted(matches)]
    # No matches — keep original to let shell handle error
    return [token]


def _expand_globs_in_command(cmd: str, cwd: str | Path | None = None) -> str:
    """Expand glob patterns (wildcards) in a plain command string locally.

    IMPORTANT: Only call this on PLAIN_CMD types (use should_expand_globs()
    or classify_command() first). Shell constructs, @fn/@python, and
    multiline commands must NOT be passed through shlex.split.

    Args:
        cmd: Command string potentially containing globs
        cwd: Working directory for relative glob resolution

    Returns:
        Command string with globs expanded to matching paths
    """
    try:
        parts = shlex.split(cmd)
    except ValueError:
        # If shlex fails (e.g., unbalanced quotes), return original
        return cmd

    expanded_parts = []
    for part in parts:
        # Preserve shell operators verbatim
        if part in _SHELL_OPS:
            expanded_parts.append(part)
        # Preserve shell redirects (2>/dev/null, 2>&1, >/dev/null, etc.)
        elif _REDIRECT_RE.match(part):
            expanded_parts.append(part)
        # Skip variables and options
        elif part.startswith('$') or part.startswith('-'):
            expanded_parts.append(shlex.quote(part))
        # Preserve @-prefixes (@remote, @local, @push, etc.)
        elif part.startswith('@'):
            expanded_parts.append(part)
        else:
            expanded_parts.extend(_safe_glob_expand(part, cwd))

    # Reconstruct command — operators already unquoted, paths quoted
    return ' '.join(expanded_parts)


def _skip_msg(runner, prefix: str, reason: str, task: Task) -> int:
    """Print skip message for a prefix command and return 0 (success/skip)."""
    if not task.silent:
        console.print(f"  [dim]⏭ Pominięto {prefix} (env '{runner.env_name}' {reason})[/]")
    return 0


def _handle_local(runner, expanded: str, task: Task) -> int:
    """Handle @local prefix — run only on non-SSH environments."""
    if runner.env.is_remote:
        return _skip_msg(runner, "@local", "jest zdalny — ma ssh_host", task)
    return _run_local(runner, strip_local_prefix(expanded), task)


def _handle_remote(runner, expanded: str, task: Task) -> int:
    """Handle @remote prefix — run only on SSH environments."""
    if not runner.env.ssh_target:
        return _skip_msg(runner, "@remote", "nie ma ssh_host", task)
    if runner.use_embedded_ssh:
        return run_embedded_ssh(runner, expanded, task)
    remote_cmd = strip_remote_prefix(expanded)
    display = f"{runner.env.ssh_target} '{remote_cmd}'"
    return _run_local(runner, wrap_ssh(expanded, runner.env), task,
                      remote=True, display_cmd=display)


def _handle_push(runner, expanded: str, task: Task) -> int:
    """Handle @push prefix — scp local→remote, only on SSH environments."""
    if not runner.env.ssh_target:
        return _skip_msg(runner, "@push", "nie ma ssh_host", task)
    scp_cmd = wrap_scp_push(expanded, runner.env)
    args = strip_push_prefix(expanded)
    display = f"@push {args} → {runner.env.ssh_target}"
    return _run_local(runner, scp_cmd, task, remote=True, display_cmd=display)


def _handle_pull(runner, expanded: str, task: Task) -> int:
    """Handle @pull prefix — scp remote→local, only on SSH environments."""
    if not runner.env.ssh_target:
        return _skip_msg(runner, "@pull", "nie ma ssh_host", task)
    scp_cmd = wrap_scp_pull(expanded, runner.env)
    args = strip_pull_prefix(expanded)
    display = f"@pull {runner.env.ssh_target}:{args}"
    return _run_local(runner, scp_cmd, task, remote=True, display_cmd=display)


def _dispatch_special_prefix(runner, expanded: str, task: Task) -> int | None:
    """Check for special command prefixes (@fn, @python, @local, @remote/@ssh, @push, @pull).

    Returns the exit code if handled, or None to fall through to local execution.

    Routing logic:
        @local  → run only when env has NO ssh_host (skip on remote envs)
        @remote → run only when env HAS ssh_host  (skip on local envs)
        @push   → scp local→remote, only when env HAS ssh_host
        @pull   → scp remote→local, only when env HAS ssh_host
    """
    stripped = expanded.strip()

    if stripped.startswith("@fn "):
        return run_function(runner, expanded, task)
    if stripped.startswith("@python "):
        return run_inline_python(runner, expanded, task)
    if is_local_command(expanded):
        return _handle_local(runner, expanded, task)
    if is_remote_command(expanded):
        return _handle_remote(runner, expanded, task)
    if is_push_command(expanded):
        return _handle_push(runner, expanded, task)
    if is_pull_command(expanded):
        return _handle_pull(runner, expanded, task)
    return None


def _render_output(output: str, task: Task) -> None:
    """Render command output as a markdown codeblock using clickmd."""
    if not output or not output.strip() or task.silent:
        return
    render_codeblock("log", output.rstrip())


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
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        # Store stderr for ErrorPresenter diagnosis
        runner._last_stderr = result.stderr or ""
        if task.register and result.stdout:
            runner.variables[task.register] = result.stdout.strip()
        _render_output(output, task)
        return result.returncode
    except subprocess.TimeoutExpired:
        console.print(f"  [red]⏱ {label} timed out after {task.timeout}s[/]")
        return 124
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Interrupted[/]")
        return 130


def _run_local(runner, actual_cmd: str, task: Task, remote: bool = False,
               display_cmd: str | None = None) -> int:
    """Execute a command locally (or a wrapped SSH command). Handles dry-run, capture, timeout."""
    if not task.silent:
        prefix = "[magenta]→ SSH[/]" if remote else "[blue]→[/]"
        shown = display_cmd or actual_cmd
        console.print(f"  {prefix} {shown}")

    if runner.dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return 0

    return _run_subprocess(runner, actual_cmd, task, label="Command")


def run_command(runner, cmd: str, task: Task) -> int:
    """Execute a single command, locally or via SSH.

    Expands variables and glob patterns before execution.
    Uses the command classifier to determine if glob expansion is safe.
    """
    expanded = runner.expand_variables(cmd)

    # Classify command and only expand globs for PLAIN_CMD types.
    # Shell constructs (for/while/if), @fn/@python, multiline scripts
    # are NOT passed through shlex.split — it would mangle them.
    if should_expand_globs(expanded) and has_glob_pattern(expanded):
        expanded = _expand_globs_in_command(expanded, cwd=task.working_dir)

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


# ─── Failure handling (delegated to failure.py) ──────────────────────────────

from taskfile.runner.failure import (  # noqa: E402
    _classify_exit_code,
    _handle_failure,
    _format_failure_header,
    _run_error_presenter,
    _format_next_steps,
)


def _execute_script_step(
    runner, task: Task, task_name: str, start: float,
    step: int, total_steps: int,
) -> bool:
    """Execute the script: step of a task. Returns False on failure."""
    source_path = runner.config.source_path
    if not task.silent:
        ref = _source_ref(source_path, _find_task_line(source_path, task_name))
        ref_str = f" `{ref}`" if ref else ""
        _md(f"### Step {step}/{total_steps} — 📜 script{ref_str}")
        if runner.verbose:
            _md(f"```yaml\n# task: {task_name}\nscript: {task.script}\n```")
    rc = _run_with_retries(lambda: execute_script(runner, task, task_name), task)
    return _handle_failure(rc, task, task_name, start, "script",
                           cmd=f"script: {task.script}", source_path=source_path,
                           runner=runner)


def _execute_cmd_step(
    runner, task: Task, task_name: str, cmd: str, start: float,
    step: int, total_steps: int,
) -> bool:
    """Execute a single command step with pre-validation. Returns False on failure."""
    source_path = runner.config.source_path
    _render_step_header(runner, task_name, cmd, step, total_steps, task)

    expanded = runner.expand_variables(cmd)
    file_warnings = _validate_command_files(expanded, cwd=task.working_dir)
    if file_warnings:
        _md("\n".join(f"  ⚠️ {w}" for w in file_warnings))
        if not task.ignore_errors:
            tip = _get_tip_for_command(cmd)
            if tip:
                _md(f"\n{tip[0]}\n\n{tip[1]}")
            _md(
                f"\n### ❌ Pre-run validation failed for task `{task_name}`\n\n"
                f"**Fix:** Create the missing files, then re-run.\n"
                f"**Diagnose:** `taskfile doctor --fix`"
            )
            return False

    rc = _run_with_retries(lambda cmd=cmd: run_command(runner, cmd, task), task)
    return _handle_failure(rc, task, task_name, start, "command",
                           cmd=cmd, source_path=source_path,
                           runner=runner)


def _pre_validate_files(runner, task: Task, task_name: str) -> None:
    """Show pre-run file validation warnings (verbose mode only)."""
    if not (runner.verbose and task.commands):
        return
    file_warnings = _validate_all_commands(runner, task, task_name)
    if file_warnings:
        _md("### ⚠️ Pre-run file check\n")
        for w in file_warnings:
            _md(f"- {w}")
        _md("")


def _show_success_tip(runner, task: Task) -> None:
    """Show a learning tip for the last command on success (verbose mode only)."""
    if not (task.commands and runner.verbose):
        return
    tip = _get_tip_for_command(task.commands[-1])
    if tip:
        _md(f"\n{tip[0]}\n\n{tip[1]}")


def execute_commands(runner, task: Task, task_name: str, start: float) -> bool:
    """Execute all commands in a task. Returns False if any failed (and not ignored).

    Supports retries (Ansible-inspired): when task.retries > 0, failed commands
    are retried up to task.retries times with task.retry_delay seconds between.

    When task.script is set, the external script file is executed first,
    followed by any inline commands.

    Step-by-step visibility: each command is numbered and its config location
    is shown so users can trace execution back to Taskfile.yml.
    """
    total_steps = len(task.commands) + (1 if task.script else 0)
    step = 0

    _pre_validate_files(runner, task, task_name)

    # Execute external script if defined
    if task.script:
        step += 1
        if not _execute_script_step(runner, task, task_name, start, step, total_steps):
            return False

    for i, cmd in enumerate(task.commands):
        step += 1
        if not _execute_cmd_step(runner, task, task_name, cmd, start, step, total_steps):
            return False

    _show_success_tip(runner, task)
    return True
