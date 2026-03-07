"""Placeholder value detection — find example.com, changeme, TODO, etc. in config.

Pre-run validation checks that catch misconfigured environments before
task execution. Extracted from checks.py for modularity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_WARNING,
    SEVERITY_ERROR,
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


PLACEHOLDER_PATTERNS = [
    re.compile(r'your-.*\.example\.com', re.I),
    re.compile(r'\.example\.com$', re.I),
    re.compile(r'xxx+', re.I),
    re.compile(r'changeme', re.I),
    re.compile(r'replace[_-]me', re.I),
    re.compile(r'\bTODO\b'),
    re.compile(r'^0\.0\.0\.0$'),
    re.compile(r'^placeholder', re.I),
]


def _load_env_file_vars(env_file_path: Path) -> set[str]:
    """Load variable names defined in an env file."""
    if not env_file_path.exists():
        return set()
    names: set[str] = set()
    for line in env_file_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            names.add(line.split("=", 1)[0].strip())
    return names


def _extract_fields_to_check(
    env_obj, resolved: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build fields dict and fallback_var_map from resolved vars + SSH attributes.

    Returns (fields_to_check, fallback_var_map) where fallback_var_map maps
    synthetic keys like '_ssh_host_default' to the VAR name from ${VAR:-default}.
    """
    fields = dict(resolved)
    fallback_map: dict[str, str] = {}
    for attr in ("ssh_host", "ssh_user"):
        raw = getattr(env_obj, attr, None)
        if not raw or not isinstance(raw, str):
            continue
        m = re.match(r'\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]+)\}', raw)
        if m:
            fallback_key = f"_{attr}_default"
            fields[fallback_key] = m.group(2)
            fallback_map[fallback_key] = m.group(1)
        else:
            fields[attr] = raw
    return fields, fallback_map


def _is_placeholder(val: str) -> bool:
    """Check if a value matches any known placeholder pattern."""
    return any(p.search(val) for p in PLACEHOLDER_PATTERNS)


def _should_skip_placeholder(
    key: str, fallback_var_map: dict[str, str], env_file_vars: set[str],
) -> bool:
    """Return True if the placeholder should be skipped (overridden by env_file)."""
    if key in fallback_var_map:
        return fallback_var_map[key] in env_file_vars
    return key in env_file_vars and not key.startswith("_")


def _check_env_placeholders(
    env_name: str, env_obj, config: "TaskfileConfig", taskfile_dir: Path,
) -> list[Issue]:
    """Check a single environment for placeholder values."""
    issues: list[Issue] = []
    resolved = env_obj.resolve_variables(config.variables or {})

    env_file_vars: set[str] = set()
    if env_obj.env_file:
        env_file_vars = _load_env_file_vars((taskfile_dir / env_obj.env_file).resolve())

    fields, fallback_map = _extract_fields_to_check(env_obj, resolved)

    for key, val in fields.items():
        if not isinstance(val, str) or not _is_placeholder(val):
            continue
        if _should_skip_placeholder(key, fallback_map, env_file_vars):
            continue

        real_key = key.lstrip("_").replace("_default", "").upper()
        env_file_hint = ""
        if env_obj.env_file:
            env_file_hint = f" or edit {(taskfile_dir / env_obj.env_file).resolve()}"
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message=f"'{real_key}' in env '{env_name}' looks like a placeholder: \"{val}\"",
            fix_strategy=FixStrategy.MANUAL,
            severity=SEVERITY_WARNING,
            fix_description=f"Set real value: export {real_key}=...{env_file_hint}",
            teach=(
                f"Variables with values like 'example.com' or 'your-*' are placeholders "
                f"— replace them with real data before deploying."
            ),
            layer=2,
        ))
    return issues


def check_placeholder_values(config: "TaskfileConfig") -> list[Issue]:
    """Detect variables with placeholder values (example.com, changeme, etc.)."""
    taskfile_dir = Path(config.source_path).parent.resolve() if config.source_path else Path.cwd().resolve()
    issues: list[Issue] = []
    for env_name, env_obj in (config.environments or {}).items():
        issues.extend(_check_env_placeholders(env_name, env_obj, config, taskfile_dir))
    return issues


def _check_env_file_for_target(
    config: "TaskfileConfig",
    env_name: str | None,
    taskfile_dir: Path,
) -> list[Issue]:
    """Check that the target environment's env_file exists."""
    issues: list[Issue] = []
    target_env = env_name or config.default_env or "local"
    env_obj = config.environments.get(target_env)
    if env_obj and env_obj.env_file:
        env_path = (taskfile_dir / env_obj.env_file).resolve()
        if not env_path.exists():
            example = (taskfile_dir / f"{env_obj.env_file}.example").resolve()
            hint = f" (copy from {example})" if example.exists() else ""
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"Missing env file for '{target_env}': {env_path}{hint}",
                fix_strategy=FixStrategy.AUTO if example.exists() else FixStrategy.MANUAL,
                severity=SEVERITY_ERROR,
                context={"env_file": str(env_path), "example": str(example) if example.exists() else None},
                teach=(
                    "Environment files (.env) contain variables specific to each environment "
                    "(passwords, addresses, keys). Each environment in Taskfile can have its own "
                    ".env file. Create one from .env.example as a template."
                ),
                layer=2,
            ))
    return issues
