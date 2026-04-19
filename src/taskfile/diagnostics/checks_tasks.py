"""Task command validation and binary checking."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_WARNING,
)
from taskfile.diagnostics.checks_env import _load_dotenv_vars

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


def check_task_commands(config: "TaskfileConfig") -> list[Issue]:
    """Check if commands in tasks reference existing binaries."""
    from taskfile.compose import resolve_variables as _compose_resolve_variables

    # Build variable context for resolving ${COMPOSE} etc.
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    var_ctx: dict[str, str] = {}
    for dotenv_name in (".env", ".env.local"):
        dotenv_path = taskfile_dir / dotenv_name
        if dotenv_path.is_file():
            var_ctx.update(_load_dotenv_vars(dotenv_path))
    var_ctx.update(config.variables)
    var_ctx.update(os.environ)

    issues: list[Issue] = []
    for task_name, task in config.tasks.items():
        for cmd in task.commands:
            resolved_cmd = _compose_resolve_variables(cmd, var_ctx)
            binary = _extract_binary(resolved_cmd)
            if binary and not shutil.which(binary) and not binary.startswith("@"):
                issues.append(
                    Issue(
                        category=IssueCategory.DEPENDENCY_MISSING,
                        message=f"Task '{task_name}': command '{binary}' not found",
                        fix_strategy=FixStrategy.LLM,
                        severity=SEVERITY_WARNING,
                        context={"binary": binary, "task": task_name, "cmd": cmd},
                        teach=(
                            f"The command '{binary}' is used in your Taskfile but not "
                            "installed on your system. Each tool in 'cmds:' must be available. "
                            "Install missing tools with your package manager (apt, brew, etc.)."
                        ),
                        layer=3,
                    )
                )
    return issues


def _extract_binary(cmd: str) -> str | None:
    """Extract the binary name from a shell command string."""
    cmd = cmd.strip()
    if not cmd:
        return None
    # Skip special prefixes
    if cmd.startswith("@"):
        return None
    # Skip shell builtins and conditionals
    if cmd.startswith(("if ", "for ", "while ", "case ", "echo ", "export ", "cd ")):
        return None
    # Handle pipe chains — check first command
    first = cmd.split("|")[0].strip()
    # Handle env var assignments
    parts = first.split()
    for part in parts:
        if "=" in part:
            continue
        return part
    return None
