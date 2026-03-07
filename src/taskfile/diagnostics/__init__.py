"""Diagnostics package — 5-layer self-diagnosing and self-healing system.

Layer 1: Preflight    — check if tools exist (docker, ssh, git, podman)
Layer 2: Validation   — check if Taskfile.yml is correct
Layer 3: Diagnostics  — check if environment is healthy (ports, SSH, env files)
Layer 4: Algorithmic  — auto-fix what can be fixed deterministically
Layer 5: LLM repair   — escalate to AI for unknown issues (optional, via litellm)
"""

from __future__ import annotations

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    DoctorReport,
)
from taskfile.diagnostics.checks import (
    check_preflight,
    check_taskfile,
    check_env_files,
    check_unresolved_variables,
    check_ports,
    check_dependent_files,
    check_docker,
    check_registry_access,
    check_ssh_keys,
    check_ssh_connectivity,
    check_remote_health,
    check_git,
    check_task_commands,
    check_examples,
    check_placeholder_values,
    check_deploy_artifacts,
    validate_before_run,
)
from taskfile.diagnostics.fixes import apply_fixes, apply_single_fix
from taskfile.diagnostics.report import (
    print_report,
    print_report_json,
    get_report_dict,
    format_summary,
)
from taskfile.diagnostics.llm_repair import (
    ask_llm_for_fix,
    classify_runtime_error,
)


class ProjectDiagnostics:
    """Facade composing checks + fixes + report — backward compatible API.

    This replaces the old monolithic ProjectDiagnostics from cli/diagnostics.py
    while preserving the same interface for wizards.py and other consumers.
    """

    def __init__(self):
        self.issues: list[tuple[str, str, bool]] = []  # legacy (message, severity, fixable)
        self._issues: list[Issue] = []
        self.fixed = 0
        self.port_fixes: dict[str, int] = {}
        self._config = None  # cached TaskfileConfig

    def _add_issue(self, issue_or_message, severity=None, auto_fixable=None, category=None) -> None:
        """Add an issue — accepts either an Issue object or old-style positional args.

        New style: _add_issue(Issue(...))
        Old style: _add_issue("message", "warning", False, IssueCategory.ENV)
        """
        if isinstance(issue_or_message, Issue):
            issue = issue_or_message
        else:
            # Old-style call: (message, severity, auto_fixable, category)
            from taskfile.diagnostics.models import _OLD_TO_NEW
            msg = issue_or_message
            sev = severity or "warning"
            fix = auto_fixable if auto_fixable is not None else False
            cat_value = category.value if hasattr(category, 'value') else str(category or "config")
            new_cat = _OLD_TO_NEW.get(cat_value, IssueCategory.CONFIG_ERROR)
            issue = Issue(
                category=new_cat,
                message=msg,
                severity=sev,
                fix_strategy=FixStrategy.AUTO if fix else FixStrategy.MANUAL,
            )
        self._issues.append(issue)
        self.issues.append((issue.message, issue.severity, issue.fix_strategy != FixStrategy.MANUAL))

    def _add_issues(self, issues: list[Issue]) -> None:
        for issue in issues:
            self._add_issue(issue)

    def _load_config(self):
        if self._config is None:
            try:
                from taskfile.parser import find_taskfile, load_taskfile
                path = find_taskfile()
                self._config = load_taskfile(path)
            except Exception:
                self._config = None
        return self._config

    # ─── Layer 1: Preflight ───

    def check_preflight(self) -> None:
        self._add_issues(check_preflight())

    # ─── Layer 2: Validation ───

    def check_taskfile(self) -> bool:
        issues = check_taskfile()
        self._add_issues(issues)
        return not any(i.severity == "error" for i in issues)

    def check_env_files(self) -> None:
        self._add_issues(check_env_files())

    def validate_taskfile_variables(self) -> None:
        config = self._load_config()
        if config:
            self._add_issues(check_unresolved_variables(config))

    def check_placeholder_values(self) -> None:
        config = self._load_config()
        if config:
            self._add_issues(check_placeholder_values(config))

    # ─── Layer 3: Diagnostics ───

    def check_ports(self) -> None:
        issues = check_ports()
        self._add_issues(issues)
        # Collect port fix suggestions for backward compat
        for iss in issues:
            if iss.context and "port_fixes" in iss.context:
                self.port_fixes.update(iss.context["port_fixes"])

    def check_docker(self) -> None:
        self._add_issues(check_docker())

    def check_registry_access(self) -> None:
        config = self._load_config()
        if config:
            self._add_issues(check_registry_access(config))

    def check_ssh_keys(self) -> None:
        self._add_issues(check_ssh_keys())

    def check_ssh_connectivity(self) -> None:
        config = self._load_config()
        if config:
            self._add_issues(check_ssh_connectivity(config))

    def check_dependent_files(self) -> None:
        config = self._load_config()
        if config:
            self._add_issues(check_dependent_files(config))

    def check_git(self) -> None:
        self._add_issues(check_git())

    def check_task_commands(self) -> None:
        config = self._load_config()
        if config:
            self._add_issues(check_task_commands(config))

    def check_remote_health(self) -> None:
        config = self._load_config()
        if config:
            self._add_issues(check_remote_health(config))

    def check_deploy_artifacts(self) -> None:
        """Scan deploy/ directory for unresolved variables and placeholders."""
        config = self._load_config()
        if config:
            self._add_issues(check_deploy_artifacts(config))

    # ─── Layer 4: Algorithmic fix ───

    def auto_fix(self) -> int:
        fixed_count = apply_fixes(self._issues)
        # Remove fixed issues from legacy list
        fixed_msgs = {i.message for i in self._issues if i.context and i.context.get("_fixed")}
        self.issues = [(m, s, f) for m, s, f in self.issues if m not in fixed_msgs]
        self._issues = [i for i in self._issues if not (i.context and i.context.get("_fixed"))]
        return fixed_count

    # ─── Layer 5: LLM repair ───

    def llm_repair(self, model: str = "gpt-4o-mini") -> list[str]:
        """Ask LLM for suggestions on unresolved issues. Returns list of suggestions."""
        suggestions = []
        config = self._load_config()
        project_context = {}
        if config:
            project_context = {
                "version": config.version,
                "name": config.name,
                "environments": list(config.environments.keys()),
                "tasks": list(config.tasks.keys()),
            }
        project_context["llm_model"] = model

        for iss in self._issues:
            if iss.fix_strategy == FixStrategy.LLM:
                suggestion = ask_llm_for_fix(iss, project_context)
                if suggestion:
                    suggestions.append(suggestion)
                    if iss.context is None:
                        iss.context = {}
                    iss.context["llm_suggestion"] = suggestion
        return suggestions

    # ─── Reporting ───

    def print_report(self, categorized: bool = True, show_teach: bool = False) -> None:
        print_report(self._issues, categorized=categorized, show_teach=show_teach)

    def print_report_json(self) -> None:
        print_report_json(self._issues)

    def get_report_dict(self) -> dict:
        return get_report_dict(self._issues)

    # ─── Static utilities ───

    @staticmethod
    def check_examples(examples_dir) -> list[dict]:
        return check_examples(examples_dir)

    @staticmethod
    def generate_env_example(taskfile_dir, env_name: str, env) -> str:
        lines = [f"# {env_name} environment template"]
        for var_name, var_value in sorted(env.variables.items()):
            lines.append(f"{var_name}={var_value}")
        if not env.variables:
            lines.append(f"APP_NAME={taskfile_dir.name}")
            lines.append("VERSION=0.1.0")
            if env.ssh_host:
                lines.append(f"# SSH: {env.ssh_user}@{env.ssh_host}")
        return "\n".join(lines) + "\n"


__all__ = [
    "Issue",
    "IssueCategory",
    "FixStrategy",
    "DoctorReport",
    "ProjectDiagnostics",
    "validate_before_run",
    "classify_runtime_error",
    "ask_llm_for_fix",
    "check_preflight",
    "check_taskfile",
    "check_env_files",
    "check_unresolved_variables",
    "check_ports",
    "check_dependent_files",
    "check_docker",
    "check_ssh_keys",
    "check_ssh_connectivity",
    "check_git",
    "check_remote_health",
    "check_task_commands",
    "check_examples",
    "check_placeholder_values",
    "check_deploy_artifacts",
    "apply_fixes",
    "apply_single_fix",
    "print_report",
    "print_report_json",
    "get_report_dict",
    "format_summary",
]
