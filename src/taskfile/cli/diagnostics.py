"""Backward-compatibility shim — re-exports from taskfile.diagnostics package.

The monolithic diagnostics module has been split into:
  taskfile/diagnostics/
    ├── models.py       — Issue, IssueCategory, FixStrategy, DoctorReport
    ├── checks.py       — pure check_* functions → list[Issue]
    ├── fixes.py        — apply fixes (IO)
    ├── report.py       — print report (IO)
    ├── llm_repair.py   — litellm integration (optional)
    └── __init__.py     — facade ProjectDiagnostics + re-exports

All old imports continue to work:
    from taskfile.cli.diagnostics import ProjectDiagnostics
    from taskfile.cli.diagnostics import validate_before_run, IssueCategory
"""

from __future__ import annotations

# ─── Re-export new package types under old names ──────────────────

from taskfile.diagnostics import ProjectDiagnostics  # noqa: F401
from taskfile.diagnostics.models import (  # noqa: F401
    IssueCategory as _NewCategory,
    FixStrategy,
    DoctorReport,
    Issue,
    CATEGORY_LABELS as _NEW_LABELS,
    CATEGORY_HINTS as _NEW_HINTS,
)
from taskfile.diagnostics.checks import (  # noqa: F401
    validate_before_run as _new_validate_before_run,
    check_examples,
)
from taskfile.diagnostics.llm_repair import classify_runtime_error  # noqa: F401

from enum import Enum


# ─── Old 4-category IssueCategory (backward compat) ──────────────


class IssueCategory(str, Enum):
    """Old 4-category system — kept for backward compatibility.

    New code should use taskfile.diagnostics.models.IssueCategory (5 categories).
    """

    CONFIG = "config"
    ENV = "env"
    INFRA = "infra"
    RUNTIME = "runtime"


CATEGORY_LABELS = {
    IssueCategory.CONFIG: "Taskfile Config",
    IssueCategory.ENV: "Environment Files",
    IssueCategory.INFRA: "Infrastructure",
    IssueCategory.RUNTIME: "Runtime",
}

CATEGORY_HINTS = {
    IssueCategory.CONFIG: "Fix your Taskfile.yml — this is a taskfile configuration problem.",
    IssueCategory.ENV: "Create or fix .env files — copy from .env.*.example and customize.",
    IssueCategory.INFRA: "Check your infrastructure — Docker, SSH keys, ports, git.",
    IssueCategory.RUNTIME: "The software taskfile runs has a problem — check logs above.",
}


# ─── Old DiagnosticIssue (backward compat) ────────────────────────


class DiagnosticIssue:
    """Old-style diagnostic issue — kept for backward compatibility.

    New code should use taskfile.diagnostics.models.Issue.
    """

    __slots__ = ("message", "severity", "auto_fixable", "category")

    def __init__(
        self,
        message: str,
        severity: str = "warning",
        auto_fixable: bool = False,
        category: IssueCategory = IssueCategory.CONFIG,
    ):
        self.message = message
        self.severity = severity
        self.auto_fixable = auto_fixable
        self.category = category

    def as_dict(self) -> dict:
        return {
            "message": self.message,
            "severity": self.severity,
            "auto_fixable": self.auto_fixable,
            "category": self.category.value,
        }


# ─── Old validate_before_run (backward compat wrapper) ────────────


def validate_before_run(config, env_name=None, task_names=None):
    """Backward-compatible wrapper — returns old DiagnosticIssue list.

    Internally delegates to the new package's validate_before_run which
    returns list[Issue], then wraps them as old DiagnosticIssue.
    """
    new_issues = _new_validate_before_run(config, env_name, task_names)
    old_issues = []
    for iss in new_issues:
        old_cat = _map_new_to_old_category(iss.category.value)
        old_issues.append(
            DiagnosticIssue(
                message=iss.message,
                severity=iss.severity,
                auto_fixable=iss.auto_fixable,
                category=old_cat,
            )
        )
    return old_issues


def _map_new_to_old_category(new_cat_value: str) -> IssueCategory:
    """Map new 5-category → old 4-category."""
    mapping = {
        "taskfile_bug": IssueCategory.CONFIG,
        "config_error": IssueCategory.CONFIG,
        "dep_missing": IssueCategory.INFRA,
        "runtime_error": IssueCategory.RUNTIME,
        "external_error": IssueCategory.INFRA,
        # Direct matches (old values)
        "config": IssueCategory.CONFIG,
        "env": IssueCategory.ENV,
        "infra": IssueCategory.INFRA,
        "runtime": IssueCategory.RUNTIME,
    }
    return mapping.get(new_cat_value, IssueCategory.CONFIG)
