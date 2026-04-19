"""Deploy artifact validation — scan deploy/ for unresolved variables and placeholders.

Catches silent deployment failures caused by:
- ${VAR} not resolved in Traefik YAML, .container files, etc.
- {{VAR}} template placeholders left in generated files
- Placeholder values like example.com, changeme, your-domain

Called by doctor and validate-deploy gate.
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
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


# Patterns for unresolved variables in deploy files
_UNRESOLVED_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_UNRESOLVED_TMPL_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")

# Placeholder values that indicate unconfigured deploy files
_PLACEHOLDER_VALUES = re.compile(
    r"(?:example\.com|your[-_]?domain|changeme|CHANGEME|your[-_]?email"
    r"|TODO|FIXME|xxx+|placeholder|replace[-_]?me)",
    re.IGNORECASE,
)

# File patterns to scan inside deploy directories
_DEPLOY_FILE_GLOBS = (
    "**/*.yml",
    "**/*.yaml",
    "**/*.container",
    "**/*.conf",
    "**/*.toml",
    "**/*.env",
)


def _scan_file_for_unresolved(
    filepath: Path,
    taskfile_dir: Path,
) -> list[Issue]:
    """Scan a single deploy file for unresolved variables and placeholder values.

    Returns list of Issues with line-level context.
    """
    issues: list[Issue] = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return issues

    rel_path = (
        filepath.relative_to(taskfile_dir) if filepath.is_relative_to(taskfile_dir) else filepath
    )

    for lineno, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # Check for unresolved ${VAR} patterns
        for m in _UNRESOLVED_VAR_RE.finditer(line):
            var_name = m.group(1)
            issues.append(
                Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"Unresolved variable ${{{var_name}}} in {rel_path}:{lineno}",
                    severity=SEVERITY_WARNING,
                    fix_strategy=FixStrategy.MANUAL,
                    fix_description=f"Set {var_name} in your .env file or Taskfile variables, then regenerate deploy files",
                    context={
                        "file": str(rel_path),
                        "line": lineno,
                        "variable": var_name,
                        "content": stripped[:120],
                    },
                    teach=(
                        f"Deploy files should not contain raw ${{{var_name}}} placeholders — "
                        "tools like Traefik and Podman read them literally, not as variables. "
                        "Set the variable in .env.prod and regenerate deploy artifacts."
                    ),
                    layer=3,
                )
            )

        # Check for unresolved {{VAR}} patterns (Jinja/Go template style)
        for m in _UNRESOLVED_TMPL_RE.finditer(line):
            var_name = m.group(1)
            # Skip Traefik template syntax like {{ .Name }}
            if var_name.startswith("."):
                continue
            issues.append(
                Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"Unresolved template {{{{{var_name}}}}} in {rel_path}:{lineno}",
                    severity=SEVERITY_WARNING,
                    fix_strategy=FixStrategy.MANUAL,
                    fix_description=f"Set {var_name} in your Taskfile variables section",
                    context={
                        "file": str(rel_path),
                        "line": lineno,
                        "variable": var_name,
                    },
                    layer=3,
                )
            )

        # Check for placeholder values
        if _PLACEHOLDER_VALUES.search(stripped):
            issues.append(
                Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"Placeholder value in {rel_path}:{lineno}: {stripped[:80]}",
                    severity=SEVERITY_WARNING,
                    fix_strategy=FixStrategy.MANUAL,
                    fix_description="Replace placeholder values with real configuration before deploying",
                    context={
                        "file": str(rel_path),
                        "line": lineno,
                        "content": stripped[:120],
                    },
                    teach=(
                        "Placeholder values like 'example.com' or 'changeme' indicate "
                        "unconfigured deployment files. Replace them with real values "
                        "before deploying to avoid silent failures."
                    ),
                    layer=3,
                )
            )

    return issues


def check_deploy_artifacts(config: "TaskfileConfig") -> list[Issue]:
    """Scan deploy/ directory for unresolved variables and placeholder values.

    This is the Phase 8 deploy validation layer — catches silent deployment
    failures caused by:
    - ${VAR} not resolved in Traefik YAML, .container files, etc.
    - {{VAR}} template placeholders left in generated files
    - Placeholder values like example.com, changeme, your-domain

    Called by doctor and validate-deploy gate.
    """
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    deploy_dir = taskfile_dir / "deploy"

    if not deploy_dir.is_dir():
        return []

    issues: list[Issue] = []
    scanned_files: set[str] = set()

    for pattern in _DEPLOY_FILE_GLOBS:
        for filepath in deploy_dir.glob(pattern):
            if not filepath.is_file():
                continue
            # Avoid scanning the same file twice (overlapping globs)
            file_key = str(filepath.resolve())
            if file_key in scanned_files:
                continue
            scanned_files.add(file_key)

            issues.extend(_scan_file_for_unresolved(filepath, taskfile_dir))

    return issues
