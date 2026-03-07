"""Docker Compose parser with env-file support.

Reads docker-compose.yml and resolves ${VAR} / ${VAR:-default} placeholders
from .env files, enabling the same compose file to work across environments.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PortMapping:
    """Represents a port mapping from docker-compose."""
    host_port: int
    container_port: int
    service_name: str
    host_ip: str | None = None


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
            return str(variables[name])
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

    @classmethod
    def from_yaml(cls, compose_path: str | Path, env_file: str | Path | None = None) -> "ComposeFile":
        """Create a ComposeFile instance from a YAML file path."""
        return cls(compose_path, env_file=env_file)

    def get_all_ports(self) -> list[PortMapping]:
        """Extract all port mappings from all services.
        
        Returns a list of PortMapping objects with host_port, container_port, and service_name.
        """
        ports = []
        for service_name, service in self.services.items():
            service_ports = service.get("ports", [])
            if not service_ports:
                continue
            
            for port_mapping in service_ports:
                parsed = self._parse_port_mapping(port_mapping)
                if parsed:
                    ports.append(PortMapping(
                        host_port=parsed["host_port"],
                        container_port=parsed["container_port"],
                        service_name=service_name,
                        host_ip=parsed.get("host_ip"),
                    ))
        return ports

    def _parse_port_mapping(self, port_mapping: str | dict) -> dict | None:
        """Parse a port mapping string or dict.
        
        Handles formats like:
        - "8080:80" (host:container)
        - "127.0.0.1:8080:80" (ip:host:container)
        - {"target": 80, "published": 8080}
        """
        if isinstance(port_mapping, dict):
            # Long form: {"target": 80, "published": 8080, "host_ip": "127.0.0.1"}
            return {
                "host_port": int(port_mapping.get("published", 0)),
                "container_port": int(port_mapping.get("target", 0)),
                "host_ip": port_mapping.get("host_ip"),
            }
        
        if not isinstance(port_mapping, str):
            return None
        
        # Parse short form: [ip:]host:container[/protocol]
        parts = port_mapping.split(":")
        
        try:
            if len(parts) == 2:
                # host:container
                host_port = int(parts[0])
                container_port = int(parts[1].split("/")[0])
                return {"host_port": host_port, "container_port": container_port, "host_ip": None}
            elif len(parts) == 3:
                # ip:host:container
                host_ip = parts[0]
                host_port = int(parts[1])
                container_port = int(parts[2].split("/")[0])
                return {"host_port": host_port, "container_port": container_port, "host_ip": host_ip}
        except (ValueError, IndexError):
            pass
        
        return None

    def service_names(self) -> list[str]:
        """List all service names."""
        return list(self.services.keys())
