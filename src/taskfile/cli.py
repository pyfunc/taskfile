"""CLI interface for taskfile."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from taskfile import __version__
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    find_taskfile,
    load_taskfile,
)
from taskfile.runner import TaskfileRunner
from taskfile.scaffold import generate_taskfile

console = Console()


def parse_var(ctx, param, value: tuple[str, ...]) -> dict[str, str]:
    """Parse --var KEY=VALUE pairs into a dict."""
    result = {}
    for item in value:
        if "=" not in item:
            raise click.BadParameter(f"Expected KEY=VALUE, got: {item}")
        key, val = item.split("=", 1)
        result[key.strip()] = val.strip()
    return result


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="taskfile")
@click.option("-f", "--file", "taskfile_path", default=None, help="Path to Taskfile.yml")
@click.option("-e", "--env", "env_name", default=None, help="Target environment")
@click.option("--var", multiple=True, callback=parse_var, help="Override variable: --var KEY=VALUE")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx, taskfile_path, env_name, var, dry_run, verbose):
    """taskfile — Universal task runner with multi-environment deploy.

    \b
    Run tasks:     taskfile run build deploy
    List tasks:    taskfile list
    Init project:  taskfile init
    Quick run:     taskfile <task_name> --env prod
    """
    ctx.ensure_object(dict)
    ctx.obj["taskfile_path"] = taskfile_path
    ctx.obj["env_name"] = env_name
    ctx.obj["var"] = var
    ctx.obj["dry_run"] = dry_run
    ctx.obj["verbose"] = verbose

    # If no subcommand, check if first arg is a task name
    if ctx.invoked_subcommand is None:
        # Show help if no args at all
        click.echo(ctx.get_help())


@main.command()
@click.argument("tasks", nargs=-1, required=True)
@click.pass_context
def run(ctx, tasks):
    """Run one or more tasks.

    \b
    Examples:
        taskfile run build
        taskfile run build deploy --env prod
        taskfile run release --var TAG=v1.2.3
        taskfile run deploy --env prod --dry-run
    """
    opts = ctx.obj
    try:
        runner = TaskfileRunner(
            taskfile_path=opts["taskfile_path"],
            env_name=opts["env_name"],
            var_overrides=opts["var"],
            dry_run=opts["dry_run"],
            verbose=opts["verbose"],
        )
        success = runner.run(list(tasks))
        sys.exit(0 if success else 1)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@main.command(name="list")
@click.pass_context
def list_tasks(ctx):
    """List available tasks and environments."""
    opts = ctx.obj
    try:
        config = load_taskfile(opts["taskfile_path"])
        runner = TaskfileRunner(config=config, env_name=opts["env_name"])
        runner.list_tasks()
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@main.command()
@click.option("--template", type=click.Choice(["minimal", "web", "podman", "codereview", "full"]), default="full")
@click.option("--force", is_flag=True, help="Overwrite existing Taskfile")
def init(template, force):
    """Create a new Taskfile.yml in the current directory.

    \b
    Templates:
        minimal    — basic build/deploy tasks
        web        — web app with Docker + Traefik
        podman     — Podman Quadlet + Traefik (low RAM)
        codereview — 3-stage: local(docker) → prod(podman quadlet)
        full       — all features, multi-env example
    """
    outpath = Path("Taskfile.yml")
    if outpath.exists() and not force:
        console.print("[yellow]Taskfile.yml already exists. Use --force to overwrite.[/]")
        sys.exit(1)

    content = generate_taskfile(template)
    outpath.write_text(content)
    console.print(f"[green]✓ Created Taskfile.yml (template: {template})[/]")
    console.print("[dim]  Edit variables and environments, then run: taskfile list[/]")


@main.command()
@click.pass_context
def validate(ctx):
    """Validate the Taskfile without running anything."""
    opts = ctx.obj
    try:
        config = load_taskfile(opts["taskfile_path"])
        from taskfile.parser import validate_taskfile
        warnings = validate_taskfile(config)
        if warnings:
            for w in warnings:
                console.print(f"[yellow]⚠ {w}[/]")
            console.print(f"\n[yellow]{len(warnings)} warning(s) found[/]")
        else:
            console.print("[green]✓ Taskfile is valid[/]")
            console.print(
                f"  {len(config.tasks)} tasks, "
                f"{len(config.environments)} environments"
            )
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@main.command()
@click.argument("task_name")
@click.pass_context
def info(ctx, task_name):
    """Show detailed info about a specific task."""
    opts = ctx.obj
    try:
        config = load_taskfile(opts["taskfile_path"])
        if task_name not in config.tasks:
            console.print(f"[red]Unknown task: {task_name}[/]")
            sys.exit(1)

        task = config.tasks[task_name]
        console.print(f"\n[bold green]{task.name}[/]")
        if task.description:
            console.print(f"  {task.description}")
        if task.deps:
            console.print(f"  [dim]Dependencies:[/] {', '.join(task.deps)}")
        if task.env_filter:
            console.print(f"  [dim]Environments:[/] {', '.join(task.env_filter)}")
        if task.condition:
            console.print(f"  [dim]Condition:[/] {task.condition}")

        console.print(f"\n  [bold]Commands:[/]")
        for cmd in task.commands:
            console.print(f"    → {cmd}")

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
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

        import subprocess

        def _run(cmd: str, label: str = ""):
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

        def _ssh(cmd: str, label: str = ""):
            if not env.ssh_target:
                console.print(f"[red]No SSH host for env '{env_name}'[/]")
                sys.exit(1)
            escaped = cmd.replace("'", "'\\''")
            full = f"ssh {env.ssh_opts} {env.ssh_target} '{escaped}'"
            _run(full, label)

        # ─── Strategy: local compose ──────────────────
        if env.service_manager == "compose" and not env.ssh_host:
            env_flag = f"--env-file {env_file_path}" if env_file_path else ""
            _run(f"{env.compose_command} {env_flag} up -d --build", "Starting local services...")
            console.print("\n[green]✅ Local deploy complete[/]")
            return

        # ─── Strategy: remote compose ─────────────────
        if env.service_manager == "compose" and env.ssh_host:
            env_flag = f"--env-file {env_file_path}" if env_file_path else ""
            _ssh(f"cd /opt/{config.name or 'app'} && {env.compose_command} {env_flag} pull",
                 "Pulling images on remote...")
            _ssh(f"cd /opt/{config.name or 'app'} && {env.compose_command} {env_flag} up -d",
                 "Starting services on remote...")
            console.print(f"\n[green]✅ Remote compose deploy complete ({env_name})[/]")
            return

        # ─── Strategy: Quadlet ────────────────────────
        if env.service_manager == "quadlet":
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
                _ssh(f"mkdir -p {env.quadlet_remote_dir}")
                _run(f"scp {file_list} {env.ssh_target}:{env.quadlet_remote_dir}/")
            else:
                console.print(f"  [dim](dry run — would upload to {env.quadlet_remote_dir})[/]")

            # Step 3: Reload + pull
            console.print(f"\n[bold]Step 3/4: Pull images & reload systemd[/]")
            _ssh("systemctl --user daemon-reload")
            for svc_name in compose.service_names() if not dry_run else ["(services)"]:
                svc = compose.get_service(svc_name) if not dry_run else {}
                image = svc.get("image", "") if svc else ""
                if image and not dry_run:
                    _ssh(f"podman pull {image}")

            # Step 4: Restart services
            console.print(f"\n[bold]Step 4/4: Restarting services[/]")
            for svc_name in compose.service_names() if not dry_run else ["(services)"]:
                _ssh(f"systemctl --user restart {svc_name}")

            _ssh("podman image prune -f", "Cleaning up old images...")

            console.print(f"\n[green]✅ Quadlet deploy complete ({env_name})[/]")
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


if __name__ == "__main__":
    main()


# ─── Quadlet subcommand group ────────────────────────

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

    \b
    Examples:
        taskfile --env prod quadlet upload
        taskfile --env prod quadlet upload -o deploy/quadlet
    """
    opts = ctx.obj or {}
    env_name = opts.get("env_name")
    dry_run = opts.get("dry_run", False)

    try:
        config = load_taskfile(opts.get("taskfile_path"))
        if not env_name:
            # Find first remote environment
            for name, env in config.environments.items():
                if env.ssh_host:
                    env_name = name
                    break
        if not env_name or env_name not in config.environments:
            console.print("[red]Error: No remote environment found. Use --env <name>[/]")
            sys.exit(1)

        env = config.environments[env_name]
        if not env.ssh_target:
            console.print(f"[red]Error: Environment '{env_name}' has no ssh_host[/]")
            sys.exit(1)

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

        remote_dir = env.quadlet_remote_dir
        target = env.ssh_target
        ssh_opts = env.ssh_opts

        console.print(f"[bold]Uploading {len(files)} Quadlet files to {target}:{remote_dir}[/]")

        import subprocess

        # Ensure remote dir exists
        mkdir_cmd = f"ssh {ssh_opts} {target} 'mkdir -p {remote_dir}'"
        console.print(f"  [dim]→ {mkdir_cmd}[/]")
        if not dry_run:
            subprocess.run(mkdir_cmd, shell=True, check=True)

        # Upload files
        file_list = " ".join(str(f) for f in files)
        scp_opts = ssh_opts.replace("-o ", "-o").replace("StrictHostKeyChecking=accept-new", "")
        scp_cmd = f"scp {' '.join(str(f) for f in files)} {target}:{remote_dir}/"
        console.print(f"  [dim]→ {scp_cmd}[/]")
        if not dry_run:
            subprocess.run(scp_cmd, shell=True, check=True)

        # Reload systemd
        reload_cmd = f"ssh {ssh_opts} {target} 'systemctl --user daemon-reload'"
        console.print(f"  [dim]→ {reload_cmd}[/]")
        if not dry_run:
            subprocess.run(reload_cmd, shell=True, check=True)

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

# ─── CI/CD subcommand group ─────────────────────────────

@main.group()
def ci():
    """Generate CI/CD configs and run pipelines locally.

    \b
    Generate:  taskfile ci generate --target github
    Run local: taskfile ci run
    Preview:   taskfile ci preview --target gitlab
    """
    pass


@ci.command(name="generate")
@click.option(
    "--target", "targets", multiple=True,
    help="CI platform: github, gitlab, gitea, drone, jenkins, makefile (repeatable)",
)
@click.option("--all", "gen_all", is_flag=True, help="Generate for all platforms")
@click.option("-o", "--output", "output_dir", default=".", help="Output project directory")
@click.pass_context
def ci_generate(ctx, targets, gen_all, output_dir):
    """Generate CI/CD config files from Taskfile.yml pipeline section.

    \b
    Examples:
        taskfile ci generate --target github
        taskfile ci generate --target github --target gitlab
        taskfile ci generate --all
        taskfile ci generate --target makefile

    \b
    Supported targets:
        github   → .github/workflows/taskfile.yml
        gitlab   → .gitlab-ci.yml
        gitea    → .gitea/workflows/taskfile.yml
        drone    → .drone.yml
        jenkins  → Jenkinsfile
        makefile → Makefile
    """
    from taskfile.cigen import generate_ci, generate_all_ci, list_targets, TARGETS

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))

        if not config.pipeline.stages:
            console.print("[yellow]⚠ No pipeline stages defined in Taskfile.yml[/]")
            console.print("[dim]  Add a 'pipeline' section or 'stage' field on tasks[/]")
            console.print()
            console.print("[dim]  Example:[/]")
            console.print("[dim]  pipeline:[/]")
            console.print("[dim]    stages:[/]")
            console.print("[dim]      - name: test[/]")
            console.print("[dim]        tasks: [lint, test][/]")
            console.print("[dim]      - name: build[/]")
            console.print("[dim]        tasks: [build, push][/]")
            console.print("[dim]        docker_in_docker: true[/]")
            console.print("[dim]      - name: deploy[/]")
            console.print("[dim]        tasks: [deploy][/]")
            console.print("[dim]        env: prod[/]")
            console.print("[dim]        when: manual[/]")
            sys.exit(1)

        console.print(f"[bold]Generating CI/CD configs from Taskfile.yml[/]")
        stages_info = " → ".join(s.name for s in config.pipeline.stages)
        console.print(f"  Pipeline: {stages_info}\n")

        if gen_all:
            generated = generate_all_ci(config, output_dir)
        elif targets:
            generated = []
            for t in targets:
                path = generate_ci(config, t, output_dir)
                generated.append(path)
        else:
            # Default: generate for common platforms
            console.print("[yellow]No target specified. Use --target or --all[/]")
            console.print()
            console.print("[bold]Available targets:[/]")
            for name, path, desc in list_targets():
                console.print(f"  [green]{name:12s}[/] → {path:40s} [dim]({desc})[/]")
            sys.exit(0)

        console.print(f"\n[green]✓ Generated {len(generated)} CI/CD config(s)[/]")
        console.print("[dim]  All configs call 'taskfile run' — your pipeline logic stays in Taskfile.yml[/]")

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="run")
@click.option("--stage", "stages", multiple=True, help="Run specific stage(s) only")
@click.option("--skip", "skip_stages", multiple=True, help="Skip specific stage(s)")
@click.option("--stop-at", default=None, help="Stop after this stage")
@click.pass_context
def ci_run(ctx, stages, skip_stages, stop_at):
    """Run CI/CD pipeline stages locally.

    Runs the same pipeline that would run on GitHub/GitLab/etc,
    but directly on your machine. No runner needed.

    \b
    Examples:
        taskfile ci run                           # full pipeline
        taskfile ci run --stage test              # only test stage
        taskfile ci run --stage test --stage build
        taskfile ci run --skip deploy             # all except deploy
        taskfile ci run --stop-at build           # test + build, skip deploy
        taskfile --env prod ci run --stage deploy # deploy stage with prod env
        taskfile --dry-run ci run                 # preview commands
    """
    from taskfile.cirunner import PipelineRunner

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))
        runner = PipelineRunner(
            config=config,
            env_name=opts.get("env_name"),
            var_overrides=opts.get("var", {}),
            dry_run=opts.get("dry_run", False),
            verbose=opts.get("verbose", False),
        )

        stage_list = list(stages) if stages else None
        skip_list = list(skip_stages) if skip_stages else None

        success = runner.run(
            stage_filter=stage_list,
            skip_stages=skip_list,
            stop_at=stop_at,
        )
        sys.exit(0 if success else 1)

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="list")
@click.pass_context
def ci_list(ctx):
    """List pipeline stages defined in Taskfile.yml."""
    from taskfile.cirunner import PipelineRunner

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))
        runner = PipelineRunner(config=config)
        runner.list_stages()
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="preview")
@click.option("--target", required=True, help="CI platform to preview")
@click.pass_context
def ci_preview(ctx, target):
    """Preview generated CI/CD config without writing files.

    \b
    Examples:
        taskfile ci preview --target github
        taskfile ci preview --target gitlab
    """
    from taskfile.cigen import preview_ci

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))
        content = preview_ci(config, target)
        console.print(f"[bold]Preview: {target}[/]\n")
        console.print(content)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="targets")
def ci_targets():
    """List available CI/CD generation targets."""
    from taskfile.cigen import list_targets

    console.print("\n[bold]Available CI/CD targets:[/]")
    for name, path, desc in list_targets():
        console.print(f"  [green]{name:12s}[/] → {path:42s} [dim]{desc}[/]")
    console.print()
    console.print("[dim]Generate: taskfile ci generate --target <name>[/]")
