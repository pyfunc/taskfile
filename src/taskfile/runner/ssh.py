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


def is_push_command(cmd: str) -> bool:
    """Detect if command is prefixed with @push."""
    return cmd.strip().startswith("@push ")


def strip_push_prefix(cmd: str) -> str:
    """Remove @push prefix from command."""
    stripped = cmd.strip()
    if stripped.startswith("@push "):
        return stripped[len("@push "):]
    return stripped


def is_pull_command(cmd: str) -> bool:
    """Detect if command is prefixed with @pull."""
    return cmd.strip().startswith("@pull ")


def strip_pull_prefix(cmd: str) -> str:
    """Remove @pull prefix from command."""
    stripped = cmd.strip()
    if stripped.startswith("@pull "):
        return stripped[len("@pull "):]
    return stripped


def wrap_scp_push(cmd: str, env) -> str:
    """Build scp command: local files → remote destination.

    Syntax: @push <local_files...> <remote_dest>
    The last argument is the remote destination path.
    Example: @push deploy/quadlet/*.container /etc/containers/systemd/
    Becomes: scp {scp_opts} file1 file2 user@host:/etc/containers/systemd/
    """
    args = strip_push_prefix(cmd)
    parts = args.rsplit(None, 1)
    if len(parts) < 2:
        # Single arg — treat as remote dest with no files (will error naturally)
        return f"scp {env.scp_opts} {args} {env.ssh_target}:"
    files_part, remote_dest = parts[0], parts[1]
    return f"scp {env.scp_opts} {files_part} {env.ssh_target}:{remote_dest}"


def wrap_scp_pull(cmd: str, env) -> str:
    """Build scp command: remote files → local destination.

    Syntax: @pull <remote_path> <local_dest>
    The last argument is the local destination path.
    Example: @pull /var/log/app.log ./logs/
    Becomes: scp {scp_opts} user@host:/var/log/app.log ./logs/
    """
    args = strip_pull_prefix(cmd)
    parts = args.rsplit(None, 1)
    if len(parts) < 2:
        return f"scp {env.scp_opts} {env.ssh_target}:{args} ."
    remote_path, local_dest = parts[0], parts[1]
    return f"scp {env.scp_opts} {env.ssh_target}:{remote_path} {local_dest}"


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
