"""Base definitions for CI/CD generators."""

from __future__ import annotations
from pathlib import Path
import yaml
from rich.console import Console
from taskfile.models import TaskfileConfig, PipelineStage

console = Console()

TARGETS: dict[str, type["CITarget"]] = {}


def register_target(name: str):
    def decorator(cls):
        TARGETS[name] = cls
        return cls

    return decorator


class CITarget:
    """Base class for CI/CD target generators."""

    name: str = ""
    output_path: str = ""
    description: str = ""

    def __init__(self, config: TaskfileConfig):
        self.config = config
        self.pipeline = config.pipeline

    def generate(self) -> str:
        """Generate the CI/CD config content. Override in subclasses."""
        raise NotImplementedError

    def write(self, project_dir: str | Path = ".") -> Path:
        """Write the generated config to the appropriate file."""
        outpath = Path(project_dir) / self.output_path
        outpath.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate()
        outpath.write_text(content)
        return outpath

    def _tag_var(self) -> str:
        """Platform-specific variable for commit SHA / tag."""
        return "latest"

    def _stage_env_flag(self, stage: PipelineStage) -> str:
        """Build --env flag for a stage."""
        env = stage.env or self.config.default_env
        return f"--env {env}" if env else ""

    def _stage_tasks_cmd(self, stage: PipelineStage) -> str:
        """Build the taskfile command for a stage."""
        tasks = " ".join(stage.tasks)
        env_flag = self._stage_env_flag(stage)
        tag = self._tag_var()
        return f"taskfile {env_flag} {tasks} --var TAG={tag}".strip()


def _sanitize_id(name: str) -> str:
    """Make a name safe for use as YAML key / job ID."""
    return name.replace(" ", "-").replace("/", "-").lower()


def _yaml_dump(data: dict) -> str:
    """Dump dict to YAML with a generation header."""
    header = (
        "# Auto-generated from Taskfile.yml — do not edit manually\n"
        "# Regenerate with: taskfile ci generate\n\n"
    )
    return header + yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
