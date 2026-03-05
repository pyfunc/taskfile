"""Core task runner — executes tasks with variable substitution, SSH, dependencies."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from taskfile.models import Environment, Platform, Task, TaskfileConfig
from taskfile.parser import load_taskfile, validate_taskfile

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
    ):
        self.config = config or load_taskfile(taskfile_path)
        self.env_name = env_name or self.config.default_env
        self.platform_name = platform_name or self.config.default_platform
        self.var_overrides = var_overrides or {}
        self.dry_run = dry_run
        self.verbose = verbose
        self._executed: set[str] = set()

        # Resolve environment
        if self.env_name not in self.config.environments:
            console.print(
                f"[yellow]⚠ Environment '{self.env_name}' not defined, using defaults[/]"
            )
            self.env = Environment(name=self.env_name)
        else:
            self.env = self.config.environments[self.env_name]

        # Resolve platform
        self.platform: Platform | None = None
        if self.platform_name:
            if self.platform_name not in self.config.platforms:
                console.print(
                    f"[yellow]⚠ Platform '{self.platform_name}' not defined, using defaults[/]"
                )
            else:
                self.platform = self.config.platforms[self.platform_name]

        # Resolve all variables: global → env → platform → CLI overrides
        self.variables = self.env.resolve_variables(self.config.variables)
        if self.platform:
            self.variables.update(self.platform.variables)
        self.variables.update(self.var_overrides)
        # Built-in variables
        self.variables.setdefault("ENV", self.env_name)
        self.variables.setdefault("RUNTIME", self.env.container_runtime)
        self.variables.setdefault("COMPOSE", self.env.compose_command)
        if self.platform_name:
            self.variables.setdefault("PLATFORM", self.platform_name)

    def expand_variables(self, text: str) -> str:
        """Replace {{VAR}} and ${VAR} placeholders with resolved values."""
        result = text
        for key, value in self.variables.items():
            if not isinstance(value, str):
                value = str(value)
            result = result.replace(f"{{{{{key}}}}}", value)
            result = result.replace(f"${{{key}}}", value)
            result = result.replace(f"${key}", value)
        return result

    def run_command(self, cmd: str, task: Task) -> int:
        """Execute a single command, locally or via SSH."""
        expanded = self.expand_variables(cmd)

        # Determine if command should run via SSH
        is_remote = self._is_remote_command(expanded)

        if is_remote and self.env.ssh_target:
            actual_cmd = self._wrap_ssh(expanded)
        else:
            actual_cmd = expanded

        if not task.silent:
            prefix = "[blue]→[/]" if not is_remote else "[magenta]→ SSH[/]"
            console.print(f"  {prefix} {actual_cmd}")

        if self.dry_run:
            console.print("  [dim](dry run — skipped)[/]")
            return 0

        try:
            env = {**os.environ, **self.variables}
            result = subprocess.run(
                actual_cmd,
                shell=True,
                cwd=task.working_dir,
                env=env,
                text=True,
                stdout=None,  # inherit stdout
                stderr=None,  # inherit stderr
            )
            return result.returncode
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Interrupted[/]")
            return 130

    def _is_remote_command(self, cmd: str) -> bool:
        """Detect if command is prefixed with @remote or @ssh."""
        return cmd.strip().startswith("@remote ") or cmd.strip().startswith("@ssh ")

    def _strip_remote_prefix(self, cmd: str) -> str:
        """Remove @remote/@ssh prefix from command."""
        stripped = cmd.strip()
        for prefix in ("@remote ", "@ssh "):
            if stripped.startswith(prefix):
                return stripped[len(prefix):]
        return stripped

    def _wrap_ssh(self, cmd: str) -> str:
        """Wrap command in SSH call to remote host."""
        remote_cmd = self._strip_remote_prefix(cmd)
        target = self.env.ssh_target
        opts = self.env.ssh_opts
        # Escape single quotes in command
        escaped = remote_cmd.replace("'", "'\\''")
        return f"ssh {opts} {target} '{escaped}'"

    def check_condition(self, task: Task) -> bool:
        """Check if task condition is met."""
        if not task.condition:
            return True
        expanded = self.expand_variables(task.condition)
        result = subprocess.run(
            expanded, shell=True, capture_output=True, text=True
        )
        return result.returncode == 0

    def run_task(self, task_name: str) -> bool:
        """Run a task and its dependencies. Returns True on success."""
        if task_name in self._executed:
            return True

        if task_name not in self.config.tasks:
            console.print(f"[red]✗ Unknown task: {task_name}[/]")
            available = ", ".join(sorted(self.config.tasks.keys()))
            console.print(f"[dim]  Available tasks: {available}[/]")
            return False

        task = self.config.tasks[task_name]

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

        # Run dependencies first
        for dep in task.deps:
            if not self.run_task(dep):
                console.print(f"[red]✗ Dependency '{dep}' failed for '{task_name}'[/]")
                return False

        # Run task
        header = Text(f"▶ {task_name}", style="bold green")
        if task.description:
            header.append(f" — {task.description}", style="dim")
        header.append(f" [{self.env_name}]", style="bold cyan")
        if self.platform_name:
            header.append(f" [{self.platform_name}]", style="bold magenta")
        console.print(header)

        start = time.time()

        for cmd in task.commands:
            returncode = self.run_command(cmd, task)
            if returncode != 0:
                if task.ignore_errors:
                    console.print(f"  [yellow]⚠ Command failed (ignored)[/]")
                else:
                    elapsed = time.time() - start
                    console.print(
                        f"[red]✗ Task '{task_name}' failed after {elapsed:.1f}s "
                        f"(exit code {returncode})[/]"
                    )
                    return False

        elapsed = time.time() - start
        console.print(f"  [green]✓ Done[/] [dim]({elapsed:.1f}s)[/]")
        self._executed.add(task_name)
        return True

    def run(self, task_names: list[str]) -> bool:
        """Run multiple tasks in order. Returns True if all succeed."""
        # Validate first
        warnings = validate_taskfile(self.config)
        for w in warnings:
            console.print(f"[yellow]⚠ {w}[/]")

        success = True
        for name in task_names:
            if not self.run_task(name):
                success = False
                break

        return success

    def list_tasks(self) -> None:
        """Print available tasks, environments, platforms and variables."""
        self._list_header()
        self._list_tasks_section()
        self._list_environments_section()
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
