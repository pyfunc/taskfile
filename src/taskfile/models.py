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
class Platform:
    """Target platform configuration (e.g. desktop, web, mobile)."""

    name: str
    variables: dict[str, str] = field(default_factory=dict)
    build_cmd: str | None = None
    deploy_cmd: str | None = None
    description: str = ""

    def resolve_variables(self, global_vars: dict[str, str]) -> dict[str, str]:
        """Merge global variables with platform-specific ones.
        Platform variables override global ones.
        """
        merged = {**global_vars, **self.variables}
        resolved = {}
        for key, value in merged.items():
            resolved[key] = os.environ.get(key, value)
        return resolved


@dataclass
class EnvironmentGroup:
    """Group of environments sharing an update strategy (e.g. RPi fleet)."""

    name: str
    members: list[str] = field(default_factory=list)
    strategy: str = "parallel"  # rolling | parallel | canary
    max_parallel: int = 5
    canary_count: int = 1


@dataclass
class ComposeConfig:
    """Compose-based deployment configuration."""

    file: str = "docker-compose.yml"
    override_files: list[str] = field(default_factory=list)
    network: str = "proxy"
    auto_update: bool = True


@dataclass
class Function:
    """Embedded function callable from tasks via @fn prefix."""

    name: str
    lang: str = "shell"  # shell | python | node | binary
    code: str | None = None  # inline code
    file: str | None = None  # external file path
    function: str | None = None  # specific function to call (Python)
    description: str = ""


@dataclass
class Task:
    """Single task definition."""

    name: str
    description: str = ""
    commands: list[str] = field(default_factory=list)
    script: str | None = None  # external script file path (alternative to inline cmds)
    deps: list[str] = field(default_factory=list)
    env_filter: list[str] | None = None
    platform_filter: list[str] | None = None
    working_dir: str | None = None
    silent: bool = False
    ignore_errors: bool = False
    condition: str | None = None
    stage: str | None = None  # pipeline stage this task belongs to
    parallel: bool = False  # run deps in parallel (concurrent execution)
    retries: int = 0  # retry count on failure (Ansible-inspired)
    retry_delay: int = 1  # seconds between retries
    timeout: int = 0  # command timeout in seconds (0 = no timeout)
    tags: list[str] = field(default_factory=list)  # tags for selective execution
    register: str | None = None  # capture stdout into this variable name

    def should_run_on(self, env_name: str) -> bool:
        if self.env_filter is None:
            return True
        return env_name in self.env_filter

    def should_run_on_platform(self, platform_name: str | None) -> bool:
        if self.platform_filter is None:
            return True
        if platform_name is None:
            return True
        return platform_name in self.platform_filter


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
    environment_groups: dict[str, EnvironmentGroup] = field(default_factory=dict)
    tasks: dict[str, Task] = field(default_factory=dict)
    platforms: dict[str, Platform] = field(default_factory=dict)
    functions: dict[str, Function] = field(default_factory=dict)
    compose: ComposeConfig = field(default_factory=ComposeConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    default_env: str = "local"
    default_platform: str | None = None
    source_path: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskfileConfig:
        """Parse raw YAML dict into TaskfileConfig."""
        config = cls(
            version=str(data.get("version", "1")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            variables=data.get("variables", {}),
            default_env=data.get("default_env", "local"),
            default_platform=data.get("default_platform", None),
        )

        config.compose = cls._parse_compose(data.get("compose", {}))
        config.environments = cls._parse_environments(data.get("environments", {}))
        config.environment_groups = cls._parse_environment_groups(
            data.get("environment_groups", {})
        )
        config.platforms = cls._parse_platforms(data.get("platforms", {}))
        config.functions = cls._parse_functions(data.get("functions", {}))
        config.tasks = cls._parse_tasks(data.get("tasks", {}))
        config.pipeline = cls._parse_pipeline(data.get("pipeline", {}), config.tasks)

        return config

    @staticmethod
    def _parse_compose(compose_data: Any) -> ComposeConfig:
        """Parse the compose section of Taskfile."""
        if not isinstance(compose_data, dict):
            return ComposeConfig()
        return ComposeConfig(
            file=compose_data.get("file", "docker-compose.yml"),
            override_files=compose_data.get("override_files", []),
            network=compose_data.get("network", "proxy"),
            auto_update=compose_data.get("auto_update", True),
        )

    @staticmethod
    def _parse_environments(env_section: dict) -> dict[str, Environment]:
        """Parse all environment definitions, ensuring 'local' always exists."""
        environments: dict[str, Environment] = {}
        for env_name, env_data in env_section.items():
            if isinstance(env_data, dict):
                environments[env_name] = Environment(
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
        if "local" not in environments:
            environments["local"] = Environment(name="local")
        return environments

    @staticmethod
    def _parse_environment_groups(groups_section: dict) -> dict[str, EnvironmentGroup]:
        """Parse environment_groups section."""
        groups: dict[str, EnvironmentGroup] = {}
        for name, grp_data in groups_section.items():
            if isinstance(grp_data, dict):
                groups[name] = EnvironmentGroup(
                    name=name,
                    members=grp_data.get("members", []),
                    strategy=grp_data.get("strategy", "parallel"),
                    max_parallel=grp_data.get("max_parallel", 5),
                    canary_count=grp_data.get("canary_count", 1),
                )
        return groups

    @staticmethod
    def _parse_platforms(plat_section: dict) -> dict[str, Platform]:
        """Parse all platform definitions."""
        platforms: dict[str, Platform] = {}
        for plat_name, plat_data in plat_section.items():
            if isinstance(plat_data, dict):
                platforms[plat_name] = Platform(
                    name=plat_name,
                    variables=plat_data.get("variables", {}),
                    build_cmd=plat_data.get("build_cmd"),
                    deploy_cmd=plat_data.get("deploy_cmd"),
                    description=plat_data.get("desc", plat_data.get("description", "")),
                )
        return platforms

    @staticmethod
    def _parse_functions(funcs_section: dict) -> dict[str, Function]:
        """Parse the functions section."""
        functions: dict[str, Function] = {}
        if not isinstance(funcs_section, dict):
            return functions
        for fn_name, fn_data in funcs_section.items():
            if isinstance(fn_data, dict):
                functions[fn_name] = Function(
                    name=fn_name,
                    lang=fn_data.get("lang", "shell"),
                    code=fn_data.get("code"),
                    file=fn_data.get("file"),
                    function=fn_data.get("function"),
                    description=fn_data.get("desc", fn_data.get("description", "")),
                )
            elif isinstance(fn_data, str):
                # Shorthand: function is just inline code
                functions[fn_name] = Function(name=fn_name, code=fn_data)
        return functions

    @staticmethod
    def _parse_tasks(tasks_section: dict) -> dict[str, Task]:
        """Parse all task definitions."""
        tasks: dict[str, Task] = {}
        for task_name, task_data in tasks_section.items():
            if isinstance(task_data, dict):
                raw_cmds = task_data.get("cmds", task_data.get("commands", []))
                raw_tags = task_data.get("tags", [])
                if isinstance(raw_tags, str):
                    raw_tags = [t.strip() for t in raw_tags.split(",")]
                tasks[task_name] = Task(
                    name=task_name,
                    description=task_data.get("desc", task_data.get("description", "")),
                    commands=_normalize_commands(raw_cmds),
                    script=task_data.get("script", None),
                    deps=task_data.get("deps", []),
                    env_filter=task_data.get("env", None),
                    platform_filter=task_data.get("platform", None),
                    working_dir=task_data.get("dir", None),
                    silent=task_data.get("silent", False),
                    ignore_errors=task_data.get("ignore_errors", task_data.get("continue_on_error", False)),
                    condition=task_data.get("condition", None),
                    stage=task_data.get("stage", None),
                    parallel=task_data.get("parallel", False),
                    retries=task_data.get("retries", 0),
                    retry_delay=task_data.get("retry_delay", 1),
                    timeout=task_data.get("timeout", 0),
                    tags=raw_tags,
                    register=task_data.get("register", None),
                )
            elif isinstance(task_data, list):
                # Shorthand: task is just a list of commands
                tasks[task_name] = Task(
                    name=task_name, commands=_normalize_commands(task_data)
                )
        return tasks

    @staticmethod
    def _parse_pipeline(pipeline_data: Any, tasks: dict[str, Task]) -> PipelineConfig:
        """Parse pipeline section and infer stages from tasks if needed."""
        if isinstance(pipeline_data, dict):
            pipeline = PipelineConfig.from_dict(pipeline_data)
        else:
            pipeline = PipelineConfig()
        pipeline.infer_from_tasks(tasks)
        return pipeline
