"""Failure handling — exit code classification, error presentation, and learning tips.

Extracted from commands.py to reduce its size and improve separation of concerns.
Delegates classification to fixop.classify when available.
"""

from __future__ import annotations

import time

from rich.console import Console

from taskfile.models import Task
from taskfile.diagnostics.fixop_adapter import HAS_FIXOP as _HAS_FIXOP_CLASSIFY, fixop_category_to_tag

try:
    from clickmd import MarkdownRenderer
    _HAS_CLICKMD = True
except ImportError:
    _HAS_CLICKMD = False

try:
    from fixop.classify import classify_error as _fixop_classify_error
    from fixop.classify import get_tip_for_failure as _fixop_get_tip
except ImportError:
    pass

console = Console()


# ─── Markdown rendering ──────────────────────────────────────────────────────

def _md(text: str) -> None:
    """Render markdown text via clickmd (falls back to plain print)."""
    if _HAS_CLICKMD:
        MarkdownRenderer(use_colors=True).render_markdown_with_fences(text)
    else:
        print(text)


# ─── Source location tracing ─────────────────────────────────────────────────

def _find_task_line(source_path: str | None, task_name: str) -> int | None:
    """Find the line number where a task is defined in the YAML source file."""
    import os, re
    if not source_path or not os.path.isfile(source_path):
        return None
    try:
        with open(source_path) as f:
            for i, line in enumerate(f, 1):
                if re.match(rf'^\s{{2,4}}{re.escape(task_name)}\s*:', line):
                    return i
    except OSError:
        pass
    return None


def _find_cmd_line(source_path: str | None, task_name: str, cmd: str) -> int | None:
    """Find the line number of a specific command within a task."""
    import os
    if not source_path or not os.path.isfile(source_path):
        return None
    try:
        cmd_stripped = cmd.strip().rstrip('"').lstrip('- ').strip('"').strip("'")
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
    import os
    if not source_path or not line:
        return ""
    name = os.path.basename(source_path)
    return f"{name}:{line}"


# ─── Exit code classification ────────────────────────────────────────────────

def _classify_exit_code(returncode: int) -> tuple[str, str]:
    """Classify exit code into error category and hint.

    Returns (category_tag, hint) where category_tag is one of:
        runtime  — the executed software failed
        config   — likely a taskfile/env misconfiguration
        infra    — infrastructure problem (network, permissions, etc.)

    Delegates to fixop.classify when available.
    """
    if _HAS_FIXOP_CLASSIFY:
        fi = _fixop_classify_error(returncode)
        tag = fixop_category_to_tag(fi)
        return tag, fi.message

    # Legacy fallback
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
    """Return a learning tip relevant to a specific failure.

    Delegates to fixop.classify.get_tip_for_failure when available.
    """
    if _HAS_FIXOP_CLASSIFY:
        tip = _fixop_get_tip(cmd, returncode)
        if tip:
            return tip

    # Legacy fallback / additional taskfile-specific tips
    cmd_lower = cmd.lower()

    if "no such file" in cmd_lower or returncode == 1:
        if "scp" in cmd_lower or "rsync" in cmd_lower:
            return (
                "**Missing files?** Run `taskfile doctor --fix` to check for missing "
                "deploy artifacts.\nGenerate Quadlet files: `taskfile quadlet generate`"
            )

    if returncode == 255 and ("ssh" in cmd_lower or "scp" in cmd_lower):
        return (
            "**SSH error (exit 255)?** Common causes:\n"
            "- Host unreachable — check `ssh_host` in Taskfile.yml\n"
            "- Key rejected — check `ssh_key` and `chmod 600`\n"
            "- Run `taskfile fleet status` to diagnose"
        )

    if returncode == 126:
        return (
            "**Permission denied?** Check:\n"
            "- Script is executable: `chmod +x scripts/*.sh`\n"
            "- Correct path in `script:` field"
        )

    if returncode == 127:
        return (
            "**Command not found?** Check:\n"
            "- Tool is installed: `which <command>`\n"
            "- PATH includes the tool's directory\n"
            "- Run `taskfile doctor` to check missing dependencies"
        )

    return None


# ─── Failure handling pipeline ────────────────────────────────────────────────

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

    category, hint = _classify_exit_code(returncode)
    _format_failure_header(task_name, label, returncode, category, hint, start, cmd, source_path)
    _run_error_presenter(runner, cmd, returncode, task_name)

    tip = _get_tip_for_failure(cmd, returncode, category)
    if tip:
        _md(f"\n{tip}")

    _format_next_steps(category)
    return False


def _format_failure_header(
    task_name: str, label: str, returncode: int, category: str, hint: str,
    start: float, cmd: str, source_path: str | None,
) -> None:
    """Print failure summary with exit code, duration, and source location."""
    elapsed = time.time() - start
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

    if cmd and source_path:
        _md(f"```yaml\n# Failing command in task '{task_name}':\n- {cmd.strip()}\n```")


def _run_error_presenter(runner, cmd: str, returncode: int, task_name: str) -> None:
    """Run ErrorPresenter for rich contextual diagnosis. Silently skips on error."""
    if not (runner and cmd):
        return
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
        pass


def _format_next_steps(category: str) -> None:
    """Print actionable next steps based on error category."""
    if category == "config":
        _md("\n**Next steps:** `taskfile doctor --fix` or `taskfile validate`")
    elif category == "infra":
        _md("\n**Next steps:** `taskfile doctor --llm` for AI-assisted troubleshooting")
    else:
        _md("\n**Next steps:** Check output above, then `taskfile doctor` for diagnostics")
