"""Data models for Taskfile configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Environment:
    """Deployment environment configuration."""

    name: str
    variables: dict[str, str] = field(default_factory=dict)
    ssh_host: str | None = None
    ssh_user: str = "deploy"
    ssh_port: int = 22
    ssh_key: str | None = None
    container_runtime: str = "docker"  # docker | podman
    compose_command: str = "docker compose"  # docker compose | podman-compose
    service_manager: str = "compose"  # compose | quadlet | systemd
    env_file: str | None = None  # .env.local, .env.prod
    compose_file: str = "docker-compose.yml"  # source compose file
    quadlet_dir: str = "deploy/quadlet"  # local dir for generated .container files
    quadlet_remote_dir: str = "~/.config/containers/systemd"  # remote dir for Quadlet

    @property
    def ssh_target(self) -> str | None:
        if not self.ssh_host:
            return None
        return f"{self.ssh_user}@{self.ssh_host}"

    @property
    def ssh_opts(self) -> str:
        parts = [f"-p {self.ssh_port}"]
        if self.ssh_key:
            key_path = os.path.expanduser(self.ssh_key)
            parts.append(f"-i {key_path}")
        parts.append("-o StrictHostKeyChecking=accept-new")
        return " ".join(parts)

    @property
    def is_remote(self) -> bool:
        return self.ssh_host is not None

    def resolve_variables(self, global_vars: dict[str, str]) -> dict[str, str]:
        """Merge global variables with environment-specific ones.
        Environment variables override global ones.
        CLI --var overrides are applied separately in the runner.
        """
        merged = {**global_vars, **self.variables}
        resolved = {}
        for key, value in merged.items():
            resolved[key] = os.environ.get(key, value)
        return resolved


@dataclass
class ComposeConfig:
    """Compose-based deployment configuration."""

    file: str = "docker-compose.yml"
    override_files: list[str] = field(default_factory=list)
    network: str = "proxy"
    auto_update: bool = True


@dataclass
class Task:
    """Single task definition."""

    name: str
    description: str = ""
    commands: list[str] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    env_filter: list[str] | None = None
    working_dir: str | None = None
    silent: bool = False
    ignore_errors: bool = False
    condition: str | None = None
    stage: str | None = None  # pipeline stage this task belongs to

    def should_run_on(self, env_name: str) -> bool:
        if self.env_filter is None:
            return True
        return env_name in self.env_filter


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


def _normalize_commands(cmds: list) -> list[str]:
    """Normalize commands list — YAML can misparse 'echo key: value' as dicts."""
    result = []
    for item in cmds:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # YAML misparse: {'echo "  App': 'http://...'} → reconstruct
            for k, v in item.items():
                result.append(f"{k}: {v}" if v else str(k))
        else:
            result.append(str(item))
    return result


@dataclass
class TaskfileConfig:
    """Parsed Taskfile configuration."""

    version: str = "1"
    name: str = ""
    description: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    environments: dict[str, Environment] = field(default_factory=dict)
    tasks: dict[str, Task] = field(default_factory=dict)
    compose: ComposeConfig = field(default_factory=ComposeConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    default_env: str = "local"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskfileConfig:
        """Parse raw YAML dict into TaskfileConfig."""
        config = cls(
            version=str(data.get("version", "1")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            variables=data.get("variables", {}),
            default_env=data.get("default_env", "local"),
        )

        # Parse compose section
        compose_data = data.get("compose", {})
        if isinstance(compose_data, dict):
            config.compose = ComposeConfig(
                file=compose_data.get("file", "docker-compose.yml"),
                override_files=compose_data.get("override_files", []),
                network=compose_data.get("network", "proxy"),
                auto_update=compose_data.get("auto_update", True),
            )

        # Parse environments
        for env_name, env_data in data.get("environments", {}).items():
            if isinstance(env_data, dict):
                config.environments[env_name] = Environment(
                    name=env_name,
                    variables=env_data.get("variables", {}),
                    ssh_host=env_data.get("ssh_host"),
                    ssh_user=env_data.get("ssh_user", "deploy"),
                    ssh_port=env_data.get("ssh_port", 22),
                    ssh_key=env_data.get("ssh_key"),
                    container_runtime=env_data.get("container_runtime", "docker"),
                    compose_command=env_data.get("compose_command", "docker compose"),
                    service_manager=env_data.get("service_manager", "compose"),
                    env_file=env_data.get("env_file"),
                    compose_file=env_data.get("compose_file", "docker-compose.yml"),
                    quadlet_dir=env_data.get("quadlet_dir", "deploy/quadlet"),
                    quadlet_remote_dir=env_data.get("quadlet_remote_dir", "~/.config/containers/systemd"),
                )

        if "local" not in config.environments:
            config.environments["local"] = Environment(name="local")

        # Parse tasks
        for task_name, task_data in data.get("tasks", {}).items():
            if isinstance(task_data, dict):
                raw_cmds = task_data.get("cmds", task_data.get("commands", []))
                config.tasks[task_name] = Task(
                    name=task_name,
                    description=task_data.get("desc", task_data.get("description", "")),
                    commands=_normalize_commands(raw_cmds),
                    deps=task_data.get("deps", []),
                    env_filter=task_data.get("env", None),
                    working_dir=task_data.get("dir", None),
                    silent=task_data.get("silent", False),
                    ignore_errors=task_data.get("ignore_errors", False),
                    condition=task_data.get("condition", None),
                    stage=task_data.get("stage", None),
                )
            elif isinstance(task_data, list):
                # Shorthand: task is just a list of commands
                config.tasks[task_name] = Task(
                    name=task_name, commands=_normalize_commands(task_data)
                )

        # Parse pipeline
        pipeline_data = data.get("pipeline", {})
        if isinstance(pipeline_data, dict):
            config.pipeline = PipelineConfig.from_dict(pipeline_data)
        config.pipeline.infer_from_tasks(config.tasks)

        return config
