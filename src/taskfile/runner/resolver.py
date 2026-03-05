"""TaskResolver — pure logic for task resolution, variable expansion, and filtering.

This module contains no IO (no subprocess, no console printing). It resolves
tasks, checks filters/conditions, expands variables, and determines execution order.
"""

from __future__ import annotations

import os
from pathlib import Path

from taskfile.compose import resolve_variables as _compose_resolve_variables
from taskfile.models import Environment, Platform, Task, TaskfileConfig
from taskfile.parser import load_taskfile


class TaskResolver:
    """Pure-logic task resolver: variable expansion, filtering, dependency ordering.

    No subprocess calls, no console output. Suitable for testing without IO.
    """

    def __init__(
        self,
        config: TaskfileConfig,
        env_name: str | None = None,
        platform_name: str | None = None,
        var_overrides: dict[str, str] | None = None,
    ):
        self.config = config
        self.env_name = env_name or config.default_env
        self.platform_name = platform_name or config.default_platform
        self.var_overrides = var_overrides or {}

        self.env = self._resolve_environment()
        self.platform = self._resolve_platform()
        self.variables = self._resolve_variables()

    @classmethod
    def from_path(
        cls,
        taskfile_path: str | Path | None = None,
        env_name: str | None = None,
        platform_name: str | None = None,
        var_overrides: dict[str, str] | None = None,
    ) -> "TaskResolver":
        """Create a resolver by loading a Taskfile from disk."""
        config = load_taskfile(taskfile_path)
        return cls(config, env_name, platform_name, var_overrides)

    # ─── Environment / platform resolution ───

    def _resolve_environment(self) -> Environment:
        """Resolve environment, returning defaults if not defined."""
        if self.env_name in self.config.environments:
            return self.config.environments[self.env_name]
        return Environment(name=self.env_name)

    def _resolve_platform(self) -> Platform | None:
        """Resolve platform, returning None if not defined."""
        if not self.platform_name:
            return None
        return self.config.platforms.get(self.platform_name)

    def _resolve_variables(self) -> dict[str, str]:
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
        for key in list(variables.keys()):
            value = variables.get(key)
            if not isinstance(value, str):
                continue
            ctx: dict[str, str] = {**os.environ, **variables}
            ctx.pop(key, None)
            variables[key] = _compose_resolve_variables(value, ctx)
        return variables

    # ─── Variable expansion ───

    def expand_variables(self, text: str) -> str:
        """Replace placeholders with resolved values.

        Supports: {{VAR}}, ${VAR}, $VAR, ${VAR:-default}
        """
        if not isinstance(text, str):
            return text

        result = text
        for key, value in self.variables.items():
            if not isinstance(value, str):
                value = str(value)
            result = result.replace(f"{{{{{key}}}}}", value)

        return _compose_resolve_variables(result, {**os.environ, **self.variables})

    # ─── Task lookup and filtering (pure) ───

    def get_task(self, task_name: str) -> Task | None:
        """Lookup task by name. Returns None if not found."""
        return self.config.tasks.get(task_name)

    def available_task_names(self) -> list[str]:
        """Return sorted list of all defined task names."""
        return sorted(self.config.tasks.keys())

    def should_skip_task(self, task: Task, task_name: str) -> tuple[bool, str]:
        """Check if task should be skipped. Returns (skip, reason).

        Pure check — does NOT execute condition commands. Condition checking
        requires IO and is handled by CommandDispatcher.
        """
        if not task.should_run_on(self.env_name):
            return True, f"not configured for env '{self.env_name}'"
        if not task.should_run_on_platform(self.platform_name):
            return True, f"not configured for platform '{self.platform_name}'"
        return False, ""

    def get_dependency_order(self, task_name: str, visited: set[str] | None = None) -> list[str]:
        """Return flat execution order for a task and its deps (depth-first).

        Raises ValueError on circular dependencies.
        """
        if visited is None:
            visited = set()
        if task_name in visited:
            raise ValueError(f"Circular dependency detected: {task_name}")

        task = self.get_task(task_name)
        if task is None:
            return [task_name]  # will fail at runtime

        visited.add(task_name)
        order: list[str] = []
        for dep in task.deps:
            if dep not in order:
                order.extend(self.get_dependency_order(dep, visited.copy()))
        order.append(task_name)
        return order

    def env_is_defined(self) -> bool:
        """Check if the current environment name is defined in config."""
        return self.env_name in self.config.environments

    def platform_is_defined(self) -> bool:
        """Check if the current platform name is defined in config."""
        return self.platform_name is not None and self.platform_name in self.config.platforms
