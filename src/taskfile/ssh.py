"""SSH embedded transport — optional paramiko-based SSH for faster execution.

Falls back to subprocess `ssh` when paramiko is not installed.
Install with: pip install taskfile[ssh]

Benefits of embedded SSH:
- Connection pooling (reuse connections across commands)
- No subprocess overhead per command
- Better error handling and timeout control
- Native Python — no external `ssh` binary required
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from rich.console import Console

from clickmd import MarkdownRenderer

if TYPE_CHECKING:
    from taskfile.models import Environment

console = Console()

# ─── Try to import paramiko (optional dependency) ─────

_HAS_PARAMIKO = False
try:
    import paramiko  # type: ignore[import-untyped]
    _HAS_PARAMIKO = True
except ImportError:
    paramiko = None  # type: ignore[assignment]


def has_paramiko() -> bool:
    """Check if paramiko is available."""
    return _HAS_PARAMIKO


# ─── Connection pool ──────────────────────────────────

_pool: dict[str, "paramiko.SSHClient"] = {}


def _pool_key(env: Environment) -> str:
    """Generate a unique key for connection pooling."""
    return f"{env.ssh_user}@{env.ssh_host}:{env.ssh_port}"


def _get_connection(env: Environment) -> "paramiko.SSHClient":
    """Get or create a pooled SSH connection."""
    key = _pool_key(env)
    if key in _pool:
        client = _pool[key]
        # Check if connection is still alive
        transport = client.get_transport()
        if transport and transport.is_active():
            return client
        # Connection dead — remove from pool
        try:
            client.close()
        except Exception:
            pass
        del _pool[key]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = {
        "hostname": env.ssh_host,
        "port": env.ssh_port,
        "username": env.ssh_user,
        "timeout": 30,
    }

    if env.ssh_key:
        key_path = os.path.expanduser(env.ssh_key)
        if os.path.isfile(key_path):
            connect_kwargs["key_filename"] = key_path

    client.connect(**connect_kwargs)
    _pool[key] = client
    return client


def close_all() -> None:
    """Close all pooled connections."""
    for key in list(_pool.keys()):
        try:
            _pool[key].close()
        except Exception:
            pass
    _pool.clear()


# ─── Execute commands ─────────────────────────────────

def ssh_exec(env: Environment, command: str, timeout: int = 300) -> int:
    """Execute a command on remote host via embedded SSH (paramiko).

    Returns the exit code of the remote command.
    """
    if not _HAS_PARAMIKO:
        return _ssh_exec_subprocess(env, command)

    try:
        client = _get_connection(env)
        _, stdout, stderr = client.exec_command(command, timeout=timeout)

        # Collect output and render as markdown codeblock
        out_text = stdout.read().decode("utf-8", errors="replace")
        err_text = stderr.read().decode("utf-8", errors="replace")
        combined = (out_text + err_text).rstrip()
        if combined:
            renderer = MarkdownRenderer(use_colors=True)
            renderer.codeblock("log", combined)

        exit_code = stdout.channel.recv_exit_status()
        return exit_code

    except Exception as exc:
        console.print(f"[yellow]⚠ Paramiko SSH failed ({exc}), falling back to subprocess[/]")
        return _ssh_exec_subprocess(env, command)


def _ssh_exec_subprocess(env: Environment, command: str) -> int:
    """Fallback: execute via subprocess `ssh` command."""
    target = env.ssh_target
    opts = env.ssh_opts
    escaped = command.replace("'", "'\\''")
    full_cmd = f"ssh {opts} {target} '{escaped}'"
    result = subprocess.run(
        full_cmd, shell=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = (result.stdout or "").rstrip()
    if output:
        renderer = MarkdownRenderer(use_colors=True)
        renderer.codeblock("log", output)
    return result.returncode
