"""Pipeline data models for CI/CD generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from taskfile.models.task import Task


@dataclass
class PipelineStage:
    """A stage in the CI/CD pipeline."""

    name: str
    tasks: list[str] = field(default_factory=list)
    env: str | None = None  # override environment for this stage
    when: str = "auto"  # auto | manual | tag | branch:main
    runner: str | None = None  # override runner image
    docker_in_docker: bool = False
    artifacts: list[str] = field(default_factory=list)
    cache: list[str] = field(default_factory=list)


@dataclass
class PipelineConfig:
    """CI/CD pipeline configuration."""

    stages: list[PipelineStage] = field(default_factory=list)
    python_version: str = "3.12"
    runner_image: str = "ubuntu-latest"
    docker_in_docker: bool = False
    cache: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    branches: list[str] = field(default_factory=lambda: ["main"])
    install_cmd: str = "pip install taskfile"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineConfig:
        config = cls(
            python_version=str(data.get("python_version", "3.12")),
            runner_image=data.get("runner_image", "ubuntu-latest"),
            docker_in_docker=data.get("docker_in_docker", False),
            cache=data.get("cache", []),
            artifacts=data.get("artifacts", []),
            secrets=data.get("secrets", []),
            branches=data.get("branches", ["main"]),
            install_cmd=data.get("install_cmd", "pip install taskfile"),
        )
        for stage_data in data.get("stages", []):
            if isinstance(stage_data, dict):
                config.stages.append(PipelineStage(
                    name=stage_data.get("name", ""),
                    tasks=stage_data.get("tasks", []),
                    env=stage_data.get("env"),
                    when=stage_data.get("when", "auto"),
                    runner=stage_data.get("runner"),
                    docker_in_docker=stage_data.get("docker_in_docker", False),
                    artifacts=stage_data.get("artifacts", []),
                    cache=stage_data.get("cache", []),
                ))
            elif isinstance(stage_data, str):
                # Shorthand: stage name = task name
                config.stages.append(PipelineStage(
                    name=stage_data, tasks=[stage_data],
                ))
        return config

    def infer_from_tasks(self, tasks: dict[str, "Task"]) -> None:
        """Auto-generate pipeline stages from task 'stage' fields if no stages defined."""
        if self.stages:
            return
        stage_map: dict[str, list[str]] = {}
        for task_name, task in tasks.items():
            if task.stage:
                stage_map.setdefault(task.stage, []).append(task_name)
        # Preserve insertion order
        for stage_name, task_names in stage_map.items():
            self.stages.append(PipelineStage(name=stage_name, tasks=task_names))
