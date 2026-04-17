"""SSH command execution for task runner — remote command handling."""

from __future__ import annotations

from rich.console import Console

from taskfile.models import Task
from taskfile.ssh import ssh_exec
from taskfile.runner.utils.prefix import has_prefix, strip_prefix, has_any_prefix, strip_any_prefix

console = Console()

# Prefix detection helpers
is_local_command = lambda cmd: has_prefix(cmd, "@local")
is_remote_command = lambda cmd: has_any_prefix(cmd, ["@remote", "@ssh"])
is_push_command = lambda cmd: has_prefix(cmd, "@push")
is_pull_command = lambda cmd: has_prefix(cmd, "@pull")

# Prefix stripping helpers
strip_local_prefix = lambda cmd: strip_prefix(cmd, "@local")
strip_remote_prefix = lambda cmd: strip_any_prefix(cmd, ["@remote", "@ssh"])
strip_push_prefix = lambda cmd: strip_prefix(cmd, "@push")
strip_pull_prefix = lambda cmd: strip_prefix(cmd, "@pull")


def wrap_ssh(cmd: str, env) -> str:
    """Wrap command in SSH call to remote host."""
    remote_cmd = strip_remote_prefix(cmd)
    target = env.ssh_target
    opts = env.ssh_opts
    # Escape single quotes in command
    escaped = remote_cmd.replace("'", "'\\''")
    return f"ssh {opts} {target} '{escaped}'"


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
