"""SSH command execution for task runner — remote command handling."""

from __future__ import annotations

from rich.console import Console

from taskfile.models import Task
from taskfile.ssh import ssh_exec

console = Console()


def is_local_command(cmd: str) -> bool:
    """Detect if command is prefixed with @local."""
    return cmd.strip().startswith("@local ")


def strip_local_prefix(cmd: str) -> str:
    """Remove @local prefix from command."""
    stripped = cmd.strip()
    if stripped.startswith("@local "):
        return stripped[len("@local "):]
    return stripped


def is_remote_command(cmd: str) -> bool:
    """Detect if command is prefixed with @remote or @ssh."""
    return cmd.strip().startswith("@remote ") or cmd.strip().startswith("@ssh ")


def strip_remote_prefix(cmd: str) -> str:
    """Remove @remote/@ssh prefix from command."""
    stripped = cmd.strip()
    for prefix in ("@remote ", "@ssh "):
        if stripped.startswith(prefix):
            return stripped[len(prefix):]
    return stripped


def wrap_ssh(cmd: str, env) -> str:
    """Wrap command in SSH call to remote host."""
    remote_cmd = strip_remote_prefix(cmd)
    target = env.ssh_target
    opts = env.ssh_opts
    # Escape single quotes in command
    escaped = remote_cmd.replace("'", "'\\''")
    return f"ssh {opts} {target} '{escaped}'"


def run_embedded_ssh(runner, cmd: str, task: Task) -> int:
    """Execute remote command via embedded SSH (paramiko)."""
    remote_cmd = strip_remote_prefix(cmd)
    if not task.silent:
        console.print(f"  [magenta]→ SSH (embedded)[/] {remote_cmd}")
    if runner.dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return 0
    try:
        return ssh_exec(runner.env, remote_cmd)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Interrupted[/]")
        return 130
