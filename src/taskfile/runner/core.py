"""Core TaskfileRunner class — facade composing TaskResolver (pure) + IO dispatch."""

from __future__ import annotations

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from taskfile.models import Environment, Platform, Task, TaskfileConfig
from taskfile.parser import load_taskfile, validate_taskfile
from taskfile.ssh import has_paramiko, close_all as ssh_close_all
from taskfile.runner.commands import run_command, execute_commands, _md, _find_task_line, _source_ref
from taskfile.runner.ssh import is_remote_command, strip_remote_prefix, wrap_ssh, run_embedded_ssh
from taskfile.runner.functions import run_function, run_inline_python
from taskfile.runner.resolver import TaskResolver

console = Console()


class TaskRunError(Exception):
    """Raised when a task command fails."""

    def __init__(self, task_name: str, command: str, returncode: int):
        self.task_name = task_name
        self.command = command
        self.returncode = returncode
        super().__init__(f"Task '{task_name}' failed: command returned {returncode}")


class TaskfileRunner:
    """Executes tasks from a Taskfile configuration.

    Composes:
    - TaskResolver (pure logic): variable expansion, filtering, task lookup
    - IO methods (this class): console output, subprocess execution, SSH
    """

    def __init__(
        self,
        config: TaskfileConfig | None = None,
        taskfile_path: str | Path | None = None,
        env_name: str | None = None,
        platform_name: str | None = None,
        var_overrides: dict[str, str] | None = None,
        dry_run: bool = False,
        verbose: bool = False,
        use_embedded_ssh: bool = True,
    ):
        loaded_config = config or load_taskfile(taskfile_path)
        self._resolver = TaskResolver(loaded_config, env_name, platform_name, var_overrides)

        self.dry_run = dry_run
        self.verbose = verbose
        self.use_embedded_ssh = use_embedded_ssh and has_paramiko()
        self._executed: set[str] = set()
        self._last_stderr: str = ""  # Store last command stderr for ErrorPresenter diagnosis

        # Emit warnings for undefined env/platform (IO concern)
        if not self._resolver.env_is_defined():
            console.print(
                f"[yellow]⚠ Environment '{self._resolver.env_name}' not defined, using defaults[/]"
            )
        if self._resolver.platform_name and not self._resolver.platform_is_defined():
            console.print(
                f"[yellow]⚠ Platform '{self._resolver.platform_name}' not defined, using defaults[/]"
            )

    # ─── Delegated properties from resolver ───

    @property
    def config(self) -> TaskfileConfig:
        return self._resolver.config

    @property
    def env_name(self) -> str:
        return self._resolver.env_name

    @property
    def platform_name(self) -> str | None:
        return self._resolver.platform_name

    @property
    def env(self) -> Environment:
        return self._resolver.env

    @property
    def platform(self) -> Platform | None:
        return self._resolver.platform

    @property
    def variables(self) -> dict[str, str]:
        return self._resolver.variables

    @variables.setter
    def variables(self, value: dict[str, str]) -> None:
        self._resolver.variables = value

    @property
    def var_overrides(self) -> dict[str, str]:
        return self._resolver.var_overrides

    def expand_variables(self, text: str) -> str:
        """Replace placeholders with resolved values."""
        return self._resolver.expand_variables(text)

    # ─── Command execution (delegated to commands module) ───

    def run_command(self, cmd: str, task: Task) -> int:
        """Execute a single command, locally or via SSH."""
        return run_command(self, cmd, task)

    def _is_remote_command(self, cmd: str) -> bool:
        """Detect if command is prefixed with @remote or @ssh."""
        return is_remote_command(cmd)

    def _strip_remote_prefix(self, cmd: str) -> str:
        """Remove @remote/@ssh prefix from command."""
        return strip_remote_prefix(cmd)

    def _wrap_ssh(self, cmd: str) -> str:
        """Wrap command in SSH call to remote host."""
        return wrap_ssh(cmd, self.env)

    def _run_embedded_ssh(self, cmd: str, task: Task) -> int:
        """Execute remote command via embedded SSH (paramiko)."""
        return run_embedded_ssh(self, cmd, task)

    def _run_function(self, cmd: str, task: Task) -> int:
        """Execute an embedded function defined in the functions section."""
        return run_function(self, cmd, task)

    def _run_inline_python(self, cmd: str, task: Task) -> int:
        """Execute inline Python code."""
        return run_inline_python(self, cmd, task)

    def _execute_script(self, task: Task, task_name: str) -> int:
        """Execute an external script file referenced by task.script."""
        from taskfile.runner.commands import execute_script
        return execute_script(self, task, task_name)

    def _execute_commands(self, task: Task, task_name: str, start: float) -> bool:
        """Execute all commands in a task."""
        return execute_commands(self, task, task_name, start)

    # ─── Condition / skip / deps ───

    def check_condition(self, task: Task) -> bool:
        """Check if task condition is met."""
        if not task.condition:
            return True
        expanded = self.expand_variables(task.condition)
        result = subprocess.run(
            expanded, shell=True, capture_output=True, text=True
        )
        return result.returncode == 0

    def _get_task_or_fail(self, task_name: str) -> Task | None:
        """Lookup task by name, print error if not found."""
        if task_name in self.config.tasks:
            return self.config.tasks[task_name]
        console.print(f"[red]✗ Unknown task: {task_name}[/]")
        available = ", ".join(sorted(self.config.tasks.keys()))
        console.print(f"[dim]  Available tasks: {available}[/]")
        return None

    def _should_skip_task(self, task: Task, task_name: str) -> bool:
        """Check if task should be skipped based on filters/condition. Returns True if skipped."""
        # Pure filter check via resolver (env/platform filters)
        skip, reason = self._resolver.should_skip_task(task, task_name)
        if skip:
            console.print(f"[yellow]⊘ Skipping '{task_name}' — {reason}[/]")
            self._executed.add(task_name)
            return True

        # IO check: condition requires subprocess execution
        if not self.check_condition(task):
            console.print(f"[yellow]⊘ Skipping '{task_name}' — condition not met[/]")
            self._executed.add(task_name)
            return True

        return False

    def _run_dependencies(self, task: Task, task_name: str) -> bool:
        """Run all task dependencies. Returns False if any failed.

        When task.parallel is True, dependencies are executed concurrently.
        """
        if not task.deps:
            return True

        if task.parallel and len(task.deps) > 1:
            return self._run_dependencies_parallel(task, task_name)

        for dep in task.deps:
            if not self.run_task(dep):
                console.print(f"[red]✗ Dependency '{dep}' failed for '{task_name}'[/]")
                return False
        return True

    def _run_dependencies_parallel(self, task: Task, task_name: str) -> bool:
        """Run task dependencies concurrently. Returns False if any failed."""
        console.print(f"  [dim]⇶ Running {len(task.deps)} deps in parallel[/]")
        failed: list[str] = []

        with ThreadPoolExecutor(max_workers=len(task.deps)) as executor:
            futures = {
                executor.submit(self.run_task, dep): dep
                for dep in task.deps
                if dep not in self._executed
            }
            for future in as_completed(futures):
                dep = futures[future]
                try:
                    if not future.result():
                        failed.append(dep)
                except Exception as exc:
                    console.print(f"[red]✗ Dependency '{dep}' raised: {exc}[/]")
                    failed.append(dep)

        if failed:
            if task.ignore_errors:
                console.print(f"  [yellow]⚠ {len(failed)} dep(s) failed (ignored): {', '.join(failed)}[/]")
                return True
            console.print(f"[red]✗ Dependencies failed for '{task_name}': {', '.join(failed)}[/]")
            return False
        return True

    # ─── Task header ───

    def _print_task_header(self, task_name: str, task: Task) -> None:
        """Print task execution header with env/platform info and YAML source location."""
        source_path = self.config.source_path
        task_line = _find_task_line(source_path, task_name)
        ref = _source_ref(source_path, task_line)

        header = Text(f"▶ {task_name}", style="bold green")
        if task.description:
            header.append(f" — {task.description}", style="dim")
        header.append(f" [{self.env_name}]", style="bold cyan")
        if self.platform_name:
            header.append(f" [{self.platform_name}]", style="bold magenta")
        if ref:
            header.append(f" ({ref})", style="dim")
        console.print(header)

    # ─── Core run methods ───

    def run_task(self, task_name: str) -> bool:
        """Run a task and its dependencies. Returns True on success."""
        if task_name in self._executed:
            return True

        task = self._get_task_or_fail(task_name)
        if task is None:
            return False

        if self._should_skip_task(task, task_name):
            return True

        if not self._run_dependencies(task, task_name):
            return False

        self._print_task_header(task_name, task)
        start = time.time()

        if not self._execute_commands(task, task_name, start):
            return False

        elapsed = time.time() - start
        console.print(f"  [green]✓ Done[/] [dim]({elapsed:.1f}s)[/]")
        self._executed.add(task_name)
        return True

    def _run_tasks_plain(self, task_names: list[str]) -> bool:
        """Run tasks sequentially without progress bar (for script-based tasks)."""
        from taskfile.notifications import notify_task_complete
        import time

        for name in task_names:
            task_start = time.time()
            if not self.run_task(name):
                return False

            task_duration = time.time() - task_start
            if task_duration > 10:
                notify_task_complete(name, True, task_duration)
        return True

    def _run_tasks_with_progress(self, task_names: list[str]) -> bool:
        """Run tasks with Rich progress bar."""
        from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
        from taskfile.notifications import notify_task_complete
        import time

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            for name in task_names:
                task = self.config.tasks.get(name)
                desc = f"Running {name}..."
                if task and task.description:
                    desc = f"{name} — {task.description}"

                progress_task = progress.add_task(desc, total=None)
                task_start = time.time()

                if not self.run_task(name):
                    progress.update(progress_task, completed=True)
                    return False

                progress.update(progress_task, completed=True)

                task_duration = time.time() - task_start
                if task_duration > 10:
                    notify_task_complete(name, True, task_duration)
        return True

    def run(self, task_names: list[str]) -> bool:
        """Run multiple tasks in order. Returns True if all succeed."""
        self._print_run_header(task_names)

        if not self._validate_pre_run(task_names):
            return False

        start_time = time.time()
        success = self._execute_task_list(task_names)
        total_duration = time.time() - start_time

        self._print_run_summary(task_names, success, total_duration)
        return success

    def _print_run_header(self, task_names: list[str]) -> None:
        """Print run context header with config, env, platform info."""
        source_name = os.path.basename(self.config.source_path) if self.config.source_path else "Taskfile.yml"
        _md(
            f"## 🚀 Running: {', '.join(f'`{t}`' for t in task_names)}\n\n"
            f"- **Config:** `{source_name}`\n"
            f"- **Environment:** `{self.env_name}`"
            + (f"\n- **Platform:** `{self.platform_name}`" if self.platform_name else "")
            + (f"\n- **Mode:** dry-run" if self.dry_run else "")
        )

    def _validate_pre_run(self, task_names: list[str]) -> bool:
        """Validate taskfile and run pre-run diagnostics. Returns False on errors."""
        warnings = validate_taskfile(self.config)
        for w in warnings:
            console.print(f"[yellow]⚠ {w}[/]")

        from taskfile.diagnostics.checks import validate_before_run
        from taskfile.diagnostics.models import CATEGORY_HINTS
        pre_issues = validate_before_run(self.config, self.env_name, task_names)
        has_errors = False
        for iss in pre_issues:
            if iss.severity == "error":
                cat_hint = CATEGORY_HINTS.get(iss.category, "")
                _md(f"- ❌ **[{iss.category.value}]** {iss.message}")
                if cat_hint:
                    _md(f"  *{cat_hint}*")
                has_errors = True
            else:
                _md(f"- ⚠️ **[{iss.category.value}]** {iss.message}")
        if has_errors:
            _md(
                "\n### Pre-run validation failed\n\n"
                "**Fix:** `taskfile doctor --fix`\n"
                "**Diagnose:** `taskfile validate`"
            )
        return not has_errors

    def _execute_task_list(self, task_names: list[str]) -> bool:
        """Execute tasks with appropriate runner (plain or progress). Cleans up SSH."""
        try:
            has_script_task = any(
                (self.config.tasks.get(n) is not None and self.config.tasks[n].script)
                for n in task_names
            )
            if has_script_task:
                return self._run_tasks_plain(task_names)
            else:
                return self._run_tasks_with_progress(task_names)
        finally:
            if self.use_embedded_ssh:
                ssh_close_all()

    def _print_run_summary(self, task_names: list[str], success: bool, total_duration: float) -> None:
        """Print run result summary and send notification for long tasks."""
        from taskfile.notifications import notify_task_complete

        if success:
            _md(
                f"\n## ✅ All tasks completed ({total_duration:.1f}s)\n\n"
                f"Tasks: {', '.join(f'`{t}`' for t in task_names)}"
            )
        else:
            _md(
                f"\n## ❌ Run failed ({total_duration:.1f}s)\n\n"
                f"**Diagnose:** `taskfile doctor`\n"
                f"**Verbose:** re-run with `-v` flag for detailed step tracing"
            )

        if len(task_names) == 1 and total_duration > 10:
            notify_task_complete(task_names[0], success, total_duration)

    # ─── List tasks ───

    def list_tasks(self) -> None:
        """Print available tasks, environments, platforms, groups and variables."""
        self._list_header()
        self._list_tasks_section()
        self._list_environments_section()
        self._list_environment_groups_section()
        self._list_platforms_section()
        self._list_variables_section()

    def _list_header(self) -> None:
        """Print project name and description panel."""
        if self.config.name:
            console.print(Panel(
                f"[bold]{self.config.name}[/]\n{self.config.description or ''}",
                border_style="blue",
            ))

    def _list_tasks_section(self) -> None:
        """Print task list with filters and dependencies."""
        console.print("\n[bold]Tasks:[/]")
        for name, task in sorted(self.config.tasks.items()):
            env_info = ""
            if task.env_filter:
                env_info = f" [dim](env: {', '.join(task.env_filter)})[/]"
            plat_info = ""
            if task.platform_filter:
                plat_info = f" [dim](platform: {', '.join(task.platform_filter)})[/]"
            deps_info = ""
            if task.deps:
                deps_info = f" [dim]← {', '.join(task.deps)}[/]"
            desc = f"  [dim]{task.description}[/]" if task.description else ""
            console.print(f"  [green]{name:20s}[/]{desc}{env_info}{plat_info}{deps_info}")

    def _list_environments_section(self) -> None:
        """Print environment list with connection info."""
        console.print(f"\n[bold]Environments:[/]")
        for name, env in sorted(self.config.environments.items()):
            default = " [yellow](default)[/]" if name == self.config.default_env else ""
            remote = f" → {env.ssh_target}" if env.ssh_target else " (local)"
            runtime = f" [{env.container_runtime}]"
            console.print(f"  [cyan]{name:20s}[/]{remote}{runtime}{default}")

    def _list_environment_groups_section(self) -> None:
        """Print environment groups if any are defined."""
        if not self.config.environment_groups:
            return
        console.print(f"\n[bold]Environment Groups:[/]")
        for name, grp in sorted(self.config.environment_groups.items()):
            members = ", ".join(grp.members) if grp.members else "empty"
            console.print(
                f"  [yellow]{name:20s}[/] strategy={grp.strategy:10s} "
                f"members=[{members}]"
            )

    def _list_platforms_section(self) -> None:
        """Print platform list if any are defined."""
        if not self.config.platforms:
            return
        console.print(f"\n[bold]Platforms:[/]")
        for name, plat in sorted(self.config.platforms.items()):
            default = " [yellow](default)[/]" if name == self.config.default_platform else ""
            desc = f"  [dim]{plat.description}[/]" if plat.description else ""
            console.print(f"  [magenta]{name:20s}[/]{desc}{default}")

    def _list_variables_section(self) -> None:
        """Print global variables."""
        if not self.config.variables:
            return
        console.print(f"\n[bold]Variables:[/]")
        for key, val in sorted(self.config.variables.items()):
            console.print(f"  [dim]{key}[/] = {val}")
