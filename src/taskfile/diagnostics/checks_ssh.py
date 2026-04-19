"""SSH-related diagnostic checks — thin wrapper over fixop.

Delegates infrastructure checks to fixop and converts results
back to taskfile Issue format via fixop_adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from taskfile.diagnostics.models import Issue
from taskfile.diagnostics.fixop_adapter import (
    HAS_FIXOP as _HAS_FIXOP,
    adapt_issue as _to_taskfile_issue,
    make_host_ctx as _make_host_ctx,
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig

try:
    import fixop
except ImportError:
    pass


# ── Public checks ─────────────────────────────────────


def check_ssh_keys() -> list[Issue]:
    """Check SSH keys exist."""
    if not _HAS_FIXOP:
        return []
    fixop_issues = fixop.check_ssh_key()
    return [_to_taskfile_issue(i) for i in fixop_issues]


def check_ssh_connectivity(config: "TaskfileConfig") -> list[Issue]:
    """Check SSH connectivity — delegates to fixop."""
    if not _HAS_FIXOP:
        return []
    from taskfile.diagnostics.checks import _resolve_env_fields

    issues: list[Issue] = []
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    for env_name, env in config.environments.items():
        if not env.is_remote:
            continue
        _resolve_env_fields(env, taskfile_dir)
        ctx = _make_host_ctx(env)
        fixop_issues = fixop.check_ssh_connectivity(ctx)
        issues.extend(_to_taskfile_issue(i, env_name) for i in fixop_issues)
    return issues


def check_remote_health(config: "TaskfileConfig") -> list[Issue]:
    """Check remote host health — DNS, firewall, containers, disk, memory.

    Delegates all infra checks to fixop, converts results to taskfile Issues.
    """
    if not _HAS_FIXOP:
        return []
    from taskfile.diagnostics.checks import _resolve_env_fields

    issues: list[Issue] = []
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    for env_name, env in config.environments.items():
        if not env.is_remote:
            continue
        _resolve_env_fields(env, taskfile_dir)
        ctx = _make_host_ctx(env)

        # Quick SSH check — skip host if unreachable
        ssh_issues = fixop.check_ssh_connectivity(ctx)
        if ssh_issues:
            continue

        # DNS
        for i in fixop.check_host_dns(ctx):
            issues.append(_to_taskfile_issue(i, env_name))
        for i in fixop.check_container_dns(ctx):
            issues.append(_to_taskfile_issue(i, env_name))

        # Firewall
        for i in fixop.check_ufw_forward_policy(ctx):
            issues.append(_to_taskfile_issue(i, env_name))

        # Containers
        for i in fixop.check_runtime(ctx):
            issues.append(_to_taskfile_issue(i, env_name))

        # Disk & memory
        for i in fixop.check_disk_usage(ctx):
            issues.append(_to_taskfile_issue(i, env_name))
        for i in fixop.check_memory(ctx):
            issues.append(_to_taskfile_issue(i, env_name))

    return issues
