"""Environment, Platform, and EnvironmentGroup data models."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


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
    def scp_opts(self) -> str:
        """SCP options — uses -P (uppercase) for port, unlike ssh's -p."""
        parts = [f"-P {self.ssh_port}"]
        if self.ssh_key:
            key_path = os.path.expanduser(self.ssh_key)
            parts.append(f"-i {key_path}")
        parts.append("-o StrictHostKeyChecking=accept-new")
        return " ".join(parts)

    @property
    def is_remote(self) -> bool:
        return self.ssh_host is not None

    def resolve_variables(self, global_vars: dict[str, str], dotenv_vars: dict[str, str] | None = None) -> dict[str, str]:
        """Merge global variables with environment-specific ones.
        Environment variables override global ones.
        CLI --var overrides are applied separately in the runner.

        Priority (highest wins): env-specific vars > global vars > dotenv.
        Dotenv only fills in values that still contain ${VAR} patterns.
        """
        merged = {**global_vars, **self.variables}
        resolved = {}
        env_source = dotenv_vars if dotenv_vars is not None else os.environ
        for key, value in merged.items():
            # Only use dotenv to fill values containing ${...} or when value is empty
            if isinstance(value, str) and ("${" in value or "$" in value or value == ""):
                resolved[key] = env_source.get(key, value)
            else:
                resolved[key] = value
        return resolved


@dataclass
class Platform:
    """Target platform configuration (e.g. desktop, web, mobile)."""

    name: str
    variables: dict[str, str] = field(default_factory=dict)
    build_cmd: str | None = None
    deploy_cmd: str | None = None
    description: str = ""

    def resolve_variables(self, global_vars: dict[str, str], dotenv_vars: dict[str, str] | None = None) -> dict[str, str]:
        """Merge global variables with platform-specific ones.
        Platform variables override global ones.
        """
        merged = {**global_vars, **self.variables}
        resolved = {}
        # Use dotenv_vars if provided, otherwise fall back to os.environ
        env_source = dotenv_vars if dotenv_vars is not None else os.environ
        for key, value in merged.items():
            resolved[key] = env_source.get(key, value)
        return resolved


@dataclass
class EnvironmentGroup:
    """Group of environments sharing an update strategy (e.g. RPi fleet)."""

    name: str
    members: list[str] = field(default_factory=list)
    strategy: str = "parallel"  # rolling | parallel | canary
    max_parallel: int = 5
    canary_count: int = 1
