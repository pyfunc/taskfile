import sys
import subprocess
from pathlib import Path
from typing import Any

import clickmd as click
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
    escaped = cmd.replace("'", "'''")
    full = f"ssh {env.ssh_opts} {env.ssh_target} '{escaped}'"
    _run(full, label, dry_run)


def _deploy_local_compose(env, env_file_path, dry_run):
    env_flag = f"--env-file {env_file_path}" if env_file_path else ""
    _run(f"{env.compose_command} {env_flag} up -d --build", "Starting local services...", dry_run)
    console.print("\n[green]✅ Local deploy complete[/]")


def _deploy_ssh_push(env, env_name, config, dry_run):
    """Deploy via docker save | ssh podman load + podman run.

    Strategy for remote hosts without a registry:
    1. Build images locally (docker compose build)
    2. Transfer images via SSH pipe (docker save | ssh podman load)
    3. Run containers on remote (podman run -d --replace)
    """
    from taskfile.deploy_utils import (
        transfer_image_via_ssh,
        deploy_container_remote,
    )

    host = env.ssh_host
    user = env.ssh_user
    port = env.ssh_port
    runtime = env.container_runtime if env.container_runtime != "docker" else "podman"

    # Discover images from compose file
    compose_path = Path(env.compose_file)
    images = _discover_compose_images(compose_path, config)

    if not images:
        console.print("[yellow]⚠ No images found to push[/]")
        return

    # Step 1: Build
    console.print("\n[bold]Step 1: Build images locally[/]")
    _run(f"{env.compose_command} build", "", dry_run)

    # Step 2: Transfer
    console.print(f"\n[bold]Step 2: Transfer images → {host}[/]")
    if not dry_run:
        for img in images:
            transfer_image_via_ssh(img, host, user, port, runtime)
    else:
        for img in images:
            console.print(
                f"  [dim](dry run) docker save {img} | ssh {user}@{host} '{runtime} load'[/]"
            )

    # Step 3: Run containers
    console.print(f"\n[bold]Step 3: Start containers on {host}[/]")
    port_mappings = _discover_compose_ports(compose_path, config)
    if not dry_run:
        for img, port_map in zip(images, port_mappings):
            name = img.split(":")[0].rsplit("/", 1)[-1]  # extract short name
            full_image = f"docker.io/library/{img}" if "/" not in img else img
            console.print(
                f"  → {runtime} run -d --name {name} --replace -p {port_map} {full_image}"
            )
            deploy_container_remote(host, full_image, name, port_map, user, port, runtime)
    else:
        for img, port_map in zip(images, port_mappings):
            name = img.split(":")[0].rsplit("/", 1)[-1]
            console.print(f"  [dim](dry run) {runtime} run -d --name {name} -p {port_map} {img}[/]")

    console.print(f"\n[green]✅ SSH push deploy complete ({env_name})[/]")


def _discover_compose_images(compose_path: Path, config) -> list[str]:
    """Discover image names from docker-compose.yml services."""
    import yaml

    if not compose_path.exists():
        return []
    try:
        data = yaml.safe_load(compose_path.read_text()) or {}
    except Exception:
        return []
    services = data.get("services") or {}
    images = []
    project = config.name or compose_path.parent.name
    for svc_name, svc in services.items():
        if isinstance(svc, dict):
            img = svc.get("image", f"{project}-{svc_name}:latest")
            if ":" not in img:
                img = f"{img}:latest"
            images.append(img)
    return images


def _discover_compose_ports(compose_path: Path, config) -> list[str]:
    """Discover port mappings from docker-compose.yml services."""
    import yaml

    if not compose_path.exists():
        return []
    try:
        data = yaml.safe_load(compose_path.read_text()) or {}
    except Exception:
        return []
    services = data.get("services") or {}
    mappings = []
    for svc_name, svc in services.items():
        if isinstance(svc, dict):
            ports = svc.get("ports") or []
            if ports:
                mappings.append(str(ports[0]))
            else:
                mappings.append("8080:8080")
    return mappings


def _deploy_remote_compose(env, env_name, env_file_path, config, dry_run):
    env_flag = f"--env-file {env_file_path}" if env_file_path else ""
    _ssh(
        f"cd /opt/{config.name or 'app'} && {env.compose_command} {env_flag} pull",
        "Pulling images on remote...",
        env,
        env_name,
        dry_run,
    )
    _ssh(
        f"cd /opt/{config.name or 'app'} && {env.compose_command} {env_flag} up -d",
        "Starting services on remote...",
        env,
        env_name,
        dry_run,
    )
    console.print(f"\n[green]✅ Remote compose deploy complete ({env_name})[/]")


def _quadlet_step1_generate(env, compose_path, env_file_path, var_overrides, dry_run):
    """Step 1: Generate Quadlet files from compose."""
    from taskfile.compose import ComposeFile
    from taskfile.quadlet import compose_to_quadlet

    console.print("[bold]Step 1/4: Generating Quadlet files[/]")
    compose = ComposeFile(
        compose_path=compose_path,
        env_file=env_file_path,
        extra_vars=var_overrides,
    )
    if not dry_run:
        compose_to_quadlet(
            compose=compose,
            output_dir=env.quadlet_dir,
            network_name="proxy",
            auto_update=True,
        )
    else:
        console.print(f"  [dim](dry run — would generate from {compose_path})[/]")
    return compose


def _quadlet_step2_upload(env, env_name, dry_run):
    """Step 2: Upload Quadlet files to remote server."""
    console.print(f"\n[bold]Step 2/4: Uploading to {env.ssh_target}[/]")
    quadlet_dir = Path(env.quadlet_dir)
    if not dry_run and quadlet_dir.is_dir():
        files = (
            list(quadlet_dir.glob("*.container"))
            + list(quadlet_dir.glob("*.network"))
            + list(quadlet_dir.glob("*.volume"))
        )
        file_list = " ".join(str(f) for f in files)
        _ssh(f"mkdir -p {env.quadlet_remote_dir}", "", env, env_name, dry_run)
        _run(f"scp {file_list} {env.ssh_target}:{env.quadlet_remote_dir}/", "", dry_run)
    else:
        console.print(f"  [dim](dry run — would upload to {env.quadlet_remote_dir})[/]")


def _quadlet_step3_reload_and_pull(env, env_name, compose, dry_run):
    """Step 3: Reload systemd and pull container images."""
    console.print("\n[bold]Step 3/4: Pull images & reload systemd[/]")
    _ssh("systemctl --user daemon-reload", "", env, env_name, dry_run)
    if not dry_run:
        for svc_name in compose.service_names():
            svc = compose.get_service(svc_name)
            image = svc.get("image", "") if svc else ""
            if image:
                _ssh(f"podman pull {image}", "", env, env_name, dry_run)


def _quadlet_step4_restart_and_cleanup(env, env_name, compose, dry_run):
    """Step 4: Restart services and cleanup old images."""
    console.print("\n[bold]Step 4/4: Restarting services[/]")
    if not dry_run:
        for svc_name in compose.service_names():
            _ssh(f"systemctl --user restart {svc_name}", "", env, env_name, dry_run)
    _ssh("podman image prune -f", "Cleaning up old images...", env, env_name, dry_run)
    console.print(f"\n[green]✅ Quadlet deploy complete ({env_name})[/]")


def _deploy_quadlet(env, env_name, env_file_path, compose_path, var_overrides, dry_run):
    """Deploy using Podman Quadlet (generate → upload → restart)."""
    compose = _quadlet_step1_generate(env, compose_path, env_file_path, var_overrides, dry_run)
    _quadlet_step2_upload(env, env_name, dry_run)
    _quadlet_step3_reload_and_pull(env, env_name, compose, dry_run)
    _quadlet_step4_restart_and_cleanup(env, env_name, compose, dry_run)


def _resolve_deploy_config(ctx, compose_override: str | None) -> tuple:
    """Resolve environment, variables, and paths for deployment.

    Returns: (config, env_name, env, compose_path, env_file_path, var_overrides, dry_run)
    """
    opts = ctx.obj
    env_name = opts.get("env_name")
    dry_run = opts.get("dry_run", False)
    var_overrides = opts.get("var", {})

    config = load_taskfile(opts.get("taskfile_path"))
    env_name = env_name or config.default_env

    if env_name not in config.environments:
        console.print(f"[red]Unknown environment: {env_name}[/]")
        sys.exit(1)

    env = config.environments[env_name]

    # Resolve variables
    variables = env.resolve_variables(config.variables)
    variables.update(var_overrides)

    compose_path = compose_override or env.compose_file
    env_file_path = env.env_file

    return config, env_name, env, compose_path, env_file_path, var_overrides, dry_run


def _print_deploy_header(
    config, env_name: str, env, compose_path: str, env_file_path: str | None
) -> None:
    """Print deployment configuration header."""
    console.print(
        f"\n[bold]Deploying [cyan]{config.name or 'project'}[/] to [yellow]{env_name}[/][/]"
    )
    console.print(f"  compose:  {compose_path}")
    if env_file_path:
        console.print(f"  env-file: {env_file_path}")
    console.print(f"  runtime:  {env.container_runtime}")
    console.print(f"  manager:  {env.service_manager}")
    console.print()


class DeployStrategy:
    """Pure data class representing selected deploy strategy."""

    def __init__(
        self,
        strategy: str,  # 'local_compose', 'remote_compose', 'ssh_push', 'quadlet', 'unknown'
        env: Any,
        env_name: str,
        env_file_path: str | None,
        config: Any,
        compose_path: str,
        var_overrides: dict,
        dry_run: bool,
    ):
        self.strategy = strategy
        self.env = env
        self.env_name = env_name
        self.env_file_path = env_file_path
        self.config = config
        self.compose_path = compose_path
        self.var_overrides = var_overrides
        self.dry_run = dry_run


def _select_deploy_strategy(
    env: Any,
    env_name: str,
    env_file_path: str | None,
    config: Any,
    compose_path: str,
    var_overrides: dict,
    dry_run: bool,
) -> DeployStrategy:
    """Pure function to select deploy strategy based on environment config.

    Returns DeployStrategy without executing any deployment actions.
    Pipeline purity: this function has no side effects.
    """
    strategy = "unknown"
    if env.service_manager == "compose" and not env.ssh_host:
        strategy = "local_compose"
    elif env.service_manager == "compose" and env.ssh_host:
        strategy = "remote_compose"
    elif env.service_manager in ("podman", "ssh_push") and env.ssh_host:
        strategy = "ssh_push"
    elif env.service_manager == "quadlet":
        strategy = "quadlet"
    elif env.ssh_host and env.container_runtime == "podman":
        # Auto-detect: remote + podman → ssh_push
        strategy = "ssh_push"

    return DeployStrategy(
        strategy=strategy,
        env=env,
        env_name=env_name,
        env_file_path=env_file_path,
        config=config,
        compose_path=compose_path,
        var_overrides=var_overrides,
        dry_run=dry_run,
    )


def _execute_deploy_strategy(strategy: DeployStrategy) -> None:
    """Execute the selected deploy strategy."""
    if strategy.strategy == "local_compose":
        _deploy_local_compose(strategy.env, strategy.env_file_path, strategy.dry_run)
        return
    if strategy.strategy == "remote_compose":
        _deploy_remote_compose(
            strategy.env,
            strategy.env_name,
            strategy.env_file_path,
            strategy.config,
            strategy.dry_run,
        )
        return
    if strategy.strategy == "ssh_push":
        _deploy_ssh_push(strategy.env, strategy.env_name, strategy.config, strategy.dry_run)
        return
    if strategy.strategy == "quadlet":
        _deploy_quadlet(
            strategy.env,
            strategy.env_name,
            strategy.env_file_path,
            strategy.compose_path,
            strategy.var_overrides,
            strategy.dry_run,
        )
        return

    console.print(f"[red]Unknown service_manager: {strategy.env.service_manager}[/]")
    sys.exit(1)


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
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    try:
        config, env_name, env, compose_path, env_file_path, var_overrides, dry_run = (
            _resolve_deploy_config(ctx, compose_override)
        )

        _print_deploy_header(config, env_name, env, compose_path, env_file_path)
        strategy = _select_deploy_strategy(
            env, env_name, env_file_path, config, compose_path, var_overrides, dry_run
        )
        _execute_deploy_strategy(strategy)

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Deploy failed:[/] {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)
