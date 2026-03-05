
import sys
import subprocess
from pathlib import Path
import click
from taskfile.parser import load_taskfile, TaskfileNotFoundError, TaskfileParseError
from taskfile.cli.main import main, console

def _run(cmd: str, label: str, dry_run: bool):
    if label:
        console.print(f"[bold]{label}[/]")
    console.print(f"  [dim]→ {cmd}[/]")
    if not dry_run:
        result = subprocess.run(cmd, shell=True)
        if result.returncode != 0:
            console.print(f"[red]✗ Command failed (exit {result.returncode})[/]")
            sys.exit(1)
    else:
        console.print("  [dim](dry run)[/]")

def _ssh(cmd: str, label: str, env: any, env_name: str, dry_run: bool):
    if not env.ssh_target:
        console.print(f"[red]No SSH host for env '{env_name}'[/]")
        sys.exit(1)
    escaped = cmd.replace("'", "'\''")
    full = f"ssh {env.ssh_opts} {env.ssh_target} '{escaped}'"
    _run(full, label, dry_run)

def _deploy_local_compose(env, env_file_path, dry_run):
    env_flag = f"--env-file {env_file_path}" if env_file_path else ""
    _run(f"{env.compose_command} {env_flag} up -d --build", "Starting local services...", dry_run)
    console.print("\n[green]✅ Local deploy complete[/]")

def _deploy_remote_compose(env, env_name, env_file_path, config, dry_run):
    env_flag = f"--env-file {env_file_path}" if env_file_path else ""
    _ssh(f"cd /opt/{config.name or 'app'} && {env.compose_command} {env_flag} pull",
         "Pulling images on remote...", env, env_name, dry_run)
    _ssh(f"cd /opt/{config.name or 'app'} && {env.compose_command} {env_flag} up -d",
         "Starting services on remote...", env, env_name, dry_run)
    console.print(f"\n[green]✅ Remote compose deploy complete ({env_name})[/]")

def _deploy_quadlet(env, env_name, env_file_path, compose_path, var_overrides, dry_run):
    from taskfile.compose import ComposeFile
    from taskfile.quadlet import compose_to_quadlet

    # Step 1: Generate Quadlet
    console.print("[bold]Step 1/4: Generating Quadlet files[/]")
    compose = ComposeFile(
        compose_path=compose_path,
        env_file=env_file_path,
        extra_vars=var_overrides,
    )
    if not dry_run:
        generated = compose_to_quadlet(
            compose=compose,
            output_dir=env.quadlet_dir,
            network_name="proxy",
            auto_update=True,
        )
    else:
        console.print(f"  [dim](dry run — would generate from {compose_path})[/]")
        generated = []

    # Step 2: Upload to server
    console.print(f"\n[bold]Step 2/4: Uploading to {env.ssh_target}[/]")
    quadlet_dir = Path(env.quadlet_dir)
    if not dry_run and quadlet_dir.is_dir():
        files = list(quadlet_dir.glob("*.container")) + \
                list(quadlet_dir.glob("*.network")) + \
                list(quadlet_dir.glob("*.volume"))
        file_list = " ".join(str(f) for f in files)
        _ssh(f"mkdir -p {env.quadlet_remote_dir}", "", env, env_name, dry_run)
        _run(f"scp {file_list} {env.ssh_target}:{env.quadlet_remote_dir}/", "", dry_run)
    else:
        console.print(f"  [dim](dry run — would upload to {env.quadlet_remote_dir})[/]")

    # Step 3: Reload + pull
    console.print(f"\n[bold]Step 3/4: Pull images & reload systemd[/]")
    _ssh("systemctl --user daemon-reload", "", env, env_name, dry_run)
    for svc_name in compose.service_names() if not dry_run else ["(services)"]:
        svc = compose.get_service(svc_name) if not dry_run else {}
        image = svc.get("image", "") if svc else ""
        if image and not dry_run:
            _ssh(f"podman pull {image}", "", env, env_name, dry_run)

    # Step 4: Restart services
    console.print(f"\n[bold]Step 4/4: Restarting services[/]")
    for svc_name in compose.service_names() if not dry_run else ["(services)"]:
        _ssh(f"systemctl --user restart {svc_name}", "", env, env_name, dry_run)

    _ssh("podman image prune -f", "Cleaning up old images...", env, env_name, dry_run)
    console.print(f"\n[green]✅ Quadlet deploy complete ({env_name})[/]")

@main.command(name="deploy")
@click.option("--compose", "compose_override", default=None, help="Path to docker-compose.yml")
@click.pass_context
def deploy_cmd(ctx, compose_override):
    """Full deploy pipeline: build → push → generate Quadlet → upload → restart.

    Reads environment config from Taskfile.yml and performs the correct
    deploy strategy for the target environment:

    \b
      local   → docker compose up -d
      compose → SSH + docker compose pull/up on remote
      quadlet → generate .container files → scp → systemctl restart

    \b
    Examples:
        taskfile --env local deploy
        taskfile --env prod deploy
        taskfile --env prod deploy --var TAG=v1.2.3
        taskfile --env prod --dry-run deploy
    """
    opts = ctx.obj
    env_name = opts.get("env_name")
    dry_run = opts.get("dry_run", False)
    var_overrides = opts.get("var", {})
    compose_path_override = compose_override

    try:
        config = load_taskfile(opts.get("taskfile_path"))
        env_name = env_name or config.default_env

        if env_name not in config.environments:
            console.print(f"[red]Unknown environment: {env_name}[/]")
            sys.exit(1)

        env = config.environments[env_name]

        # Resolve variables
        variables = env.resolve_variables(config.variables)
        variables.update(var_overrides)

        compose_path = compose_path_override or env.compose_file
        env_file_path = env.env_file

        console.print(f"\n[bold]Deploying [cyan]{config.name or 'project'}[/] to [yellow]{env_name}[/][/]")
        console.print(f"  compose:  {compose_path}")
        if env_file_path:
            console.print(f"  env-file: {env_file_path}")
        console.print(f"  runtime:  {env.container_runtime}")
        console.print(f"  manager:  {env.service_manager}")
        console.print()


        if env.service_manager == "compose" and not env.ssh_host:
            _deploy_local_compose(env, env_file_path, dry_run)
            return
        if env.service_manager == "compose" and env.ssh_host:
            _deploy_remote_compose(env, env_name, env_file_path, config, dry_run)
            return
        if env.service_manager == "quadlet":
            _deploy_quadlet(env, env_name, env_file_path, compose_path, var_overrides, dry_run)
            return

        console.print(f"[red]Unknown service_manager: {env.service_manager}[/]")
        sys.exit(1)

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Deploy failed:[/] {e}")
        if opts.get("verbose"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


