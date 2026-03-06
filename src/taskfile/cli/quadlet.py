"""## Quadlet management commands for taskfile

Generate and manage Podman Quadlet files from docker-compose.yml.

### Overview

Podman Quadlet allows running containers as systemd services without root:
- **Generate** - Convert docker-compose.yml to Quadlet format
- **Install** - Install Quadlet files to systemd user directory
- **Manage** - Start/stop services via systemd

### Quadlet vs Docker Compose

| Feature | Quadlet | Docker Compose |
|---------|---------|----------------|
| Rootless | ✅ Yes | ⚠️ Partial |
| systemd | ✅ Native | ❌ Requires wrapper |
| Auto-start | ✅ Built-in | ❌ Manual |
| Resources | ✅ cgroup v2 | ⚠️ Limited |

### File Locations

```
~/.config/containers/systemd/
├── myapp.container      # Container definition
├── myapp.network        # Network definition
└── myapp.volume         # Volume definition
```

### Usage

```bash
# Generate Quadlet files from docker-compose.yml
taskfile quadlet generate

# Install and start services
taskfile quadlet install

# Check service status
taskfile quadlet status
```

### Why clickmd?

Uses `clickmd` for consistent CLI experience and markdown rendering of Quadlet info.

### Dependencies

- `clickmd` - CLI framework
- `rich` - Rich console output for service status
"""

from __future__ import annotations
import sys
from pathlib import Path
import clickmd as click
from taskfile.parser import load_taskfile, TaskfileNotFoundError, TaskfileParseError
from taskfile.cli.main import main, console

@main.group()
def quadlet():
    """**Generate and manage Podman Quadlet files** from docker-compose.yml.

## Overview

Convert Docker Compose services to systemd-compatible Quadlet unit files
for Podman rootless containers.

## Commands

| Command | Description |
|---------|-------------|
| `generate` | Create .container files from docker-compose.yml |
| `upload` | Upload Quadlet files to remote server via SSH |

## Examples

```bash
# Generate Quadlet files
taskfile quadlet generate

# Generate with specific env file
taskfile quadlet generate --env-file .env.prod

# Upload to remote
taskfile --env prod quadlet upload
```
"""


@quadlet.command(name="generate")
@click.option(
    "-c", "--compose", "compose_path",
    default="docker-compose.yml", help="Path to docker-compose.yml"
)
@click.option(
    "--env-file", "env_file",
    default=None, help="Path to .env file (.env.prod, .env.staging, etc.)"
)
@click.option(
    "-o", "--output", "output_dir",
    default="deploy/quadlet", help="Output directory for .container files"
)
@click.option(
    "--network", default="proxy", help="Network name for containers"
)
@click.option(
    "--no-auto-update", is_flag=True, help="Disable AutoUpdate=registry"
)
@click.option(
    "--service", "services", multiple=True, help="Only generate for specific service(s)"
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be generated without writing files"
)
@click.pass_context
def quadlet_generate(ctx, compose_path, env_file, output_dir, network, no_auto_update, services, dry_run):
    """**Generate Quadlet .container files** from docker-compose.yml.

## Options

| Option | Description |
|--------|-------------|
| `-c, --compose` | Path to docker-compose.yml |
| `--env-file` | Environment file for variable resolution |
| `-o, --output` | Output directory (default: deploy/quadlet) |
| `--network` | Network name for containers |
| `--no-auto-update` | Disable AutoUpdate=registry |
| `--service` | Generate only for specific service(s) |
| `--dry-run` | Preview without writing files |

## Examples

```bash
# Generate with default options
taskfile quadlet generate

# Use production environment variables
taskfile quadlet generate --env-file .env.prod

# Generate for specific services only
taskfile quadlet generate --service web --service api

# Preview without writing
taskfile quadlet generate --dry-run
```
"""
    from taskfile.compose import ComposeFile, load_env_file
    from taskfile.quadlet import compose_to_quadlet

    opts = ctx.obj or {}
    var_overrides = opts.get("var", {})

    try:
        console.print(f"[bold]Generating Quadlet from[/] {compose_path}")
        if env_file:
            console.print(f"  [dim]env-file:[/] {env_file}")

        compose = ComposeFile(
            compose_path=compose_path,
            env_file=env_file,
            extra_vars=var_overrides,
        )

        # Load env vars for port resolution
        env_vars = {}
        if env_file:
            env_vars = load_env_file(env_file)
        env_vars.update(var_overrides)

        svc_filter = list(services) if services else None

        if dry_run:
            console.print(f"\n[dim]Would generate files in {output_dir}/:[/]")
            # Preview mode: show what would be generated
            from taskfile.quadlet import generate_container_unit
            for svc_name, svc_data in compose.services.items():
                if svc_filter and svc_name not in svc_filter:
                    continue
                content = generate_container_unit(
                    service_name=svc_name,
                    service=svc_data,
                    network_name=network,
                    auto_update=not no_auto_update,
                    env=env_vars,
                )
                console.print(f"\n[cyan]{svc_name}.container:[/]")
                for line in content.strip().split("\n")[:15]:  # Show first 15 lines
                    console.print(f"  [dim]{line}[/]")
                if len(content.strip().split("\n")) > 15:
                    console.print("  [dim]...[/]")
            console.print(f"\n[dim](dry run — no files written)[/]")
        else:
            generated = compose_to_quadlet(
                compose=compose,
                output_dir=output_dir,
                network_name=network,
                auto_update=not no_auto_update,
                services_filter=svc_filter,
                env=env_vars,
            )
            console.print(f"\n[green]✓ Generated {len(generated)} files in {output_dir}/[/]")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


import subprocess
from taskfile.models import Environment, TaskfileConfig

def _get_upload_env(config: TaskfileConfig, env_name: str | None) -> tuple[str, Environment]:
    """Resolve and validate the target remote environment."""
    if not env_name:
        for name, env in config.environments.items():
            if env.ssh_host:
                return name, env
        console.print("[red]Error: No remote environment found. Use --env <name>[/]")
        sys.exit(1)

    if env_name not in config.environments:
        console.print(f"[red]Error: Environment '{env_name}' not found in Taskfile.yml[/]")
        sys.exit(1)

    env = config.environments[env_name]
    if not env.ssh_target:
        console.print(f"[red]Error: Environment '{env_name}' has no ssh_host[/]")
        sys.exit(1)

    return env_name, env

def _get_upload_files(quadlet_dir: str) -> list[Path]:
    """Find valid Quadlet files in the local directory."""
    quadlet_path = Path(quadlet_dir)
    if not quadlet_path.is_dir():
        console.print(f"[red]Error: Directory not found: {quadlet_dir}[/]")
        console.print("[dim]  Run 'taskfile quadlet generate' first[/]")
        sys.exit(1)

    files = list(quadlet_path.glob("*.container")) + \
            list(quadlet_path.glob("*.network")) + \
            list(quadlet_path.glob("*.volume"))

    if not files:
        console.print(f"[yellow]No Quadlet files found in {quadlet_dir}[/]")
        sys.exit(1)
        
    return files

def _run_upload_commands(env: Environment, files: list[Path], dry_run: bool) -> None:
    """Execute SSH commands to upload and reload Quadlet units."""
    remote_dir = env.quadlet_remote_dir
    target = env.ssh_target
    ssh_opts = env.ssh_opts

    console.print(f"[bold]Uploading {len(files)} Quadlet files to {target}:{remote_dir}[/]")

    # Ensure remote dir exists
    mkdir_cmd = f"ssh {ssh_opts} {target} 'mkdir -p {remote_dir}'"
    console.print(f"  [dim]→ {mkdir_cmd}[/]")
    if not dry_run:
        subprocess.run(mkdir_cmd, shell=True, check=True)

    # Upload files
    file_list = " ".join(str(f) for f in files)
    scp_cmd = f"scp {' '.join(str(f) for f in files)} {target}:{remote_dir}/"
    console.print(f"  [dim]→ {scp_cmd}[/]")
    if not dry_run:
        subprocess.run(scp_cmd, shell=True, check=True)

    # Reload systemd
    reload_cmd = f"ssh {ssh_opts} {target} 'systemctl --user daemon-reload'"
    console.print(f"  [dim]→ {reload_cmd}[/]")
    if not dry_run:
        subprocess.run(reload_cmd, shell=True, check=True)

@quadlet.command(name="upload")
@click.option(
    "-o", "--output", "quadlet_dir",
    default="deploy/quadlet", help="Local directory with .container files"
)
@click.pass_context
def quadlet_upload(ctx, quadlet_dir):
    """Upload generated Quadlet files to remote server via SSH.

    Uses environment settings from Taskfile.yml for SSH connection
    and remote quadlet directory.

    
    Examples:
        taskfile --env prod quadlet upload
        taskfile --env prod quadlet upload -o deploy/quadlet
    """
    opts = ctx.obj or {}
    env_name = opts.get("env_name")
    dry_run = opts.get("dry_run", False)

    try:
        config = load_taskfile(opts.get("taskfile_path"))
        env_name, env = _get_upload_env(config, env_name)
        files = _get_upload_files(quadlet_dir)
        _run_upload_commands(env, files, dry_run)

        if dry_run:
            console.print("[dim](dry run — nothing executed)[/]")
        else:
            console.print(f"[green]✓ Uploaded and reloaded systemd on {env_name}[/]")

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Upload failed:[/] {e}")
        sys.exit(1)

