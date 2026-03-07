"""SSH-related diagnostic checks — thin wrapper over fixop.

Delegates infrastructure checks to fixop and converts results
back to taskfile Issue format (adapter pattern).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig

try:
    import fixop
    from fixop.models import Issue as FixopIssue, Category as FixopCategory, Severity as FixopSeverity
    from fixop.models import HostContext
    _HAS_FIXOP = True
except ImportError:
    _HAS_FIXOP = False


# ── Adapter: fixop Issue → taskfile Issue ──────────────

_CATEGORY_MAP: dict = {}
_SEVERITY_MAP: dict = {}
if _HAS_FIXOP:
    _CATEGORY_MAP = {
        FixopCategory.SSH: IssueCategory.CONFIG_ERROR,
        FixopCategory.DNS: IssueCategory.EXTERNAL_ERROR,
        FixopCategory.FIREWALL: IssueCategory.EXTERNAL_ERROR,
        FixopCategory.CONTAINER: IssueCategory.DEPENDENCY_MISSING,
        FixopCategory.SYSTEMD: IssueCategory.EXTERNAL_ERROR,
        FixopCategory.TLS: IssueCategory.EXTERNAL_ERROR,
        FixopCategory.PORT: IssueCategory.RUNTIME_ERROR,
        FixopCategory.DEPLOY: IssueCategory.CONFIG_ERROR,
    }
    _SEVERITY_MAP = {
        FixopSeverity.INFO: SEVERITY_INFO,
        FixopSeverity.WARNING: SEVERITY_WARNING,
        FixopSeverity.ERROR: SEVERITY_ERROR,
        FixopSeverity.CRITICAL: SEVERITY_ERROR,
    }


def _to_taskfile_issue(fi: "FixopIssue", env_name: str = "") -> Issue:
    """Convert fixop Issue to taskfile Issue."""
    context = {}
    if fi.host:
        context["host"] = fi.host
    if env_name:
        context["env"] = env_name

    return Issue(
        category=_CATEGORY_MAP.get(fi.category, IssueCategory.EXTERNAL_ERROR),
        message=fi.message,
        fix_strategy=FixStrategy.CONFIRM if fi.fix_command else FixStrategy.MANUAL,
        severity=_SEVERITY_MAP.get(fi.severity, SEVERITY_WARNING),
        fix_command=fi.fix_command,
        fix_description=fi.details,
        context=context if context else None,
        layer=3,
    )


def _make_host_ctx(env) -> "HostContext":
    """Build a fixop HostContext from a taskfile environment."""
    return HostContext(
        host=env.ssh_host,
        user=env.ssh_user or "root",
        port=env.ssh_port or 22,
        key=env.ssh_key or "~/.ssh/id_ed25519",
    )


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
