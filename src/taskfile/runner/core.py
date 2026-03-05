"""Core TaskfileRunner class — init, run, run_task, list_tasks."""

from __future__ import annotations

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from taskfile.compose import resolve_variables as _compose_resolve_variables
from taskfile.models import Environment, Platform, Task, TaskfileConfig
from taskfile.parser import load_taskfile, validate_taskfile
from taskfile.ssh import has_paramiko, close_all as ssh_close_all
from taskfile.runner.commands import run_command, execute_commands
from taskfile.runner.ssh import is_remote_command, strip_remote_prefix, wrap_ssh, run_embedded_ssh
from taskfile.runner.functions import run_function, run_inline_python

console = Console()


class TaskRunError(Exception):
    """Raised when a task command fails."""

    def __init__(self, task_name: str, command: str, returncode: int):
        self.task_name = task_name
        self.command = command
        self.returncode = returncode
        super().__init__(f"Task '{task_name}' failed: command returned {returncode}")


class TaskfileRunner:
    """Executes tasks from a Taskfile configuration."""

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
        self._init_config(config, taskfile_path)
        self.env_name = env_name or self.config.default_env
        self.platform_name = platform_name or self.config.default_platform
        self.var_overrides = var_overrides or {}
        self.dry_run = dry_run
        self.verbose = verbose
        self.use_embedded_ssh = use_embedded_ssh and has_paramiko()
        self._executed: set[str] = set()

        self.env = self._init_environment()
        self.platform = self._init_platform()
        self.variables = self._init_variables()

    def _init_config(self, config: TaskfileConfig | None, taskfile_path: str | Path | None) -> None:
        """Load or accept the Taskfile configuration."""
        self.config = config or load_taskfile(taskfile_path)

    def _init_environment(self) -> Environment:
        """Initialize and validate environment configuration."""
        if self.env_name not in self.config.environments:
            console.print(
                f"[yellow]⚠ Environment '{self.env_name}' not defined, using defaults[/]"
            )
            return Environment(name=self.env_name)
        return self.config.environments[self.env_name]

    def _init_platform(self) -> Platform | None:
        """Initialize and validate platform configuration."""
        if not self.platform_name:
            return None
        if self.platform_name not in self.config.platforms:
            console.print(
                f"[yellow]⚠ Platform '{self.platform_name}' not defined, using defaults[/]"
            )
            return None
        return self.config.platforms[self.platform_name]

    def _init_variables(self) -> dict[str, str]:
        """Resolve all variables: global → env → platform → CLI overrides."""
        variables = self.env.resolve_variables(self.config.variables)
        if self.platform:
            variables.update(self.platform.variables)
        variables.update(self.var_overrides)
        # Built-in variables
        variables.setdefault("ENV", self.env_name)
        variables.setdefault("RUNTIME", self.env.container_runtime)
        variables.setdefault("COMPOSE", self.env.compose_command)
        if self.platform_name:
            variables.setdefault("PLATFORM", self.platform_name)

        # Resolve ${VAR:-default} / $VAR inside variable values.
        # Important: avoid self-reference (e.g. TAG: ${TAG:-latest}) by resolving
        # each variable against a context that excludes itself.
        for key in list(variables.keys()):
            value = variables.get(key)
            if not isinstance(value, str):
                continue
            ctx: dict[str, str] = {**os.environ, **variables}
            ctx.pop(key, None)
            variables[key] = _compose_resolve_variables(value, ctx)
        return variables

    def expand_variables(self, text: str) -> str:
        """Replace placeholders with resolved values.

        Supports:
            - {{VAR}}
            - ${VAR}
            - $VAR
            - ${VAR:-default}
        """
        if not isinstance(text, str):
            return text

        # First pass: resolve legacy {{VAR}} placeholders.
        result = text
        for key, value in self.variables.items():
            if not isinstance(value, str):
                value = str(value)
            result = result.replace(f"{{{{{key}}}}}", value)

        # Second pass: resolve ${VAR}, ${VAR:-default}, $VAR using shared resolver.
        return _compose_resolve_variables(result, {**os.environ, **self.variables})

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
        # Check environment filter
        if not task.should_run_on(self.env_name):
            console.print(
                f"[yellow]⊘ Skipping '{task_name}' — not configured for env '{self.env_name}'[/]"
            )
            self._executed.add(task_name)
            return True

        # Check platform filter
        if not task.should_run_on_platform(self.platform_name):
            console.print(
                f"[yellow]⊘ Skipping '{task_name}' — not configured for platform '{self.platform_name}'[/]"
            )
            self._executed.add(task_name)
            return True

        # Check condition
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
        """Print task execution header with env/platform info."""
        header = Text(f"▶ {task_name}", style="bold green")
        if task.description:
            header.append(f" — {task.description}", style="dim")
        header.append(f" [{self.env_name}]", style="bold cyan")
        if self.platform_name:
            header.append(f" [{self.platform_name}]", style="bold magenta")
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

    def run(self, task_names: list[str]) -> bool:
        """Run multiple tasks in order. Returns True if all succeed."""
        from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
        from taskfile.notifications import notify_task_complete
        import time

        # Validate first
        warnings = validate_taskfile(self.config)
        for w in warnings:
            console.print(f"[yellow]⚠ {w}[/]")

        success = True
        start_time = time.time()
        try:
            # Rich Progress uses live rendering; for interactive scripts (read/select)
            # it can make stdin prompts appear to "hang". Disable progress when any
            # selected task is script-based.
            has_script_task = any(
                (self.config.tasks.get(n) is not None and self.config.tasks[n].script)
                for n in task_names
            )

            if has_script_task:
                for name in task_names:
                    task_start = time.time()
                    if not self.run_task(name):
                        success = False
                        break

                    task_duration = time.time() - task_start
                    if task_duration > 10:
                        notify_task_complete(name, True, task_duration)
            else:
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
                            success = False
                            progress.update(progress_task, completed=True)
                            break

                        progress.update(progress_task, completed=True)

                        # Notification for long-running tasks (>10s)
                        task_duration = time.time() - task_start
                        if task_duration > 10:
                            notify_task_complete(name, True, task_duration)
        finally:
            if self.use_embedded_ssh:
                ssh_close_all()

        total_duration = time.time() - start_time
        if len(task_names) == 1 and total_duration > 10:
            notify_task_complete(task_names[0], success, total_duration)

        return success

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
