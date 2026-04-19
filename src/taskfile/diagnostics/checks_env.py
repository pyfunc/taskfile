"""Environment variable and .env file validation checks."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_WARNING,
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


def _load_dotenv_vars(env_file_path: Path) -> dict[str, str]:
    """Parse a .env file and return key=value pairs (no shell export)."""
    result: dict[str, str] = {}
    if not env_file_path.exists():
        return result
    for line in env_file_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            result[key] = val
    return result


def _resolve_env_fields(env, taskfile_dir: Path | None = None) -> None:
    """Expand ${VAR:-default} in environment string fields.

    Mirrors the runner's dotenv loading: auto-loads .env and .env.local
    from taskfile_dir, then the environment's .env file, then os.environ.
    This ensures variables like PROD_HOST are available even when not
    exported in the shell.
    """
    from taskfile.compose import resolve_variables as _compose_resolve_variables

    # Build context: .env file vars → os.environ (shell overrides file)
    ctx: dict[str, str] = {}

    # Auto-load .env and .env.local from taskfile dir (matches runner behaviour)
    base_dir = taskfile_dir or Path.cwd()
    for dotenv_name in (".env", ".env.local"):
        dotenv_path = base_dir / dotenv_name
        if dotenv_path.is_file():
            ctx.update(_load_dotenv_vars(dotenv_path))

    # Load environment-specific .env file if set
    env_file = getattr(env, "env_file", None)
    if env_file:
        env_path = base_dir / env_file
        if env_path.is_file():
            ctx.update(_load_dotenv_vars(env_path))

    # Shell env overrides file values
    ctx.update(os.environ)

    for field_name in (
        "ssh_host",
        "ssh_user",
        "ssh_key",
        "compose_command",
        "container_runtime",
        "service_manager",
        "env_file",
        "compose_file",
        "quadlet_dir",
        "quadlet_remote_dir",
    ):
        value = getattr(env, field_name, None)
        if isinstance(value, str) and ("${" in value or "$" in value):
            setattr(env, field_name, _compose_resolve_variables(value, ctx))


def check_env_files() -> list[Issue]:
    """Check local .env files for common problems."""
    issues: list[Issue] = []
    for env_file in [".env", ".env.local", ".env.prod"]:
        env_path = Path(env_file).resolve()
        if not env_path.exists():
            continue
        content = env_path.read_text()

        # Check for empty API keys
        if "OPENROUTER_API_KEY=" in content and "OPENROUTER_API_KEY=\n" in content:
            issues.append(
                Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"{env_path}: OPENROUTER_API_KEY is empty",
                    fix_strategy=FixStrategy.MANUAL,
                    severity=SEVERITY_WARNING,
                    fix_description=f"Get key from https://openrouter.ai/settings/keys and set in {env_path}",
                    layer=3,
                )
            )

        # Check for incorrect PORT variable names
        for line in content.splitlines():
            if line.startswith("PORT=") and not line.startswith("PORT_"):
                issues.append(
                    Issue(
                        category=IssueCategory.CONFIG_ERROR,
                        message=f"{env_path}: Use PORT_WEB or PORT_LANDING instead of PORT",
                        fix_strategy=FixStrategy.AUTO,
                        severity=SEVERITY_WARNING,
                        fix_description=f"Rename PORT= to PORT_WEB= in {env_path}",
                        layer=3,
                    )
                )
                break
    return issues


def _collect_required_vars(config: "TaskfileConfig") -> set[str]:
    """Collect all ${VAR} references from config variables and SSH fields."""
    required_vars: set[str] = set()
    # From global variables
    for var_value in (config.variables or {}).values():
        if isinstance(var_value, str):
            refs = re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-[^}]*)?\}", var_value)
            required_vars.update(refs)
    # From SSH config in environments
    for env_name, env_obj in (config.environments or {}).items():
        for field_name in ("ssh_host", "ssh_user", "ssh_key"):
            value = getattr(env_obj, field_name, None) or ""
            if isinstance(value, str) and value.startswith("${"):
                m = re.match(r"\$\{(?P<var>[A-Za-z_][A-Za-z0-9_]*)", value)
                if m:
                    required_vars.add(m.group("var"))
    return required_vars


def _check_env_file_vars(env_file: str, required_vars: set[str]) -> list[Issue]:
    """Check a single .env file for missing or empty required variables."""
    issues: list[Issue] = []
    env_path = Path(env_file).resolve()
    if not env_path.exists():
        return issues
    env_content = env_path.read_text()
    env_vars: set[str] = set()
    for line in env_content.splitlines():
        if "=" in line and not line.startswith("#"):
            env_vars.add(line.split("=", 1)[0].strip())
    for var in required_vars:
        if var not in env_vars:
            issues.append(
                Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"{env_path}: Missing required variable {var}",
                    fix_strategy=FixStrategy.CONFIRM,
                    severity=SEVERITY_WARNING,
                    fix_description=f"Set {var} in {env_path}",
                    teach=(
                        f"Variable {var} is referenced in Taskfile but not defined in {env_path}. "
                        "Add it to the env file with a real value."
                    ),
                    layer=3,
                )
            )
        elif f"{var}=\n" in env_content or f"{var}=\r\n" in env_content:
            issues.append(
                Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"{env_path}: {var} is empty",
                    fix_strategy=FixStrategy.CONFIRM,
                    severity=SEVERITY_WARNING,
                    fix_description=f"Set value for {var} in {env_path}",
                    teach=(
                        f"Variable {var} exists in {env_path} but has no value. "
                        "Set it to a real value before running the task."
                    ),
                    layer=3,
                )
            )
    return issues


def check_unresolved_variables(config: "TaskfileConfig") -> list[Issue]:
    """Find ${VAR} references without values — most common problem from TEST_REPORT."""
    required_vars = _collect_required_vars(config)
    if not required_vars:
        return []
    issues: list[Issue] = []
    for env_file in [".env", ".env.local", ".env.prod", ".env.staging"]:
        issues.extend(_check_env_file_vars(env_file, required_vars))
    return issues
