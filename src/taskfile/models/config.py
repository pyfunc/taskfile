"""TaskfileConfig and ComposeConfig — main configuration container."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskfile.models.environment import Environment, Platform, EnvironmentGroup
from taskfile.models.task import Task, Function, _normalize_commands
from taskfile.models.pipeline import PipelineConfig

# ── Hosts shorthand key mappings ──────────────────────────────────

_HOST_KEY_MAP = {
    "host": "ssh_host",
    "user": "ssh_user",
    "port": "ssh_port",
    "key": "ssh_key",
    "runtime": "container_runtime",
    "manager": "service_manager",
    "compose_cmd": "compose_command",
}

_ENV_FIELDS = {
    "ssh_host",
    "ssh_user",
    "ssh_port",
    "ssh_key",
    "container_runtime",
    "compose_command",
    "service_manager",
    "env_file",
    "compose_file",
    "quadlet_dir",
    "quadlet_remote_dir",
    "variables",
}


def _normalize_host_keys(d: dict) -> dict:
    """Replace short alias keys with canonical Environment field names."""
    return {_HOST_KEY_MAP.get(k, k): v for k, v in d.items()}


def _expand_single_host(name: str, entry, norm_defaults: dict) -> dict | None:
    """Expand a single host entry into an environment dict. Returns None if invalid."""
    if isinstance(entry, str):
        return {**norm_defaults, "ssh_host": entry}
    if not isinstance(entry, dict):
        return None
    merged = {**norm_defaults, **_normalize_host_keys(entry)}
    env_data: dict[str, Any] = {}
    extra_vars: dict[str, str] = {}
    for k, v in merged.items():
        if k in _ENV_FIELDS:
            env_data[k] = v
        else:
            extra_vars[k.upper()] = str(v)
    if extra_vars:
        env_vars = env_data.get("variables", {})
        if isinstance(env_vars, dict):
            extra_vars.update(env_vars)
        env_data["variables"] = extra_vars
    return env_data


@dataclass
class ComposeConfig:
    """Compose-based deployment configuration."""

    file: str = "docker-compose.yml"
    override_files: list[str] = field(default_factory=list)
    network: str = "proxy"
    auto_update: bool = True


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
        cls._apply_environment_defaults(data)
        cls._expand_hosts_section(data)
        cls._expand_addons_section(data)
        cls._expand_deploy_section(data)

        # Accept 'vars:' as alias for 'variables:' (Go task syntax)
        raw_vars = data.get("variables") or data.get("vars") or {}
        # Normalise {{.KEY}} → {{KEY}} so dot-prefix vars resolve correctly
        normalised_vars = {
            k: v.replace("{{.", "{{") if isinstance(v, str) else v for k, v in raw_vars.items()
        }

        config = cls(
            version=str(data.get("version", "1")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            variables=normalised_vars,
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
    def _apply_environment_defaults(data: dict) -> None:
        """Apply environment_defaults to all environments in-place."""
        if "environment_defaults" not in data:
            return
        defaults = data.pop("environment_defaults") or {}
        if not isinstance(defaults, dict):
            return
        env_section = data.get("environments", {})
        for env_name, env_data in env_section.items():
            if isinstance(env_data, dict):
                merged_vars = {**defaults.get("variables", {}), **env_data.get("variables", {})}
                for k, v in defaults.items():
                    if k != "variables":
                        env_data.setdefault(k, v)
                if merged_vars:
                    env_data["variables"] = merged_vars

    @classmethod
    def _expand_hosts_section(cls, data: dict) -> None:
        """Expand hosts: shorthand into environments + environment_groups in-place."""
        if "hosts" not in data:
            return
        env_section, groups_section = cls._expand_hosts(data.pop("hosts"))
        data.setdefault("environments", {}).update(env_section)
        data.setdefault("environment_groups", {}).update(groups_section)

    @staticmethod
    def _expand_addons_section(data: dict) -> None:
        """Expand addons: into generated tasks in-place."""
        if "addons" not in data or not isinstance(data["addons"], list):
            return
        from taskfile.addons import expand_addons

        addon_tasks = expand_addons(data.pop("addons"))
        existing_tasks = data.setdefault("tasks", {})
        for task_name, task_data in addon_tasks.items():
            if task_name not in existing_tasks:
                existing_tasks[task_name] = task_data

    @staticmethod
    def _expand_deploy_section(data: dict) -> None:
        """Expand deploy: recipe into generated tasks in-place."""
        if "deploy" not in data or not isinstance(data["deploy"], dict):
            return
        from taskfile.deploy_recipes import expand_deploy_recipe

        recipe_tasks = expand_deploy_recipe(data.pop("deploy"), data.get("variables", {}))
        existing_tasks = data.setdefault("tasks", {})
        for task_name, task_data in recipe_tasks.items():
            if task_name not in existing_tasks:
                existing_tasks[task_name] = task_data

    @staticmethod
    def _expand_hosts(hosts_section: dict) -> tuple[dict, dict]:
        """Expand compact hosts: syntax into full environments + environment_groups.

        Format:
            hosts:
              _defaults:
                ssh_user: deploy
                runtime: podman          # alias for container_runtime
                env_file: .env.prod
              prod-eu:   { host: eu.example.com, region: eu-west-1 }
              prod-us:   { host: us.example.com, region: us-east-1 }
              _groups:
                all-prod: { members: [prod-eu, prod-us], strategy: canary }

        Returns (environments_dict, environment_groups_dict).
        """
        if not isinstance(hosts_section, dict):
            return {}, {}

        defaults = hosts_section.pop("_defaults", {}) or {}
        groups_raw = hosts_section.pop("_groups", {}) or {}
        norm_defaults = _normalize_host_keys(defaults)

        environments: dict[str, dict] = {}
        for name, entry in hosts_section.items():
            env_data = _expand_single_host(name, entry, norm_defaults)
            if env_data is not None:
                environments[name] = env_data

        # Parse _groups (already in standard format)
        groups: dict[str, dict] = {}
        if isinstance(groups_raw, dict):
            for grp_name, grp_data in groups_raw.items():
                if isinstance(grp_data, dict):
                    groups[grp_name] = grp_data

        return environments, groups

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
        """Parse all environment definitions, ensuring 'local' always exists.

        Smart defaults — when ssh_host is present and user didn't explicitly set:
          container_runtime → podman
          service_manager   → quadlet
          ssh_key           → ~/.ssh/id_ed25519
        When ssh_host is absent (local-like):
          container_runtime → docker
          compose_command   → docker compose
        env_file is NOT auto-inferred — set explicitly if needed.
        """
        environments: dict[str, Environment] = {}
        for env_name, env_data in env_section.items():
            if isinstance(env_data, dict):
                has_ssh = env_data.get("ssh_host") is not None
                # Smart defaults based on whether env is remote
                if has_ssh:
                    runtime_default = "podman"
                    compose_default = "podman-compose"
                    manager_default = "quadlet"
                    key_default = "~/.ssh/id_ed25519"
                else:
                    runtime_default = "docker"
                    compose_default = "docker compose"
                    manager_default = "compose"
                    key_default = None
                env_file_default = None

                environments[env_name] = Environment(
                    name=env_name,
                    variables=env_data.get("variables", {}),
                    ssh_host=env_data.get("ssh_host"),
                    ssh_user=env_data.get("ssh_user", "deploy"),
                    ssh_port=env_data.get("ssh_port", 22),
                    ssh_key=env_data.get("ssh_key", key_default),
                    container_runtime=env_data.get("container_runtime", runtime_default),
                    compose_command=env_data.get("compose_command", compose_default),
                    service_manager=env_data.get("service_manager", manager_default),
                    env_file=env_data.get("env_file", env_file_default),
                    compose_file=env_data.get("compose_file", "docker-compose.yml"),
                    quadlet_dir=env_data.get("quadlet_dir", "deploy/quadlet"),
                    quadlet_remote_dir=env_data.get(
                        "quadlet_remote_dir", "~/.config/containers/systemd"
                    ),
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
                    ignore_errors=task_data.get(
                        "ignore_errors", task_data.get("continue_on_error", False)
                    ),
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
                tasks[task_name] = Task(name=task_name, commands=_normalize_commands(task_data))
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
