"""CLI commands for Docker service management (stop containers, compose down, port helpers)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import click

from taskfile.cli.main import console, main


@dataclass(frozen=True)
class DockerContainer:
    container_id: str
    name: str
    ports: str


_PORT_TOKEN_RE = re.compile(r"(?P<host>(?:\d{1,3}\.){3}\d{1,3}|\[::\]|\*|0\.0\.0\.0|::):(?P<port>\d+)->")


def _docker_ps() -> list[DockerContainer]:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Ports}}"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or "docker ps failed")

    containers: list[DockerContainer] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        containers.append(DockerContainer(container_id=parts[0], name=parts[1], ports=parts[2]))
    return containers


def _container_publishes_port(container: DockerContainer, port: int) -> bool:
    # Typical ports string examples:
    #   0.0.0.0:8002->8002/tcp, [::]:8002->8002/tcp
    #   8000/tcp
    for m in _PORT_TOKEN_RE.finditer(container.ports or ""):
        try:
            if int(m.group("port")) == int(port):
                return True
        except ValueError:
            continue
    return False


def _containers_using_port(port: int) -> list[DockerContainer]:
    return [c for c in _docker_ps() if _container_publishes_port(c, port)]


def _docker_stop(container_ids: list[str]) -> None:
    if not container_ids:
        return
    result = subprocess.run(["docker", "stop", *container_ids], text=True, capture_output=True)
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or "docker stop failed")


@main.group(name="docker")
def docker_group():
    """🐳 Docker helpers - inspect and stop containers, compose down, port management."""


@docker_group.command(name="ps")
def docker_ps_cmd():
    """Show running docker containers (id, name, ports)."""
    try:
        containers = _docker_ps()
    except click.ClickException as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)

    if not containers:
        console.print("[dim]No running containers[/]")
        return

    for c in containers:
        console.print(f"{c.container_id}\t{c.name}\t{c.ports}")


@docker_group.command(name="stop-port")
@click.argument("port", type=int)
@click.option("--yes", "assume_yes", is_flag=True, help="Do not ask for confirmation")
def docker_stop_port_cmd(port: int, assume_yes: bool):
    """Stop all containers that publish the given host TCP port."""
    containers = _containers_using_port(port)
    if not containers:
        console.print(f"[green]✓[/] No running containers publish port {port}")
        return

    console.print(f"[yellow]Port {port} is published by:[/]")
    for c in containers:
        console.print(f"  {c.container_id}  {c.name}  {c.ports}")

    if not assume_yes:
        if not click.confirm(f"Stop {len(containers)} container(s)?", default=False):
            console.print("[dim]Cancelled[/]")
            return

    _docker_stop([c.container_id for c in containers])
    console.print(f"[green]✓[/] Stopped {len(containers)} container(s)")


@docker_group.command(name="compose-down")
@click.option("--path", "compose_dir", type=click.Path(path_type=Path), default=Path("."))
@click.option("--yes", "assume_yes", is_flag=True, help="Do not ask for confirmation")
def docker_compose_down_cmd(compose_dir: Path, assume_yes: bool):
    """Run `docker compose down` in the given directory (default: current)."""
    compose_dir = compose_dir.resolve()
    if not (compose_dir / "docker-compose.yml").exists() and not (compose_dir / "compose.yml").exists():
        console.print(f"[yellow]⚠[/] No compose file found in {compose_dir}")

    if not assume_yes:
        if not click.confirm(f"Run 'docker compose down' in {compose_dir}?", default=False):
            console.print("[dim]Cancelled[/]")
            return

    result = subprocess.run(
        ["docker", "compose", "down"],
        cwd=str(compose_dir),
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
