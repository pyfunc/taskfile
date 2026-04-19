"""Virtual environment and Python dependency checks.

Layer 1/3: Checks if .venv exists, required packages are installed,
and lock files are in sync with pyproject.toml.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from taskfile.diagnostics.models import (
    FixStrategy,
    Issue,
    IssueCategory,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)


def _find_venv(project_root: Path | None = None) -> Path | None:
    """Return the first recognised venv directory under project_root."""
    root = project_root or Path.cwd()
    for candidate in (".venv", "venv", ".env"):
        venv_dir = root / candidate
        if (venv_dir / "bin" / "python").is_file() or (
            venv_dir / "Scripts" / "python.exe"
        ).is_file():
            return venv_dir
    return None


def _venv_python(venv_dir: Path) -> Path:
    """Return the python binary inside a venv directory."""
    for rel in ("bin/python", "Scripts/python.exe"):
        candidate = venv_dir / rel
        if candidate.is_file():
            return candidate
    return venv_dir / "bin" / "python"


def check_venv(project_root: Path | None = None) -> list[Issue]:
    """Check whether a virtual environment exists for the project."""
    root = project_root or Path.cwd()
    pyproject = root / "pyproject.toml"
    requirements = root / "requirements.txt"

    # Only warn if the project actually has Python deps declared
    if not pyproject.is_file() and not requirements.is_file():
        return []

    venv_dir = _find_venv(root)
    if venv_dir is not None:
        return []

    # Prefer poetry if poetry.lock exists, otherwise pip
    if (root / "poetry.lock").is_file():
        fix_cmd = "poetry install"
        fix_desc = "Run 'poetry install' to create .venv and install dependencies"
    elif pyproject.is_file():
        fix_cmd = "python -m venv .venv && .venv/bin/pip install -e '.[dev]'"
        fix_desc = "Create a venv and install dev dependencies"
    else:
        fix_cmd = "python -m venv .venv && .venv/bin/pip install -r requirements.txt"
        fix_desc = "Create a venv and install requirements"

    return [
        Issue(
            category=IssueCategory.DEPENDENCY_MISSING,
            message="No virtual environment found (.venv, venv, or .env)",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_WARNING,
            fix_command=fix_cmd,
            fix_description=fix_desc,
            layer=1,
            teach=(
                "A virtual environment isolates project dependencies from the system Python. "
                "Without it, package versions may conflict and 'pyqual', 'pytest', etc. may not run. "
                "Create one with 'python -m venv .venv' or 'poetry install'."
            ),
        )
    ]


def _installed_packages(python_bin: Path) -> set[str] | None:
    """Return the set of installed package names (lowercase) for a given Python binary.

    Returns None if pip cannot be queried (subprocess failure / timeout).
    An empty set means pip ran successfully but nothing is installed.
    """
    try:
        result = subprocess.run(
            [str(python_bin), "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        packages: set[str] = set()
        for line in result.stdout.splitlines():
            name = line.split("==")[0].lower().replace("-", "_")
            if name:
                packages.add(name)
        return packages
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _parse_pyproject_deps(pyproject_path: Path) -> dict[str, list[str]]:
    """Parse dependency groups from pyproject.toml (PEP 517/518/621).

    Returns mapping: group_name -> [package_name, ...]
    """
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return {}

    try:
        data = tomllib.loads(pyproject_path.read_text())
    except Exception:
        return {}

    groups: dict[str, list[str]] = {}

    project = data.get("project", {})
    core_deps = project.get("dependencies", [])
    if core_deps:
        groups["core"] = [_pkg_name(d) for d in core_deps]

    optional = project.get("optional-dependencies", {})
    for group, deps in optional.items():
        groups[group] = [_pkg_name(d) for d in deps]

    # Poetry-style
    poetry = data.get("tool", {}).get("poetry", {})
    if poetry:
        if "dependencies" in poetry:
            groups.setdefault("core", []).extend(
                k.lower() for k in poetry["dependencies"] if k.lower() != "python"
            )
        for group, group_data in poetry.get("group", {}).items():
            deps_dict = group_data.get("dependencies", {})
            groups[group] = [k.lower() for k in deps_dict]

    return groups


def _pkg_name(dep_spec: str) -> str:
    """Extract bare package name from a PEP 508 dependency specifier."""
    for sep in (">=", "<=", "!=", "==", ">", "<", "[", ";", " "):
        dep_spec = dep_spec.split(sep)[0]
    return dep_spec.strip().lower().replace("-", "_")


def check_dependencies(
    groups: list[str] | None = None,
    project_root: Path | None = None,
) -> list[Issue]:
    """Check whether declared pyproject.toml deps are installed in the active venv.

    Args:
        groups: Optional list of dependency group names to check (e.g. ['dev']).
                Defaults to checking 'core' and 'dev'.
        project_root: Project root directory (defaults to cwd).

    Returns:
        One Issue per missing package.
    """
    root = project_root or Path.cwd()
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return []

    target_groups = groups or ["core", "dev"]
    dep_groups = _parse_pyproject_deps(pyproject)
    if not dep_groups:
        return []

    # Prefer venv python, fall back to current interpreter
    venv_dir = _find_venv(root)
    python_bin = _venv_python(venv_dir) if venv_dir else Path(sys.executable)
    installed = _installed_packages(python_bin)
    if installed is None:
        return []

    issues: list[Issue] = []
    for group in target_groups:
        if group not in dep_groups:
            continue
        for pkg in dep_groups[group]:
            if pkg and pkg not in installed:
                install_cmd = (
                    "poetry install" if (root / "poetry.lock").is_file() else f"pip install {pkg}"
                )
                issues.append(
                    Issue(
                        category=IssueCategory.DEPENDENCY_MISSING,
                        message=f"Package '{pkg}' (group: {group}) is not installed",
                        fix_strategy=FixStrategy.CONFIRM,
                        severity=SEVERITY_WARNING,
                        fix_command=install_cmd,
                        fix_description=f"Install missing '{group}' dependency: {pkg}",
                        layer=1,
                        teach=(
                            f"'{pkg}' is listed in pyproject.toml [{group}] but not found "
                            f"in the current Python environment. Run '{install_cmd}' to install."
                        ),
                    )
                )
    return issues


def check_poetry_lock(project_root: Path | None = None) -> list[Issue]:
    """Check whether poetry.lock is in sync with pyproject.toml.

    Runs 'poetry check --no-interaction' which exits non-zero when the lock
    file is stale. Also warns if pyproject.toml exists but poetry.lock does not.
    """
    root = project_root or Path.cwd()
    pyproject = root / "pyproject.toml"
    lock = root / "poetry.lock"

    if not pyproject.is_file():
        return []

    # No lock file at all — only warn for poetry projects
    if not lock.is_file():
        # Detect poetry in pyproject.toml
        try:
            text = pyproject.read_text()
        except OSError:
            return []
        if "[tool.poetry]" not in text:
            return []
        return [
            Issue(
                category=IssueCategory.DEPENDENCY_MISSING,
                message="poetry.lock is missing — dependency versions are not pinned",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_WARNING,
                fix_command="poetry lock",
                fix_description="Generate poetry.lock to pin all dependency versions",
                layer=1,
                teach=(
                    "poetry.lock pins exact versions of all transitive dependencies, "
                    "ensuring reproducible installs across machines. "
                    "Run 'poetry lock' to generate it."
                ),
            )
        ]

    # Lock file exists — check if it is still in sync
    try:
        result = subprocess.run(
            ["poetry", "check", "--no-interaction"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(root),
        )
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip().splitlines()
            first_line = detail[0] if detail else "lock file may be out of date"
            return [
                Issue(
                    category=IssueCategory.DEPENDENCY_MISSING,
                    message=f"poetry.lock is out of sync: {first_line}",
                    fix_strategy=FixStrategy.CONFIRM,
                    severity=SEVERITY_WARNING,
                    fix_command="poetry lock --no-update",
                    fix_description="Regenerate poetry.lock without upgrading packages",
                    layer=1,
                    teach=(
                        "poetry.lock must match pyproject.toml. "
                        "Run 'poetry lock --no-update' to sync without upgrading packages."
                    ),
                )
            ]
    except FileNotFoundError:
        return [
            Issue(
                category=IssueCategory.DEPENDENCY_MISSING,
                message="poetry is not installed — cannot verify poetry.lock sync",
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_INFO,
                fix_description="Install poetry: https://python-poetry.org/docs/#installation",
                layer=1,
            )
        ]
    except subprocess.TimeoutExpired:
        pass

    return []
