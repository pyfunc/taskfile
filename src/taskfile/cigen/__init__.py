"""CI/CD config generator — generates platform-specific CI/CD files."""
from __future__ import annotations
from pathlib import Path
from taskfile.models import TaskfileConfig
from taskfile.cigen.base import TARGETS, CITarget, console
from taskfile.cigen.github import *
from taskfile.cigen.gitlab import *
from taskfile.cigen.gitea import *
from taskfile.cigen.drone import *
from taskfile.cigen.jenkins import *
from taskfile.cigen.makefile import *

# ─── Public API ───────────────────────────────────────────

def generate_ci(
    config: TaskfileConfig,
    target: str,
    project_dir: str | Path = ".",
) -> Path:
    """Generate CI/CD config for a specific target platform."""
    if target not in TARGETS:
        available = ", ".join(sorted(TARGETS.keys()))
        raise ValueError(f"Unknown CI target: '{target}'. Available: {available}")

    generator = TARGETS[target](config)
    outpath = generator.write(project_dir)
    console.print(f"  [green]✓[/] {generator.description}: {outpath}")
    return outpath


def generate_all_ci(
    config: TaskfileConfig,
    project_dir: str | Path = ".",
    targets: list[str] | None = None,
) -> list[Path]:
    """Generate CI/CD configs for multiple targets."""
    target_list = targets or list(TARGETS.keys())
    generated = []
    for target in target_list:
        path = generate_ci(config, target, project_dir)
        generated.append(path)
    return generated


def list_targets() -> list[tuple[str, str, str]]:
    """Return list of (name, output_path, description) for all registered targets."""
    result = []
    for name, cls in sorted(TARGETS.items()):
        result.append((name, cls.output_path, cls.description))
    return result


def preview_ci(config: TaskfileConfig, target: str) -> str:
    """Generate CI/CD config content without writing to disk."""
    if target not in TARGETS:
        available = ", ".join(sorted(TARGETS.keys()))
        raise ValueError(f"Unknown CI target: '{target}'. Available: {available}")
    return TARGETS[target](config).generate()
