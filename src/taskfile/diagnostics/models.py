"""Diagnostic data models — Issue, IssueCategory, FixStrategy, DoctorReport."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IssueCategory(str, Enum):
    """Classification of diagnostic issues — helps users identify root cause."""

    TASKFILE_BUG = "taskfile_bug"  # bug in taskfile itself (parser crash)
    CONFIG_ERROR = "config_error"  # user misconfiguration (.env, keys, YAML)
    DEPENDENCY_MISSING = "dep_missing"  # missing tool (docker, ssh, podman)
    RUNTIME_ERROR = "runtime_error"  # app crashes, port busy, command fails
    EXTERNAL_ERROR = "external_error"  # network down, VPS offline, registry down


class FixStrategy(str, Enum):
    """How an issue can be resolved."""

    AUTO = "auto"  # fix without asking
    CONFIRM = "confirm"  # ask user before fixing
    MANUAL = "manual"  # print instructions, user must act
    LLM = "llm"  # escalate to AI for suggestion


# Severity levels
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


CATEGORY_LABELS: dict[IssueCategory, str] = {
    IssueCategory.TASKFILE_BUG: "Taskfile Bug",
    IssueCategory.CONFIG_ERROR: "Configuration Error",
    IssueCategory.DEPENDENCY_MISSING: "Missing Dependency",
    IssueCategory.RUNTIME_ERROR: "Runtime Error",
    IssueCategory.EXTERNAL_ERROR: "External / Network Error",
}

CATEGORY_HINTS: dict[IssueCategory, str] = {
    IssueCategory.TASKFILE_BUG: "This looks like a taskfile bug — please report it.",
    IssueCategory.CONFIG_ERROR: "Fix your configuration — check Taskfile.yml and .env files.",
    IssueCategory.DEPENDENCY_MISSING: "Install the missing tool or check your PATH.",
    IssueCategory.RUNTIME_ERROR: "The software taskfile runs has a problem — check logs above.",
    IssueCategory.EXTERNAL_ERROR: "External issue (network, VPS, registry) — not a taskfile problem.",
}

# Map old 4-category system → new 5-category for backward compat
_OLD_TO_NEW: dict[str, IssueCategory] = {
    "config": IssueCategory.CONFIG_ERROR,
    "env": IssueCategory.CONFIG_ERROR,
    "infra": IssueCategory.DEPENDENCY_MISSING,
    "runtime": IssueCategory.RUNTIME_ERROR,
}


@dataclass
class Issue:
    """Single diagnostic issue with category, severity, fix strategy, and context."""

    category: IssueCategory
    message: str
    fix_strategy: FixStrategy = FixStrategy.MANUAL
    severity: str = SEVERITY_WARNING
    fix_command: str | None = None
    fix_description: str | None = None
    context: dict | None = None
    # Layer that detected this issue (1-5)
    layer: int = 3
    # Educational explanation — teaches user the underlying principle
    teach: str | None = None

    @property
    def auto_fixable(self) -> bool:
        return self.fix_strategy in (FixStrategy.AUTO, FixStrategy.CONFIRM)

    def as_dict(self) -> dict:
        d = {
            "category": self.category.value,
            "message": self.message,
            "severity": self.severity,
            "fix_strategy": self.fix_strategy.value,
            "auto_fixable": self.auto_fixable,
            "layer": self.layer,
        }
        if self.fix_command:
            d["fix_command"] = self.fix_command
        if self.fix_description:
            d["fix_description"] = self.fix_description
        if self.context:
            # Filter internal keys
            d["context"] = {k: v for k, v in self.context.items() if not k.startswith("_")}
        if self.teach:
            d["teach"] = self.teach
        return d


@dataclass
class DoctorReport:
    """Aggregated report from a full doctor run."""

    issues: list[Issue] = field(default_factory=list)
    fixed: list[Issue] = field(default_factory=list)
    pending: list[Issue] = field(default_factory=list)
    external: list[Issue] = field(default_factory=list)
    llm_suggestions: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_WARNING)

    def classify(self) -> None:
        """Sort issues into fixed/pending/external buckets."""
        self.fixed.clear()
        self.pending.clear()
        self.external.clear()
        for iss in self.issues:
            if iss.context and iss.context.get("_fixed"):
                self.fixed.append(iss)
            elif iss.category == IssueCategory.EXTERNAL_ERROR:
                self.external.append(iss)
            else:
                self.pending.append(iss)

    def as_dict(self) -> dict:
        by_cat: dict[str, list[dict]] = {}
        for iss in self.issues:
            by_cat.setdefault(iss.category.value, []).append(iss.as_dict())
        return {
            "total_issues": self.total,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "auto_fixable": sum(1 for i in self.issues if i.auto_fixable),
            "fixed": len(self.fixed),
            "pending": len(self.pending),
            "external": len(self.external),
            "categories": by_cat,
            "llm_suggestions": self.llm_suggestions,
        }
