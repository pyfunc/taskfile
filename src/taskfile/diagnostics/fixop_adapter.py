"""Single point of integration between taskfile and fixop.

All fixop ↔ taskfile Issue conversion goes through this module.
Other diagnostics modules import adapt_issue / adapt_issues instead of
duplicating category/severity maps.

Graceful degradation: when fixop is not installed, HAS_FIXOP is False
and adapt_* functions return empty results.
"""

from __future__ import annotations

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)

try:
    from fixop.models import (
        Issue as FixopIssue,
        Category as FixopCategory,
        Severity as FixopSeverity,
        HostContext,
    )

    HAS_FIXOP = True
except ImportError:
    HAS_FIXOP = False

# ── Category mapping ─────────────────────────────────────

_CATEGORY_MAP: dict = {}
_SEVERITY_MAP: dict = {}

if HAS_FIXOP:
    _CATEGORY_MAP = {
        FixopCategory.SSH: IssueCategory.CONFIG_ERROR,
        FixopCategory.DNS: IssueCategory.EXTERNAL_ERROR,
        FixopCategory.FIREWALL: IssueCategory.EXTERNAL_ERROR,
        FixopCategory.CONTAINER: IssueCategory.RUNTIME_ERROR,
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


# ── Public API ────────────────────────────────────────────


def adapt_issue(fi: "FixopIssue", env_name: str = "") -> Issue:
    """Convert a single fixop Issue to a taskfile Issue."""
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


def adapt_issues(fixop_issues: list, env_name: str = "") -> list[Issue]:
    """Convert a list of fixop Issues to taskfile Issues."""
    return [adapt_issue(fi, env_name) for fi in fixop_issues]


# ── Legacy category tag mapping (for runner/commands.py) ──

_CATEGORY_TAG_MAP: dict = {}
if HAS_FIXOP:
    _CATEGORY_TAG_MAP = {
        FixopCategory.SSH: "infra",
        FixopCategory.DNS: "infra",
        FixopCategory.FIREWALL: "infra",
        FixopCategory.CONTAINER: "runtime",
        FixopCategory.SYSTEMD: "infra",
        FixopCategory.TLS: "infra",
        FixopCategory.PORT: "runtime",
        FixopCategory.DEPLOY: "config",
    }


def fixop_category_to_tag(fi) -> str:
    """Map a fixop Issue's category to a legacy tag string (runtime/config/infra)."""
    return _CATEGORY_TAG_MAP.get(fi.category, "runtime")


def make_host_ctx(env) -> "HostContext":
    """Build a fixop HostContext from a taskfile Environment."""
    return HostContext(
        host=env.ssh_host,
        user=env.ssh_user or "root",
        port=env.ssh_port or 22,
        key=env.ssh_key or "~/.ssh/id_ed25519",
    )
