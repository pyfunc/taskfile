"""Taskfile YAML parser — loads and validates Taskfile.yml."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from taskfile.models import TaskfileConfig

TASKFILE_NAMES = [
    "Taskfile.yml",
    "Taskfile.yaml",
    "taskfile.yml",
    "taskfile.yaml",
    ".taskfile.yml",
    ".taskfile.yaml",
]


class TaskfileNotFoundError(Exception):
    """Raised when no Taskfile is found in the search path."""


class TaskfileParseError(Exception):
    """Raised when Taskfile cannot be parsed."""


def find_taskfile(start_dir: str | Path | None = None) -> Path:
    """Find Taskfile.yml by walking up the directory tree.

    Searches from start_dir (default: cwd) upward to filesystem root,
    similar to how git finds .git directory.
    """
    current = Path(start_dir or os.getcwd()).resolve()

    while True:
        for name in TASKFILE_NAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate

        parent = current.parent
        if parent == current:
            break
        current = parent

    raise TaskfileNotFoundError(
        f"No Taskfile found. Searched for: {', '.join(TASKFILE_NAMES)}\n"
        f"Run 'taskfile init' to create one."
    )


def _resolve_includes(raw: dict, base_dir: Path) -> dict:
    """Resolve `include` section — merge tasks/variables/environments from other files.

    Include format in Taskfile.yml:
        include:
          - path: ./tasks/build.yml        # relative to Taskfile dir
          - path: ./tasks/deploy.yml
            prefix: deploy                 # optional: prefix task names

    Merge order: included files first, then local Taskfile (local wins).
    """
    includes = raw.pop("include", None)
    if not includes:
        return raw

    if not isinstance(includes, list):
        raise TaskfileParseError("'include' must be a list of file references")

    for entry in includes:
        if isinstance(entry, str):
            inc_path = base_dir / entry
            prefix = ""
        elif isinstance(entry, dict):
            inc_path = base_dir / entry.get("path", entry.get("file", ""))
            prefix = entry.get("prefix", "")
        else:
            continue

        if not inc_path.is_file():
            raise TaskfileParseError(f"Include file not found: {inc_path}")

        try:
            with open(inc_path) as f:
                inc_raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise TaskfileParseError(f"Invalid YAML in included file {inc_path}: {e}") from e

        if not isinstance(inc_raw, dict):
            continue

        # Merge tasks (with optional prefix)
        inc_tasks = inc_raw.get("tasks", {})
        if inc_tasks and isinstance(inc_tasks, dict):
            existing_tasks = raw.setdefault("tasks", {})
            for task_name, task_data in inc_tasks.items():
                key = f"{prefix}-{task_name}" if prefix else task_name
                if key not in existing_tasks:
                    existing_tasks[key] = task_data

        # Merge variables (included first, local wins)
        inc_vars = inc_raw.get("variables", {})
        if inc_vars and isinstance(inc_vars, dict):
            existing_vars = raw.setdefault("variables", {})
            for k, v in inc_vars.items():
                if k not in existing_vars:
                    existing_vars[k] = v

        # Merge environments (included first, local wins)
        inc_envs = inc_raw.get("environments", {})
        if inc_envs and isinstance(inc_envs, dict):
            existing_envs = raw.setdefault("environments", {})
            for k, v in inc_envs.items():
                if k not in existing_envs:
                    existing_envs[k] = v

    return raw


def load_taskfile(path: str | Path | None = None) -> TaskfileConfig:
    """Load and parse a Taskfile.

    Args:
        path: Explicit path to Taskfile. If None, searches automatically.

    Returns:
        Parsed TaskfileConfig.
    """
    if path is None:
        filepath = find_taskfile()
    else:
        filepath = Path(path)
        if not filepath.is_file():
            raise TaskfileNotFoundError(f"Taskfile not found: {filepath}")

    try:
        with open(filepath) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise TaskfileParseError(f"Invalid YAML in {filepath}: {e}") from e

    if not isinstance(raw, dict):
        raise TaskfileParseError(f"Taskfile must be a YAML mapping, got {type(raw).__name__}")

    raw = _resolve_includes(raw, filepath.parent)

    config = TaskfileConfig.from_dict(raw)
    return config


def _validate_tasks_exist(config: TaskfileConfig) -> list[str]:
    """Check that at least one task is defined."""
    if not config.tasks:
        return ["No tasks defined"]
    return []


def _validate_task_commands(task_name: str, task) -> list[str]:
    """Check that task has at least one command."""
    if not task.commands:
        return [f"Task '{task_name}' has no commands"]
    return []


def _validate_task_dependencies(config: TaskfileConfig, task_name: str, task) -> list[str]:
    """Check that all task dependencies exist."""
    warnings = []
    for dep in task.deps:
        if dep not in config.tasks:
            warnings.append(f"Task '{task_name}' depends on unknown task '{dep}'")
    return warnings


def _validate_task_env_filter(config: TaskfileConfig, task_name: str, task) -> list[str]:
    """Check that all environment references in filters exist."""
    warnings = []
    if task.env_filter:
        for env in task.env_filter:
            if env not in config.environments:
                warnings.append(
                    f"Task '{task_name}' references unknown environment '{env}'"
                )
    return warnings


def _validate_task_platform_filter(config: TaskfileConfig, task_name: str, task) -> list[str]:
    """Check that all platform references in filters exist."""
    warnings = []
    if task.platform_filter:
        for plat in task.platform_filter:
            if plat not in config.platforms:
                warnings.append(
                    f"Task '{task_name}' references unknown platform '{plat}'"
                )
    return warnings


def validate_taskfile(config: TaskfileConfig) -> list[str]:
    """Validate a TaskfileConfig and return list of warnings."""
    warnings = []

    warnings.extend(_validate_tasks_exist(config))

    for task_name, task in config.tasks.items():
        warnings.extend(_validate_task_commands(task_name, task))
        warnings.extend(_validate_task_dependencies(config, task_name, task))
        warnings.extend(_validate_task_env_filter(config, task_name, task))
        warnings.extend(_validate_task_platform_filter(config, task_name, task))

    return warnings
