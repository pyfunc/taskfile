"""TaskExplainer — --explain and --teach pre-run analysis.

Analyzes the execution plan WITHOUT running any commands:
- Shows what will happen step by step
- Detects @local/@remote filtering
- Finds placeholder values in resolved variables
- Checks if required binaries exist
- Checks if referenced files exist
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from taskfile.models import Task, TaskfileConfig
from taskfile.runner.resolver import TaskResolver
from taskfile.runner.ssh import is_remote_command, is_local_command

console = Console()

# Placeholder patterns (reuse from checks)
_PLACEHOLDER_WORDS = [
    "example.com",
    "your-",
    "xxx",
    "changeme",
    "replace-me",
    "replace_me",
    "todo",
    "placeholder",
    "0.0.0.0",
]


@dataclass
class StepIssue:
    """A potential problem detected in a step."""

    message: str
    severity: str = "warning"  # warning | error


@dataclass
class ExplainStep:
    """Analysis of a single command in the execution plan."""

    task_name: str
    cmd: str
    expanded: str = ""
    is_dep: bool = False
    skipped: bool = False
    skip_reason: str = ""
    issues: list[StepIssue] = field(default_factory=list)
    cmd_type: str = "local"  # local | remote | function | python | script


@dataclass
class ExplainReport:
    """Full pre-run analysis report."""

    steps: list[ExplainStep] = field(default_factory=list)
    issues: list[StepIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


class TaskExplainer:
    """Analyzes execution plan and explains what will happen."""

    def __init__(self, resolver: TaskResolver):
        self._resolver = resolver

    def explain(self, task_names: list[str]) -> ExplainReport:
        """Analyze the full execution plan for given tasks."""
        report = ExplainReport()

        # Build full execution order (with deps)
        full_order: list[str] = []
        seen: set[str] = set()
        for name in task_names:
            try:
                order = self._resolver.get_dependency_order(name)
            except ValueError as e:
                report.issues.append(StepIssue(str(e), "error"))
                continue
            for t in order:
                if t not in seen:
                    full_order.append(t)
                    seen.add(t)

        # Analyze each task's commands
        for task_name in full_order:
            task = self._resolver.get_task(task_name)
            if task is None:
                report.issues.append(StepIssue(f"Unknown task: {task_name}", "error"))
                continue

            is_dep = task_name not in task_names

            # Script
            if task.script:
                step = self._analyze_script(task, task_name, is_dep)
                report.steps.append(step)
                report.issues.extend(step.issues)

            # Commands
            for cmd in task.commands:
                step = self._analyze_command(cmd, task, task_name, is_dep)
                report.steps.append(step)
                report.issues.extend(step.issues)

        return report

    def _analyze_command(self, cmd: str, task: Task, task_name: str, is_dep: bool) -> ExplainStep:
        """Analyze a single command WITHOUT executing it."""
        expanded = self._resolver.expand_variables(cmd)
        stripped = cmd.strip()

        # Determine command type
        if stripped.startswith("@fn "):
            cmd_type = "function"
        elif stripped.startswith("@python "):
            cmd_type = "python"
        elif stripped.startswith("@remote ") or stripped.startswith("@ssh "):
            cmd_type = "remote"
        elif stripped.startswith("@local "):
            cmd_type = "local"
        else:
            cmd_type = "local"

        step = ExplainStep(
            task_name=task_name,
            cmd=cmd.strip(),
            expanded=expanded.strip(),
            is_dep=is_dep,
            cmd_type=cmd_type,
        )

        env = self._resolver.env

        # @local/@remote filtering
        if is_local_command(expanded) and env.is_remote:
            step.skipped = True
            step.skip_reason = (
                f"@local pomijany w env '{self._resolver.env_name}' (env jest zdalny)"
            )
        elif is_remote_command(expanded) and not env.ssh_target:
            step.skipped = True
            step.skip_reason = f"@remote pomijany w env '{self._resolver.env_name}' (brak ssh_host)"

        if not step.skipped:
            # Check placeholders in expanded command
            self._check_placeholders(step, expanded)
            # Check if binary exists
            self._check_binary(step, expanded, cmd_type)
            # Check referenced files
            self._check_files(step, expanded)

        return step

    def _analyze_script(self, task: Task, task_name: str, is_dep: bool) -> ExplainStep:
        """Analyze a script: directive."""
        script_path = self._resolver.expand_variables(task.script)
        step = ExplainStep(
            task_name=task_name,
            cmd=f"script: {task.script}",
            expanded=script_path,
            is_dep=is_dep,
            cmd_type="script",
        )

        # Check if script file exists
        taskfile_dir = (
            Path(self._resolver.config.source_path).parent
            if self._resolver.config.source_path
            else Path.cwd()
        )
        resolved = taskfile_dir / script_path
        if not resolved.exists():
            step.issues.append(StepIssue(f"Script '{script_path}' nie istnieje", "error"))
        elif not resolved.stat().st_mode & 0o100:
            step.issues.append(
                StepIssue(f"Script '{script_path}' nie jest wykonywalny (brak +x)", "warning")
            )

        return step

    def _check_placeholders(self, step: ExplainStep, expanded: str) -> None:
        """Check for placeholder values in the expanded command."""
        for word in _PLACEHOLDER_WORDS:
            if word in expanded.lower():
                # Try to find which variable contains the placeholder
                for k, v in self._resolver.variables.items():
                    if isinstance(v, str) and word in v.lower():
                        step.issues.append(StepIssue(f'{k} = "{v}" (placeholder)', "warning"))
                        break
                else:
                    step.issues.append(
                        StepIssue(f"Komenda zawiera placeholder: '{word}'", "warning")
                    )
                break  # one placeholder warning per step is enough

    def _check_binary(self, step: ExplainStep, expanded: str, cmd_type: str) -> None:
        """Check if the command's binary exists on PATH."""
        if cmd_type in ("function", "python", "script"):
            return
        # Strip prefixes
        check = expanded.strip()
        for prefix in ("@remote ", "@local ", "@ssh "):
            if check.startswith(prefix):
                check = check[len(prefix) :]
                break
        # For remote commands, we can't check binary on local system
        if cmd_type == "remote":
            return
        # Extract first word (the binary)
        parts = check.split()
        if not parts:
            return
        binary = parts[0]
        # Skip shell builtins and variable assignments
        if "=" in binary or binary in (
            "if",
            "for",
            "while",
            "case",
            "echo",
            "export",
            "cd",
            "test",
            "[",
            "true",
            "false",
        ):
            return
        if not shutil.which(binary):
            step.issues.append(StepIssue(f"Komenda '{binary}' nie znaleziona w PATH", "warning"))

    def _check_files(self, step: ExplainStep, expanded: str) -> None:
        """Check if referenced local files exist in scp/rsync/cp commands."""
        check = expanded.strip()
        for prefix in ("@remote ", "@local ", "@ssh "):
            if check.startswith(prefix):
                check = check[len(prefix) :]
                break
        parts = check.split()
        if not parts:
            return
        binary = parts[0]
        if binary not in ("scp", "rsync", "cp"):
            return
        for part in parts[1:]:
            if part.startswith("-") or ":" in part or "$" in part or "*" in part:
                continue
            p = Path(part)
            if not p.is_absolute():
                continue
            if not p.exists():
                step.issues.append(StepIssue(f"Plik '{part}' nie istnieje", "warning"))


# ─── Rendering ────────────────────────────────────────────────────────────


def print_explain_report(report: ExplainReport, task_names: list[str], env_name: str) -> None:
    """Print the --explain report to console."""
    console.print(
        Panel(
            f"[bold]📋 Plan wykonania: {', '.join(task_names)}[/]  (env=[cyan]{env_name}[/])",
            border_style="blue",
        )
    )

    current_task = None
    step_num = 0

    for step in report.steps:
        if step.task_name != current_task:
            current_task = step.task_name
            dep_tag = " [dim](dep)[/]" if step.is_dep else ""
            console.print(f"\n  [bold green]{current_task}[/]{dep_tag}")

        step_num += 1
        icon = _cmd_type_icon(step.cmd_type)

        if step.skipped:
            console.print(f"    [dim]⏭ {icon} {step.cmd[:80]}[/]")
            console.print(f"      [dim]↳ {step.skip_reason}[/]")
        else:
            console.print(f"    {icon} {step.cmd[:80]}")
            if step.expanded != step.cmd and step.expanded:
                console.print(f"      [dim]↳ {step.expanded[:100]}[/]")

        for issue in step.issues:
            sev_icon = "[yellow]⚠[/]" if issue.severity == "warning" else "[red]✗[/]"
            console.print(f"      {sev_icon}  {issue.message}")

    # Summary
    if report.issues:
        console.print(f"\n  [yellow bold]Problemy wykryte ({len(report.issues)}):[/]")
        for i, issue in enumerate(report.issues, 1):
            sev_icon = "⚠" if issue.severity == "warning" else "✗"
            console.print(f"    {i}. {sev_icon} {issue.message}")

    if not report.issues:
        console.print("\n  [green]✓ Brak problemów — gotowe do uruchomienia[/]")


def _print_teach_deps(task_names: list[str], config: TaskfileConfig) -> None:
    """Print dependency explanations."""
    for name in task_names:
        task = config.tasks.get(name)
        if task and task.deps:
            dep_str = ", ".join(f"'{d}'" for d in task.deps)
            console.print(
                f"\n  '{name}' ma zależność {dep_str} — najpierw uruchomi się "
                + ("ta zależność." if len(task.deps) == 1 else "te zależności.")
            )


def _print_teach_prefix_info(has_local: bool, has_remote: bool) -> None:
    """Print @local/@remote prefix explanation."""
    if has_local or has_remote:
        console.print("\n  Twój task używa prefiksów @local i @remote:")
        console.print(
            "  • [bold]@local[/]  — uruchamia się TYLKO gdy env nie ma ssh_host (lokalne środowisko)"
        )
        console.print(
            "  • [bold]@remote[/] — uruchamia się TYLKO gdy env ma ssh_host (zdalny serwer)"
        )


def _print_teach_current_env(report: ExplainReport, env_name: str) -> None:
    """Print what runs in current env."""
    console.print(f"\n  Przy env='[cyan]{env_name}[/]' zostaną uruchomione:")
    for step in report.steps:
        if step.skipped:
            console.print(f"    [dim]⏭ {step.cmd[:80]} (pomijany — {step.skip_reason})[/]")
        else:
            console.print(f"    [green]✅[/] {step.cmd[:80]}")


def _print_remote_alt_env(
    remote_envs: list[str], env_name: str, report: ExplainReport, config: TaskfileConfig
) -> None:
    """Print alternative environment steps for remote environments."""
    if not remote_envs or env_name in remote_envs:
        return
    alt = remote_envs[0]
    console.print(f"\n  Przy env='[cyan]{alt}[/]' (zdalny) zostaną uruchomione:")
    for step in report.steps:
        is_remote = step.cmd_type == "remote"
        is_non_local = step.cmd_type != "local" and "@local" not in step.cmd
        if is_remote or is_non_local:
            console.print(f"    [green]✅[/] {step.cmd[:80]}")
        else:
            skip_reason = f"pomijany — {alt} jest zdalny"
            console.print(f"    [dim]⏭ {step.cmd[:80]} ({skip_reason})[/]")


def _print_local_alt_env(local_envs: list[str], env_name: str, report: ExplainReport) -> None:
    """Print alternative environment steps for local environments."""
    if not local_envs or env_name in local_envs:
        return
    alt = local_envs[0]
    console.print(f"\n  Przy env='[cyan]{alt}[/]' (lokalny) zostaną uruchomione:")
    for step in report.steps:
        if step.cmd_type != "remote":
            console.print(f"    [green]✅[/] {step.cmd[:80]}")
        else:
            skip_reason = f"pomijany — {alt} brak SSH"
            console.print(f"    [dim]⏭ {step.cmd[:80]} ({skip_reason})[/]")


def _print_teach_alt_env(
    report: ExplainReport,
    env_name: str,
    config: TaskfileConfig,
) -> None:
    """Print alternative env behavior for @local/@remote commands."""
    remote_envs = [n for n, e in config.environments.items() if e.is_remote]
    local_envs = [n for n, e in config.environments.items() if not e.is_remote]

    _print_remote_alt_env(remote_envs, env_name, report, config)
    _print_local_alt_env(local_envs, env_name, report)


def print_teach_report(
    report: ExplainReport,
    task_names: list[str],
    env_name: str,
    config: TaskfileConfig,
) -> None:
    """Print the --teach educational report."""
    console.print(
        Panel(
            f"[bold]📖 Task '{', '.join(task_names)}' — co się stanie[/]",
            border_style="magenta",
        )
    )

    _print_teach_deps(task_names, config)

    has_local = any(s.cmd_type == "local" and "@local" in s.cmd for s in report.steps)
    has_remote = any(s.cmd_type == "remote" for s in report.steps)

    _print_teach_prefix_info(has_local, has_remote)
    _print_teach_current_env(report, env_name)

    if has_local and has_remote:
        _print_teach_alt_env(report, env_name, config)

    if report.issues:
        console.print("\n  [yellow bold]⚠ Problemy:[/]")
        for i, issue in enumerate(report.issues, 1):
            console.print(f"    {i}. {issue.message}")

    console.print()


def _cmd_type_icon(cmd_type: str) -> str:
    return {
        "local": "💻",
        "remote": "🌐",
        "function": "⚡",
        "python": "🐍",
        "script": "📜",
    }.get(cmd_type, "→")
