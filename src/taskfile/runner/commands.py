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

try:
    from clickmd import MarkdownRenderer
    _HAS_CLICKMD = True
except ImportError:
    _HAS_CLICKMD = False

from taskfile.models import Task
from taskfile.runner.ssh import (
    is_remote_command, is_local_command, strip_local_prefix, strip_remote_prefix,
    wrap_ssh, run_embedded_ssh,
    is_push_command, is_pull_command, strip_push_prefix, strip_pull_prefix,
    wrap_scp_push, wrap_scp_pull,
)
from taskfile.runner.functions import run_function, run_inline_python

console = Console()


# ─── Markdown rendering helpers ──────────────────────────────────────────────

def _md(text: str) -> None:
    """Render markdown text via clickmd (falls back to plain print)."""
    if _HAS_CLICKMD:
        MarkdownRenderer(use_colors=True).render_markdown_with_fences(text)
    else:
        print(text)


# ─── Source location tracing ─────────────────────────────────────────────────

def _find_task_line(source_path: str | None, task_name: str) -> int | None:
    """Find the line number where a task is defined in the YAML source file."""
    if not source_path or not os.path.isfile(source_path):
        return None
    try:
        with open(source_path) as f:
            for i, line in enumerate(f, 1):
                # Match '  task_name:' as a YAML key under tasks
                if re.match(rf'^\s{{2,4}}{re.escape(task_name)}\s*:', line):
                    return i
    except OSError:
        pass
    return None


def _find_cmd_line(source_path: str | None, task_name: str, cmd: str) -> int | None:
    """Find the line number of a specific command within a task."""
    if not source_path or not os.path.isfile(source_path):
        return None
    try:
        cmd_stripped = cmd.strip().rstrip('"').lstrip('- ').strip('"').strip("'")
        # Use first 40 chars for matching (commands can be long)
        needle = cmd_stripped[:40]
        with open(source_path) as f:
            for i, line in enumerate(f, 1):
                if needle and needle in line:
                    return i
    except OSError:
        pass
    return None


def _source_ref(source_path: str | None, line: int | None) -> str:
    """Format a source file reference like 'Taskfile.yml:37'."""
    if not source_path or not line:
        return ""
    name = os.path.basename(source_path)
    return f"{name}:{line}"


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


def _check_file_arg(part: str, base: Path) -> str | None:
    """Check a single file argument from a transfer command. Returns warning or None."""
    if part.startswith('-') or ':' in part or part == '-':
        return None
    if '$' in part:
        return None

    path = Path(part)
    resolved = path if path.is_absolute() else base / part

    if '*' in part or '?' in part:
        matches = glob.glob(part, root_dir=str(base)) if not path.is_absolute() else glob.glob(part)
        if not matches:
            return (
                f"**No files match** `{part}` — generate them first "
                f"(e.g. `taskfile quadlet generate`)"
            )
    elif not resolved.exists():
        parent = resolved.parent
        suffix = resolved.suffix
        similar = []
        if parent.exists():
            similar = sorted(p.name for p in parent.iterdir() if p.suffix == suffix)[:5]
        hint = f" Available: `{'`, `'.join(similar)}`" if similar else ""
        return f"**File not found:** `{part}`{hint}"
    return None


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


# ─── Learning tips ───────────────────────────────────────────────────────────

_TIPS: list[tuple[str, str, str]] = [
    # (trigger_pattern, tip_title, tip_body)
    (
        "scp",
        "💡 Tip: Use rsync instead of scp",
        "`rsync -avz` handles globs, partial transfers, and resume better than `scp`.\n"
        "Example: `rsync -avz deploy/quadlet/ user@host:/etc/containers/systemd/`",
    ),
    (
        "quadlet",
        "💡 Tip: Generate Quadlet files first",
        "Run `taskfile quadlet generate --env-file .env.prod -o deploy/quadlet` before deploy.\n"
        "Add `quadlet-generate` as a dependency: `deps: [build, quadlet-generate]`",
    ),
    (
        "@remote",
        "💡 Tip: Test SSH connectivity",
        "Run `taskfile fleet status` to verify all remote hosts are reachable.\n"
        "Use `taskfile --dry-run` to preview SSH commands without executing.",
    ),
    (
        "docker compose",
        "💡 Tip: Check Docker Compose",
        "Run `docker compose config` to validate your compose file.\n"
        "Use `taskfile doctor --category runtime` to check Docker health.",
    ),
    (
        "systemctl",
        "💡 Tip: Quadlet + systemctl",
        "Podman Quadlet auto-generates systemd units from `.container` files.\n"
        "After uploading, run `systemctl daemon-reload` then `systemctl start <unit>`.",
    ),
    (
        ".env",
        "💡 Tip: Environment files",
        "Keep `.env.prod` gitignored. Use `.env.prod.example` as a template.\n"
        "Run `taskfile doctor --fix` to auto-create missing .env files from examples.",
    ),
]


def _get_tip_for_command(cmd: str) -> tuple[str, str] | None:
    """Return a (title, body) learning tip relevant to the command, or None."""
    cmd_lower = cmd.lower()
    for trigger, title, body in _TIPS:
        if trigger in cmd_lower:
            return title, body
    return None


def _get_tip_for_failure(cmd: str, returncode: int, category: str) -> str | None:
    """Return a learning tip relevant to a specific failure."""
    cmd_lower = cmd.lower()

    if "no such file" in cmd_lower or returncode == 1:
        if "scp" in cmd_lower or "rsync" in cmd_lower:
            return (
                "**💡 Missing files?** Run `taskfile doctor --fix` to check for missing "
                "deploy artifacts.\nGenerate Quadlet files: `taskfile quadlet generate`"
            )

    if returncode == 255 and ("ssh" in cmd_lower or "scp" in cmd_lower):
        return (
            "**💡 SSH error (exit 255)?** Common causes:\n"
            "- Host unreachable — check `ssh_host` in Taskfile.yml\n"
            "- Key rejected — check `ssh_key` and `chmod 600`\n"
            "- Run `taskfile fleet status` to diagnose"
        )

    if returncode == 126:
        return (
            "**💡 Permission denied?** Check:\n"
            "- Script is executable: `chmod +x scripts/*.sh`\n"
            "- Correct path in `script:` field"
        )

    if returncode == 127:
        return (
            "**💡 Command not found?** Check:\n"
            "- Tool is installed: `which <command>`\n"
            "- PATH includes the tool's directory\n"
            "- Run `taskfile doctor` to check missing dependencies"
        )

    return None


def _expand_globs_in_command(cmd: str, cwd: str | Path | None = None) -> str:
    """Expand glob patterns (wildcards) in a command string locally.

    This ensures patterns like 'deploy/quadlet/*.container' are expanded
    to actual file paths before the command is executed, preventing
    'No such file or directory' errors when using scp/ssh.

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

    # Shell operators that must NOT be quoted
    _SHELL_OPS = frozenset({
        '&&', '||', ';', '|', '>', '>>', '<', '<<', '2>', '2>>', '&>', '&',
    })

    import re
    # Redirect patterns: 2>/dev/null, 2>&1, &>/dev/null, >/dev/null, etc.
    _REDIRECT_RE = re.compile(r'^[0-9]*[<>]+.*')

    expanded_parts = []
    for part in parts:
        # Preserve shell operators verbatim
        if part in _SHELL_OPS:
            expanded_parts.append(part)
            continue

        # Preserve shell redirects (2>/dev/null, 2>&1, >/dev/null, etc.)
        if _REDIRECT_RE.match(part):
            expanded_parts.append(part)
            continue

        # Skip if it looks like a variable or option
        if part.startswith('$') or part.startswith('-'):
            expanded_parts.append(shlex.quote(part))
            continue

        # Preserve @-prefixes (@remote, @local, @push, etc.)
        if part.startswith('@'):
            expanded_parts.append(part)
            continue

        # Check for glob patterns
        if '*' in part or '?' in part or '[' in part:
            # Resolve glob relative to cwd if provided
            if cwd and not part.startswith('/'):
                matches = glob.glob(part, root_dir=cwd)
            else:
                matches = glob.glob(part)

            if matches:
                sorted_matches = sorted(matches)
                expanded_parts.extend(shlex.quote(m) for m in sorted_matches)
            else:
                # No matches found - keep original to let shell handle error
                expanded_parts.append(part)
        else:
            expanded_parts.append(shlex.quote(part))

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
    """
    expanded = runner.expand_variables(cmd)
    # Skip glob expansion for @fn/@python and multiline shell scripts —
    # shlex.split would mangle if/then/fi, for loops, etc.
    stripped = expanded.strip()
    if not (stripped.startswith("@fn ") or stripped.startswith("@python ")
            or '\n' in stripped):
        # Expand globs locally (e.g., deploy/quadlet/*.container → actual files)
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
    returncode: int, task: Task, task_name: str, start: float, label: str,
    cmd: str = "", source_path: str | None = None,
    runner=None,
) -> bool:
    """Handle a non-zero return code. Returns False if execution should stop."""
    if returncode == 0:
        return True
    if task.ignore_errors:
        console.print(f"  [yellow]⚠ {label} failed (ignored)[/]")
        return True
    elapsed = time.time() - start
    category, hint = _classify_exit_code(returncode)

    # Show failure with config location
    cmd_line = _find_cmd_line(source_path, task_name, cmd) if cmd else None
    ref = _source_ref(source_path, cmd_line)
    ref_info = f" at `{ref}`" if ref else ""

    _md(
        f"### ❌ Task `{task_name}` {label} failed\n\n"
        f"- **Exit code:** {returncode} ({category})\n"
        f"- **Duration:** {elapsed:.1f}s\n"
        f"- **Hint:** {hint}\n"
        + (f"- **Location:**{ref_info}\n" if ref_info else "")
    )

    # Show the failing command in context
    if cmd and source_path:
        _md(f"```yaml\n# Failing command in task '{task_name}':\n- {cmd.strip()}\n```")

    # Rich contextual diagnosis via ErrorPresenter
    if runner and cmd:
        try:
            from taskfile.runner.error_presenter import ErrorPresenter
            stderr = runner._last_stderr if hasattr(runner, '_last_stderr') else ""
            ErrorPresenter().present(
                cmd=cmd,
                exit_code=returncode,
                stderr=stderr,
                task_name=task_name,
                env_name=runner.env_name,
                variables=runner.variables,
            )
        except Exception:
            pass  # fallback to legacy tips below

    # Contextual learning tip
    tip = _get_tip_for_failure(cmd, returncode, category)
    if tip:
        _md(f"\n{tip}")

    # Actionable next steps
    if category == "config":
        _md("\n**Next steps:** `taskfile doctor --fix` or `taskfile validate`")
    elif category == "infra":
        _md("\n**Next steps:** `taskfile doctor --llm` for AI-assisted troubleshooting")
    else:
        _md("\n**Next steps:** Check output above, then `taskfile doctor` for diagnostics")

    return False


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

    # Pre-run file validation — catch missing files before execution
    if runner.verbose and task.commands:
        file_warnings = _validate_all_commands(runner, task, task_name)
        if file_warnings:
            _md("### ⚠️ Pre-run file check\n")
            for w in file_warnings:
                _md(f"- {w}")
            _md("")

    # Execute external script if defined
    if task.script:
        step += 1
        if not _execute_script_step(runner, task, task_name, start, step, total_steps):
            return False

    for i, cmd in enumerate(task.commands):
        step += 1
        if not _execute_cmd_step(runner, task, task_name, cmd, start, step, total_steps):
            return False

    # Success tip — show a learning tip for the last command (occasionally)
    if task.commands and runner.verbose:
        tip = _get_tip_for_command(task.commands[-1])
        if tip:
            _md(f"\n{tip[0]}\n\n{tip[1]}")

    return True
