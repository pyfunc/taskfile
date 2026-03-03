"""Generate Podman Quadlet .container files from docker-compose.yml.

Pure Python implementation — does NOT require podlet binary.
Reads a ComposeFile and generates systemd-compatible Quadlet unit files
for each service.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rich.console import Console

from taskfile.compose import ComposeFile

console = Console()


def _parse_port(port_str: str) -> tuple[str, str]:
    """Parse '8080:80' → ('8080', '80') or '80' → ('80', '80')."""
    parts = str(port_str).split(":")
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], parts[0]


def _parse_memory_limit(deploy: dict) -> str | None:
    """Extract memory limit from deploy.resources.limits.memory."""
    try:
        return deploy["resources"]["limits"]["memory"]
    except (KeyError, TypeError):
        return None


def _parse_cpus_limit(deploy: dict) -> str | None:
    """Extract CPU limit from deploy.resources.limits.cpus."""
    try:
        return str(deploy["resources"]["limits"]["cpus"])
    except (KeyError, TypeError):
        return None


def generate_container_unit(
    service_name: str,
    service: dict,
    network_name: str = "proxy",
    auto_update: bool = True,
) -> str:
    """Generate a .container Quadlet unit file content from a compose service.

    Args:
        service_name: Name of the service (becomes ContainerName)
        service: Resolved service dict from docker-compose.yml
        network_name: Podman network to attach to
        auto_update: Enable AutoUpdate=registry

    Returns:
        String content of the .container file
    """
    lines_unit = ["[Unit]"]
    lines_unit.append(f"Description={service_name} container")

    # Dependencies — if service has depends_on
    depends = service.get("depends_on", [])
    if isinstance(depends, dict):
        depends = list(depends.keys())
    for dep in depends:
        lines_unit.append(f"After={dep}.service")
        lines_unit.append(f"Requires={dep}.service")

    # [Container] section
    lines_container = ["\n[Container]"]

    # Image
    image = service.get("image", "")
    if image:
        lines_container.append(f"Image={image}")

    lines_container.append(f"ContainerName={service_name}")

    # Auto-update
    if auto_update and image:
        lines_container.append("AutoUpdate=registry")

    # Environment variables
    env = service.get("environment", {})
    if isinstance(env, list):
        for item in env:
            lines_container.append(f"Environment={item}")
    elif isinstance(env, dict):
        for key, value in env.items():
            lines_container.append(f"Environment={key}={value}")

    # Env files
    env_files = service.get("env_file", [])
    if isinstance(env_files, str):
        env_files = [env_files]
    for ef in env_files:
        lines_container.append(f"EnvironmentFile={ef}")

    # Ports
    ports = service.get("ports", [])
    for port in ports:
        host_port, container_port = _parse_port(str(port))
        lines_container.append(f"PublishPort={host_port}:{container_port}")

    # Volumes
    volumes = service.get("volumes", [])
    for vol in volumes:
        if isinstance(vol, str):
            # Check if it's a named volume (no / or . prefix)
            src = vol.split(":")[0]
            if not src.startswith("/") and not src.startswith(".") and not src.startswith("$"):
                # Named volume → use Quadlet .volume reference
                vol_name = src
                mount_parts = vol.split(":")
                if len(mount_parts) >= 2:
                    lines_container.append(f"Volume={vol_name}.volume:{mount_parts[1]}")
                else:
                    lines_container.append(f"Volume={vol}")
            else:
                lines_container.append(f"Volume={vol}")
        elif isinstance(vol, dict):
            src = vol.get("source", "")
            tgt = vol.get("target", "")
            ro = ":ro" if vol.get("read_only") else ""
            lines_container.append(f"Volume={src}:{tgt}{ro}")

    # Network
    networks = service.get("networks", [])
    if isinstance(networks, list):
        for net in networks:
            lines_container.append(f"Network={net}.network")
    elif isinstance(networks, dict):
        for net in networks.keys():
            lines_container.append(f"Network={net}.network")
    else:
        lines_container.append(f"Network={network_name}.network")

    # Labels (including Traefik)
    labels = service.get("labels", {})
    if isinstance(labels, list):
        for item in labels:
            lines_container.append(f"Label={item}")
    elif isinstance(labels, dict):
        for key, value in labels.items():
            lines_container.append(f"Label={key}={value}")

    # Resource limits
    deploy = service.get("deploy", {})
    memory = _parse_memory_limit(deploy)
    # Note: Quadlet doesn't have native memory limit syntax —
    # we use PodmanArgs for cgroup limits
    podman_args = []
    if memory:
        podman_args.append(f"--memory={memory}")
    cpus = _parse_cpus_limit(deploy)
    if cpus:
        podman_args.append(f"--cpus={cpus}")
    if podman_args:
        lines_container.append(f"PodmanArgs={' '.join(podman_args)}")

    # [Service] section
    lines_service = ["\n[Service]"]
    restart = service.get("restart", "always")
    if restart == "unless-stopped":
        restart = "always"
    lines_service.append(f"Restart={restart}")
    lines_service.append("TimeoutStartSec=300")

    # [Install] section
    lines_install = ["\n[Install]"]
    lines_install.append("WantedBy=multi-user.target default.target")

    return "\n".join(lines_unit + lines_container + lines_service + lines_install) + "\n"


def generate_network_unit(network_name: str) -> str:
    """Generate a .network Quadlet unit file."""
    return f"""\
[Network]
NetworkName={network_name}
Driver=bridge
"""


def generate_volume_unit(volume_name: str) -> str:
    """Generate a .volume Quadlet unit file."""
    return f"""\
[Volume]
VolumeName={volume_name}
"""


def compose_to_quadlet(
    compose: ComposeFile,
    output_dir: str | Path,
    network_name: str = "proxy",
    auto_update: bool = True,
    services_filter: list[str] | None = None,
) -> list[Path]:
    """Convert all services in a ComposeFile to Quadlet unit files.

    Args:
        compose: Parsed ComposeFile
        output_dir: Directory to write .container files
        network_name: Default network name
        auto_update: Enable AutoUpdate on all containers
        services_filter: Only generate for these services (None = all)

    Returns:
        List of paths to generated files
    """
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    # Generate network file
    net_path = outdir / f"{network_name}.network"
    net_path.write_text(generate_network_unit(network_name))
    generated.append(net_path)
    console.print(f"  [green]✓[/] {net_path.name}")

    # Collect named volumes
    named_volumes: set[str] = set()

    # Generate container files
    for svc_name, svc_data in compose.services.items():
        if services_filter and svc_name not in services_filter:
            continue

        # Track named volumes
        for vol in svc_data.get("volumes", []):
            if isinstance(vol, str):
                src = vol.split(":")[0]
                if not src.startswith("/") and not src.startswith(".") and not src.startswith("$"):
                    named_volumes.add(src)

        content = generate_container_unit(
            service_name=svc_name,
            service=svc_data,
            network_name=network_name,
            auto_update=auto_update,
        )
        filepath = outdir / f"{svc_name}.container"
        filepath.write_text(content)
        generated.append(filepath)
        console.print(f"  [green]✓[/] {filepath.name}")

    # Generate volume files
    for vol_name in sorted(named_volumes):
        vol_path = outdir / f"{vol_name}.volume"
        vol_path.write_text(generate_volume_unit(vol_name))
        generated.append(vol_path)
        console.print(f"  [green]✓[/] {vol_path.name}")

    return generated
