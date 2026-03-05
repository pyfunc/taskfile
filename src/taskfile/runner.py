"""Core task runner — executes tasks with variable substitution, SSH, dependencies."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from taskfile.models import Environment, Platform, Task, TaskfileConfig
from taskfile.parser import load_taskfile, validate_taskfile
from taskfile.ssh import has_paramiko, ssh_exec, close_all as ssh_close_all

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
        return variables

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

        # @fn prefix — call embedded function
        if expanded.strip().startswith("@fn "):
            return self._run_function(expanded, task)

        # @python prefix — run inline Python expression
        if expanded.strip().startswith("@python "):
            return self._run_inline_python(expanded, task)

        # Determine if command should run via SSH
        is_remote = self._is_remote_command(expanded)

        if is_remote and self.env.ssh_target:
            if self.use_embedded_ssh:
                return self._run_embedded_ssh(expanded, task)
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
            capture = task.register is not None
            timeout = task.timeout if task.timeout > 0 else None
            result = subprocess.run(
                actual_cmd,
                shell=True,
                cwd=task.working_dir,
                env=env,
                text=True,
                stdout=subprocess.PIPE if capture else None,
                stderr=None,
                timeout=timeout,
            )
            if capture and result.stdout:
                if not task.silent:
                    sys.stdout.write(result.stdout)
                self.variables[task.register] = result.stdout.strip()
            return result.returncode
        except subprocess.TimeoutExpired:
            console.print(f"  [red]⏱ Command timed out after {task.timeout}s[/]")
            return 124
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

    def _run_embedded_ssh(self, cmd: str, task: Task) -> int:
        """Execute remote command via embedded SSH (paramiko)."""
        remote_cmd = self._strip_remote_prefix(cmd)
        if not task.silent:
            console.print(f"  [magenta]→ SSH (embedded)[/] {remote_cmd}")
        if self.dry_run:
            console.print("  [dim](dry run — skipped)[/]")
            return 0
        try:
            return ssh_exec(self.env, remote_cmd)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Interrupted[/]")
            return 130

    def _run_function(self, cmd: str, task: Task) -> int:
        """Execute an embedded function defined in the functions section.

        Syntax: @fn <function_name> [args...]
        Functions are defined in the `functions` section of Taskfile.yml.
        """
        parts = cmd.strip()[4:].split(None, 1)  # strip "@fn "
        fn_name = parts[0] if parts else ""
        fn_args = parts[1] if len(parts) > 1 else ""

        fn = self.config.functions.get(fn_name)
        if fn is None:
            console.print(f"  [red]✗ Unknown function: {fn_name}[/]")
            available = ", ".join(sorted(self.config.functions.keys()))
            if available:
                console.print(f"  [dim]Available functions: {available}[/]")
            return 1

        if not task.silent:
            console.print(f"  [cyan]→ @fn {fn_name}[/] {fn_args}")

        if self.dry_run:
            console.print("  [dim](dry run — skipped)[/]")
            return 0

        env = {**os.environ, **self.variables, "FN_ARGS": fn_args}

        if fn.lang == "python":
            return self._exec_function_python(fn, fn_args, env, task)
        elif fn.lang == "node":
            return self._exec_function_node(fn, fn_args, env, task)
        elif fn.lang == "binary":
            return self._exec_function_binary(fn, fn_args, env, task)
        else:
            # Default: shell
            return self._exec_function_shell(fn, fn_args, env, task)

    def _exec_function_shell(self, fn, fn_args: str, env: dict, task: Task) -> int:
        """Execute a shell function (inline code or file)."""
        if fn.file:
            actual_cmd = f"bash {fn.file} {fn_args}".strip()
        elif fn.code:
            actual_cmd = fn.code
        else:
            return 0
        result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
        return result.returncode

    def _exec_function_python(self, fn, fn_args: str, env: dict, task: Task) -> int:
        """Execute a Python function (inline code or file)."""
        if fn.file:
            entry = f" -c \"import runpy; runpy.run_path('{fn.file}')\"" if not fn.function else f" {fn.file}"
            if fn.function:
                actual_cmd = f"python -c \"import importlib.util, sys; spec=importlib.util.spec_from_file_location('m','{fn.file}'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.{fn.function}({repr(fn_args)})\""
            else:
                actual_cmd = f"python {fn.file} {fn_args}".strip()
        elif fn.code:
            # Write inline code to temp and execute
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
                tmp.write(fn.code)
                tmp_path = tmp.name
            actual_cmd = f"python {tmp_path} {fn_args}".strip()
        else:
            return 0
        result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
        return result.returncode

    def _exec_function_node(self, fn, fn_args: str, env: dict, task: Task) -> int:
        """Execute a Node.js function (inline code or file)."""
        if fn.file:
            actual_cmd = f"node {fn.file} {fn_args}".strip()
        elif fn.code:
            actual_cmd = f"node -e {repr(fn.code)}"
        else:
            return 0
        result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
        return result.returncode

    def _exec_function_binary(self, fn, fn_args: str, env: dict, task: Task) -> int:
        """Execute a binary/executable function."""
        if fn.file:
            actual_cmd = f"{fn.file} {fn_args}".strip()
        else:
            return 0
        result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
        return result.returncode

    def _run_inline_python(self, cmd: str, task: Task) -> int:
        """Execute inline Python code.

        Syntax: @python <python_expression_or_statement>
        Variables are available as env vars and via os.environ.
        """
        code = cmd.strip()[8:]  # strip "@python "
        if not task.silent:
            console.print(f"  [cyan]→ @python[/] {code[:80]}{'...' if len(code) > 80 else ''}")
        if self.dry_run:
            console.print("  [dim](dry run — skipped)[/]")
            return 0
        env = {**os.environ, **self.variables}
        result = subprocess.run(
            f"python -c {repr(code)}",
            shell=True, env=env, cwd=task.working_dir, text=True,
        )
        return result.returncode

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

    def _execute_commands(self, task: Task, task_name: str, start: float) -> bool:
        """Execute all commands in a task. Returns False if any failed (and not ignored).

        Supports retries (Ansible-inspired): when task.retries > 0, failed commands
        are retried up to task.retries times with task.retry_delay seconds between.
        """
        for cmd in task.commands:
            returncode = self.run_command(cmd, task)
            # Retry logic
            if returncode != 0 and task.retries > 0:
                for attempt in range(1, task.retries + 1):
                    console.print(
                        f"  [yellow]↻ Retry {attempt}/{task.retries} "
                        f"(waiting {task.retry_delay}s)[/]"
                    )
                    time.sleep(task.retry_delay)
                    returncode = self.run_command(cmd, task)
                    if returncode == 0:
                        break
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
        return True

    def _print_task_header(self, task_name: str, task: Task) -> None:
        """Print task execution header with env/platform info."""
        header = Text(f"▶ {task_name}", style="bold green")
        if task.description:
            header.append(f" — {task.description}", style="dim")
        header.append(f" [{self.env_name}]", style="bold cyan")
        if self.platform_name:
            header.append(f" [{self.platform_name}]", style="bold magenta")
        console.print(header)

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
