"""Docker Compose parser with env-file support.

Reads docker-compose.yml and resolves ${VAR} / ${VAR:-default} placeholders
from .env files, enabling the same compose file to work across environments.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


VAR_PATTERN = re.compile(
    r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?::?-(?P<default>[^}]*))?\}"
    r"|"
    r"\$(?P<simple>[A-Za-z_][A-Za-z0-9_]*)"
)


def load_env_file(path: str | Path) -> dict[str, str]:
    """Parse a .env file into a dict.

    Supports:
        KEY=value
        KEY="quoted value"
        KEY='single quoted'
        # comments
        empty lines
    """
    env = {}
    filepath = Path(path)
    if not filepath.is_file():
        return env

    for line in filepath.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        env[key] = value

    return env


def resolve_variables(text: str, variables: dict[str, str]) -> str:
    """Resolve ${VAR}, ${VAR:-default}, and $VAR in a string."""
    if not isinstance(text, str):
        return text

    def replacer(match):
        groups = match.groupdict()
        name = groups.get("n") or groups.get("name") or groups.get("simple")
        default = groups.get("default")
        if name and name in variables:
            return variables[name]
        if default is not None:
            return default
        # Keep unresolved vars as-is (useful for runtime vars)
        return match.group(0)

    return VAR_PATTERN.sub(replacer, text)


def resolve_dict(data: Any, variables: dict[str, str]) -> Any:
    """Recursively resolve variables in a nested dict/list structure."""
    if isinstance(data, str):
        return resolve_variables(data, variables)
    elif isinstance(data, dict):
        return {k: resolve_dict(v, variables) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_dict(item, variables) for item in data]
    return data


class ComposeFile:
    """Parsed docker-compose.yml with environment resolution."""

    def __init__(
        self,
        compose_path: str | Path = "docker-compose.yml",
        env_file: str | Path | None = None,
        extra_vars: dict[str, str] | None = None,
    ):
        self.compose_path = Path(compose_path)
        self.env_file = Path(env_file) if env_file else None
        self.extra_vars = extra_vars or {}

        # Load env variables (priority: extra_vars > env_file > os.environ)
        self.variables: dict[str, str] = {}
        if self.env_file:
            self.variables.update(load_env_file(self.env_file))
        self.variables.update(self.extra_vars)

        # Load and resolve compose
        if not self.compose_path.is_file():
            raise FileNotFoundError(f"Compose file not found: {self.compose_path}")

        with open(self.compose_path) as f:
            self.raw = yaml.safe_load(f)

        self.resolved = resolve_dict(self.raw, self.variables)

    @property
    def services(self) -> dict[str, dict]:
        """Return resolved services dict."""
        return self.resolved.get("services", {})

    @property
    def networks(self) -> dict[str, dict]:
        """Return resolved networks dict."""
        return self.resolved.get("networks", {})

    @property
    def volumes(self) -> dict[str, dict]:
        """Return resolved volumes dict."""
        return self.resolved.get("volumes", {})

    def get_service(self, name: str) -> dict | None:
        """Get a single resolved service by name."""
        return self.services.get(name)

    @staticmethod
    def _labels_list_to_dict(labels: list) -> dict[str, str]:
        """Convert list format ['key=value'] to dict, filtering for traefik labels."""
        result = {}
        for item in labels:
            if "=" in item:
                k, _, v = item.partition("=")
                if k.startswith("traefik."):
                    result[k] = v
        return result

    @staticmethod
    def _filter_traefik_labels(labels: dict) -> dict[str, str]:
        """Filter dict labels for traefik-prefixed keys."""
        return {k: v for k, v in labels.items() if k.startswith("traefik.")}

    def get_traefik_labels(self, service_name: str) -> dict[str, str]:
        """Extract Traefik labels from a service."""
        service = self.get_service(service_name)
        if not service:
            return {}

        labels = service.get("labels", {})
        if isinstance(labels, list):
            return self._labels_list_to_dict(labels)
        elif isinstance(labels, dict):
            return self._filter_traefik_labels(labels)
        return {}

    def service_names(self) -> list[str]:
        """List all service names."""
        return list(self.services.keys())
