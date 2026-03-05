from __future__ import annotations
import sys
from pathlib import Path
import click
from taskfile.parser import load_taskfile, TaskfileNotFoundError, TaskfileParseError
from taskfile.cli.main import main, console

@main.group()
def quadlet():
    """Generate and manage Podman Quadlet files from docker-compose.yml."""
    pass


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
@click.pass_context
def quadlet_generate(ctx, compose_path, env_file, output_dir, network, no_auto_update, services):
    """Generate Quadlet .container files from docker-compose.yml.

    \b
    Examples:
        taskfile quadlet generate
        taskfile quadlet generate --env-file .env.prod
        taskfile quadlet generate --env-file .env.prod -o deploy/quadlet
        taskfile quadlet generate --service app1 --service app2
    """
    from taskfile.compose import ComposeFile
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

        svc_filter = list(services) if services else None
        generated = compose_to_quadlet(
            compose=compose,
            output_dir=output_dir,
            network_name=network,
            auto_update=not no_auto_update,
            services_filter=svc_filter,
        )

        console.print(f"\n[green]✓ Generated {len(generated)} files in {output_dir}/[/]")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
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

