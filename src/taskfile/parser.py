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


def _scan_dir_for_taskfiles(directory: Path, level: int) -> list[tuple[Path, int]]:
    """Check a single directory for any Taskfile variants. Returns (path, level) pairs."""
    found = []
    for name in TASKFILE_NAMES:
        candidate = directory / name
        if candidate.is_file():
            found.append((candidate, level))
    return found


def _scan_subdirectories(start: Path, max_depth: int = 2) -> list[tuple[Path, int]]:
    """Walk subdirectories up to max_depth, collecting Taskfiles."""
    found = []
    try:
        for child in start.iterdir():
            if not child.is_dir():
                continue
            found.extend(_scan_dir_for_taskfiles(child, 1))
            if max_depth >= 2:
                try:
                    for grandchild in child.iterdir():
                        if grandchild.is_dir():
                            found.extend(_scan_dir_for_taskfiles(grandchild, 2))
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return found


def scan_nearby_taskfiles(start_dir: str | Path | None = None) -> list[tuple[Path, int]]:
    """Scan for Taskfiles in nearby directories.

    Searches:
    - 1 level up (parent directory)
    - 2 levels down (subdirectories)
    - Current directory

    Returns list of (path, relative_level) where:
    - negative = parent/ancestor directories
    - zero = current directory
    - positive = subdirectories
    """
    start = Path(start_dir or os.getcwd()).resolve()
    found = _scan_dir_for_taskfiles(start, 0)

    parent = start.parent
    if parent != start:
        found.extend(_scan_dir_for_taskfiles(parent, -1))

    found.extend(_scan_subdirectories(start))
    return found


class TaskfileNotFoundError(Exception):
    """Raised when no Taskfile is found in the search path."""

    def __init__(self, message: str, nearby: list[tuple[Path, int]] | None = None):
        super().__init__(message)
        self.nearby = nearby or []


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
        f"Run 'taskfile init' to create one.",
        nearby=scan_nearby_taskfiles(start_dir)
    )


def _parse_include_entry(entry, base_dir: Path) -> tuple[Path, str] | None:
    """Parse a single include entry into (path, prefix). Returns None if invalid."""
    if isinstance(entry, str):
        return base_dir / entry, ""
    elif isinstance(entry, dict):
        return base_dir / entry.get("path", entry.get("file", "")), entry.get("prefix", "")
    return None


def _load_include_file(inc_path: Path) -> dict:
    """Load and validate an included YAML file."""
    if not inc_path.is_file():
        raise TaskfileParseError(f"Include file not found: {inc_path}")
    try:
        with open(inc_path) as f:
            inc_raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise TaskfileParseError(f"Invalid YAML in included file {inc_path}: {e}") from e
    return inc_raw if isinstance(inc_raw, dict) else {}


def _merge_include_sections(raw: dict, inc_raw: dict, prefix: str) -> None:
    """Merge tasks/variables/environments from an included file into raw config.

    Merge order: included values first, local Taskfile wins on conflict.
    """
    # Merge tasks (with optional prefix)
    inc_tasks = inc_raw.get("tasks", {})
    if inc_tasks and isinstance(inc_tasks, dict):
        existing_tasks = raw.setdefault("tasks", {})
        for task_name, task_data in inc_tasks.items():
            key = f"{prefix}-{task_name}" if prefix else task_name
            if key not in existing_tasks:
                existing_tasks[key] = task_data

    # Merge variables (included first, local wins)
    for section in ("variables", "environments"):
        inc_section = inc_raw.get(section, {})
        if inc_section and isinstance(inc_section, dict):
            existing = raw.setdefault(section, {})
            for k, v in inc_section.items():
                if k not in existing:
                    existing[k] = v


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
        parsed = _parse_include_entry(entry, base_dir)
        if parsed is None:
            continue
        inc_path, prefix = parsed
        inc_raw = _load_include_file(inc_path)
        if inc_raw:
            _merge_include_sections(raw, inc_raw, prefix)

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
    """Check that task has at least one command or a script reference."""
    if not task.commands and not task.script:
        return [f"Task '{task_name}' has no commands and no script"]
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
