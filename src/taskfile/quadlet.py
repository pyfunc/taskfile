"""Generate Podman Quadlet .container files from docker-compose.yml.

Pure Python implementation — does NOT require podlet binary.
Reads a ComposeFile and generates systemd-compatible Quadlet unit files
for each service.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from rich.console import Console

from taskfile.compose import ComposeFile

console = Console()


class ServiceConfig(TypedDict):
    """Type definition for a docker-compose service configuration."""

    image: NotRequired[str]
    container_name: NotRequired[str]
    environment: NotRequired[dict[str, Any] | list[str]]
    env_file: NotRequired[str | list[str]]
    ports: NotRequired[list[str]]
    volumes: NotRequired[list[str | dict[str, Any]]]
    networks: NotRequired[list[str] | dict[str, Any]]
    labels: NotRequired[dict[str, str] | list[str]]
    depends_on: NotRequired[list[str] | dict[str, Any]]
    restart: NotRequired[str]
    deploy: NotRequired[dict[str, Any]]


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


def _build_unit_section(service_name: str, service: ServiceConfig) -> list[str]:
    lines = ["[Unit]", f"Description={service_name} container"]
    depends = service.get("depends_on", [])
    if isinstance(depends, dict):
        depends = list(depends.keys())
    for dep in depends:
        lines.extend([f"After={dep}.service", f"Requires={dep}.service"])
    return lines


def _build_container_env(service: ServiceConfig, lines: list[str]) -> None:
    env = service.get("environment", {})
    if isinstance(env, list):
        for item in env:
            lines.append(f"Environment={item}")
    elif isinstance(env, dict):
        for key, value in env.items():
            lines.append(f"Environment={key}={value}")

    env_files = service.get("env_file", [])
    if isinstance(env_files, str):
        env_files = [env_files]
    for ef in env_files:
        lines.append(f"EnvironmentFile={ef}")


def _build_container_ports(
    service: ServiceConfig, lines: list[str], env: dict[str, str] | None = None
) -> None:
    """Build PublishPort lines, resolving env vars in port mappings.

    Args:
        service: Service configuration from compose
        lines: Output lines list to append to
        env: Optional environment variables dict for resolving ${VAR:-default}
    """
    env = env or {}
    for port in service.get("ports", []):
        host_port, container_port = _parse_port(str(port))
        # Resolve env vars in host port (e.g., ${PORT_WEB:-8000})
        host_port = _resolve_env_in_port(host_port, env)
        lines.append(f"PublishPort={host_port}:{container_port}")


def _resolve_env_in_port(port_str: str, env: dict[str, str]) -> str:
    """Resolve ${VAR} or ${VAR:-default} syntax in port string."""
    import re

    def replace_var(match: re.Match) -> str:
        var_name = match.group("var")
        default = match.group("default")
        value = env.get(var_name)
        if value:
            return value
        if default is not None:
            return default
        return match.group(0)  # Keep original if no value and no default

    # Match ${VAR} or ${VAR:-default}
    pattern = r"\$\{(?P<var>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}"
    return re.sub(pattern, replace_var, port_str)


def _build_container_volumes(service: ServiceConfig, lines: list[str]) -> None:
    for vol in service.get("volumes", []):
        if isinstance(vol, str):
            src = vol.split(":")[0]
            if not src.startswith("/") and not src.startswith(".") and not src.startswith("$"):
                vol_name = src
                mount_parts = vol.split(":")
                if len(mount_parts) >= 2:
                    lines.append(f"Volume={vol_name}.volume:{mount_parts[1]}")
                else:
                    lines.append(f"Volume={vol}")
            else:
                lines.append(f"Volume={vol}")
        elif isinstance(vol, dict):
            src = vol.get("source", "")
            tgt = vol.get("target", "")
            ro = ":ro" if vol.get("read_only") else ""
            lines.append(f"Volume={src}:{tgt}{ro}")


def _build_container_networks(service: ServiceConfig, network_name: str, lines: list[str]) -> None:
    networks = service.get("networks", [])
    if isinstance(networks, list):
        if networks:
            for net in networks:
                lines.append(f"Network={net}.network")
        else:
            lines.append(f"Network={network_name}.network")
    elif isinstance(networks, dict):
        if networks:
            for net in networks.keys():
                lines.append(f"Network={net}.network")
        else:
            lines.append(f"Network={network_name}.network")
    else:
        lines.append(f"Network={network_name}.network")


def _build_container_labels(service: ServiceConfig, lines: list[str]) -> None:
    labels = service.get("labels", {})
    if isinstance(labels, list):
        for item in labels:
            lines.append(f"Label={item}")
    elif isinstance(labels, dict):
        for key, value in labels.items():
            lines.append(f"Label={key}={value}")


def _build_container_podman_args(service: ServiceConfig, lines: list[str]) -> None:
    deploy = service.get("deploy", {})
    memory = _parse_memory_limit(deploy)
    podman_args = []
    if memory:
        podman_args.append(f"--memory={memory}")
    cpus = _parse_cpus_limit(deploy)
    if cpus:
        podman_args.append(f"--cpus={cpus}")
    if podman_args:
        lines.append(f"PodmanArgs={' '.join(podman_args)}")


def _build_container_section(
    service_name: str,
    service: ServiceConfig,
    network_name: str,
    auto_update: bool,
    env: dict[str, str] | None = None,
) -> list[str]:
    lines = ["\\n[Container]"]
    image = service.get("image", "")
    if image:
        lines.append(f"Image={image}")
    lines.append(f"ContainerName={service_name}")
    if auto_update and image:
        lines.append("AutoUpdate=registry")

    _build_container_env(service, lines)
    _build_container_ports(service, lines, env)
    _build_container_volumes(service, lines)
    _build_container_networks(service, network_name, lines)
    _build_container_labels(service, lines)
    _build_container_podman_args(service, lines)

    return lines


def _build_service_section(service: ServiceConfig) -> list[str]:
    lines = ["\\n[Service]"]
    restart = service.get("restart", "always")
    if restart == "unless-stopped":
        restart = "always"
    lines.extend([f"Restart={restart}", "TimeoutStartSec=300"])
    return lines


def _build_install_section() -> list[str]:
    return ["\\n[Install]", "WantedBy=multi-user.target default.target"]


def generate_container_unit(
    service_name: str,
    service: ServiceConfig,
    network_name: str = "proxy",
    auto_update: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    """Generate a .container Quadlet unit file content from a compose service.

    Args:
        service_name: Name of the service (becomes ContainerName)
        service: Resolved service dict from docker-compose.yml
        network_name: Podman network to attach to
        auto_update: Enable AutoUpdate=registry
        env: Environment variables for resolving ${VAR:-default} in ports

    Returns:
        String content of the .container file
    """
    lines_unit = _build_unit_section(service_name, service)
    lines_container = _build_container_section(
        service_name, service, network_name, auto_update, env
    )
    lines_service = _build_service_section(service)
    lines_install = _build_install_section()

    return "\\n".join(lines_unit + lines_container + lines_service + lines_install) + "\\n"


def _generate_quadlet_unit(section: str, name: str, extra_props: str = "") -> str:
    """Generate a Quadlet unit file with given section and properties."""
    name_field = f"{section}Name"
    props = f"{name_field}={name}\n"
    if extra_props:
        props += extra_props
    return f"""\
[{section}]
{props}"""


def generate_network_unit(network_name: str) -> str:
    """Generate a .network Quadlet unit file."""
    return _generate_quadlet_unit("Network", network_name, "Driver=bridge\n")


def generate_volume_unit(volume_name: str) -> str:
    """Generate a .volume Quadlet unit file."""
    return _generate_quadlet_unit("Volume", volume_name)


def _collect_named_volumes(service: ServiceConfig) -> set[str]:
    """Extract named volume references from a service definition."""
    named = set()
    for vol in service.get("volumes", []):
        if isinstance(vol, str):
            src = vol.split(":")[0]
            if not src.startswith("/") and not src.startswith(".") and not src.startswith("$"):
                named.add(src)
    return named


def _generate_network_file(outdir: Path, network_name: str) -> Path:
    """Write the .network Quadlet file and return its path."""
    net_path = outdir / f"{network_name}.network"
    net_path.write_text(generate_network_unit(network_name))
    console.print(f"  [green]✓[/] {net_path.name}")
    return net_path


def _generate_container_files(
    outdir: Path,
    compose: ComposeFile,
    network_name: str,
    auto_update: bool,
    services_filter: list[str] | None,
    env: dict[str, str] | None = None,
) -> tuple[list[Path], set[str]]:
    """Write .container files for each service. Returns (paths, named_volumes)."""
    generated: list[Path] = []
    named_volumes: set[str] = set()

    for svc_name, svc_data in compose.services.items():
        if services_filter and svc_name not in services_filter:
            continue

        named_volumes |= _collect_named_volumes(svc_data)

        content = generate_container_unit(
            service_name=svc_name,
            service=svc_data,
            network_name=network_name,
            auto_update=auto_update,
            env=env,
        )
        filepath = outdir / f"{svc_name}.container"
        filepath.write_text(content)
        generated.append(filepath)
        console.print(f"  [green]✓[/] {filepath.name}")

    return generated, named_volumes


def _generate_volume_files(outdir: Path, named_volumes: set[str]) -> list[Path]:
    """Write .volume Quadlet files for named volumes."""
    generated: list[Path] = []
    for vol_name in sorted(named_volumes):
        vol_path = outdir / f"{vol_name}.volume"
        vol_path.write_text(generate_volume_unit(vol_name))
        generated.append(vol_path)
        console.print(f"  [green]✓[/] {vol_path.name}")
    return generated


_RESOLV_CONF_CONTENT = """\
# Auto-generated by taskfile quadlet generate
# Fixes Podman bridge network DNS isolation — containers need
# external DNS to reach registries, ACME servers, etc.
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver 8.8.4.4
"""


def generate_resolv_conf(output_dir: str | Path) -> Path:
    """Generate a resolv.conf with public DNS servers for Podman containers.

    Podman's default bridge network uses 10.88.0.1 as DNS resolver,
    which often cannot resolve external domains. This file should be
    mounted as /etc/resolv.conf:ro in .container files.

    Returns:
        Path to generated resolv.conf
    """
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    resolv_path = outdir / "resolv.conf"
    resolv_path.write_text(_RESOLV_CONF_CONTENT)
    console.print(f"  [green]✓[/] {resolv_path.name} (Podman DNS fix)")
    return resolv_path


def compose_to_quadlet(
    compose: ComposeFile,
    output_dir: str | Path,
    network_name: str = "proxy",
    auto_update: bool = True,
    services_filter: list[str] | None = None,
    env: dict[str, str] | None = None,
    dns_fix: bool = True,
) -> list[Path]:
    """Convert all services in a ComposeFile to Quadlet unit files.

    Args:
        compose: Parsed ComposeFile
        output_dir: Directory to write .container files
        network_name: Default network name
        auto_update: Enable AutoUpdate on all containers
        services_filter: Only generate for these services (None = all)
        env: Environment variables for resolving ${VAR:-default} in ports
        dns_fix: Generate resolv.conf and add Volume mount for Podman DNS fix

    Returns:
        List of paths to generated files
    """
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    generated.append(_generate_network_file(outdir, network_name))
    container_paths, named_volumes = _generate_container_files(
        outdir,
        compose,
        network_name,
        auto_update,
        services_filter,
        env,
    )
    generated.extend(container_paths)
    generated.extend(_generate_volume_files(outdir, named_volumes))

    # Auto-generate resolv.conf for Podman DNS fix
    if dns_fix:
        resolv_path = generate_resolv_conf(outdir)
        generated.append(resolv_path)
        # Inject Volume mount into generated .container files
        for cpath in container_paths:
            _inject_resolv_volume(cpath)

    return generated


def _inject_resolv_volume(container_path: Path) -> None:
    """Add Volume=./resolv.conf:/etc/resolv.conf:ro to a .container file.

    Only adds the line if it's not already present.
    """
    content = container_path.read_text()
    volume_line = "Volume=./resolv.conf:/etc/resolv.conf:ro"
    if volume_line in content:
        return
    # Insert after the last Volume= line, or after [Container] section
    lines = content.split("\\n")
    insert_idx = None
    for i, line in enumerate(lines):
        if line.startswith("Volume="):
            insert_idx = i + 1
        elif line.startswith("[Service]") and insert_idx is None:
            insert_idx = i
    if insert_idx is not None:
        lines.insert(insert_idx, volume_line)
        container_path.write_text("\\n".join(lines))
