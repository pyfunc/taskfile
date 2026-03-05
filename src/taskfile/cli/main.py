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


def _print_nearby_taskfiles(nearby: list[tuple[Path, int]]) -> None:
    """Print information about nearby Taskfiles and how to use them."""
    if not nearby:
        return
    
    console.print("\n[bold yellow]📍 Found Taskfiles in nearby directories:[/]")
    for path, level in sorted(nearby, key=lambda x: (abs(x[1]), str(x[0]))):
        if level == 0:
            rel = f"./{path.name}"
            hint = "[green]← you are here[/]"
        elif level < 0:
            parent_parts = [".."] * abs(level)
            rel = "/".join(parent_parts) + f"/{path.name}"
            hint = f"[yellow]({abs(level)} level{'s' if abs(level) > 1 else ''} up)[/]"
        else:
            try:
                rel = str(path.relative_to(Path.cwd()))
            except ValueError:
                rel = str(path)
            hint = f"[blue]({level} level{'s' if level > 1 else ''} down)[/]"
        console.print(f"   {rel} {hint}")
    
    # Show how to use the first found
    first = nearby[0]
    console.print("\n[dim]To use:[/]")
    if first[1] == 0:
        console.print(f"  taskfile run <task>")
    elif first[1] < 0:
        parent_parts = [".."] * abs(first[1])
        console.print(f"  cd {'/'.join(parent_parts)} && taskfile run <task>")
    else:
        try:
            rel_dir = str(first[0].parent.relative_to(Path.cwd()))
        except ValueError:
            rel_dir = str(first[0].parent)
        console.print(f"  cd {rel_dir} && taskfile run <task>")


def _run_env_group(
    taskfile_path,
    env_group: str,
    task_names: list[str],
    platform_name: str | None = None,
    var_overrides: dict[str, str] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Run tasks across all environments in a group using the group's strategy.

    Strategies:
        rolling  — one environment at a time, pause between each
        canary   — first N environments, then rest after confirmation
        parallel — all environments concurrently (via ThreadPoolExecutor)
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    config = load_taskfile(taskfile_path)

    if env_group not in config.environment_groups:
        console.print(f"[red]Error: Environment group '{env_group}' not found[/]")
        available = ", ".join(sorted(config.environment_groups.keys()))
        if available:
            console.print(f"[dim]  Available groups: {available}[/]")
        return False

    group = config.environment_groups[env_group]
    if not group.members:
        console.print(f"[yellow]Group '{env_group}' has no members[/]")
        return True

    console.print(
        f"[bold]Running on group '{env_group}' "
        f"({len(group.members)} envs, strategy={group.strategy})[/]\n"
    )

    def run_on_env(env_name: str) -> bool:
        console.print(f"[cyan]━━━ {env_name} ━━━[/]")
        runner = TaskfileRunner(
            config=config,
            env_name=env_name,
            platform_name=platform_name,
            var_overrides=var_overrides or {},
            dry_run=dry_run,
            verbose=verbose,
        )
        return runner.run(task_names)

    if group.strategy == "rolling":
        return _group_rolling(group.members, run_on_env)
    elif group.strategy == "canary":
        return _group_canary(group.members, run_on_env, group.canary_count)
    else:
        return _group_parallel(group.members, run_on_env, group.max_parallel)


def _group_rolling(members: list[str], run_fn) -> bool:
    """Execute on each member sequentially with a pause between."""
    import time
    all_ok = True
    for i, env_name in enumerate(members):
        if not run_fn(env_name):
            console.print(f"[red]✗ Failed on {env_name} — stopping rolling deploy[/]")
            return False
        if i < len(members) - 1:
            console.print("[dim]  ⏳ Pause before next...[/]")
            time.sleep(2)
    return all_ok


def _group_canary(members: list[str], run_fn, canary_count: int) -> bool:
    """Deploy to canary members first, then the rest."""
    canaries = members[:canary_count]
    rest = members[canary_count:]

    console.print(f"[bold]🐤 Canary: {', '.join(canaries)}[/]\n")
    for env_name in canaries:
        if not run_fn(env_name):
            console.print(f"[red]✗ Canary failed on {env_name} — aborting[/]")
            return False

    if rest:
        console.print(f"\n[green]✓ Canary OK[/] — deploying to remaining {len(rest)} env(s)\n")
        for env_name in rest:
            if not run_fn(env_name):
                console.print(f"[red]✗ Failed on {env_name}[/]")
                return False

    return True


def _group_parallel(members: list[str], run_fn, max_parallel: int) -> bool:
    """Execute on all members in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=min(max_parallel, len(members))) as ex:
        futures = {ex.submit(run_fn, env): env for env in members}
        for future in as_completed(futures):
            env = futures[future]
            try:
                if not future.result():
                    failed.append(env)
            except Exception as exc:
                console.print(f"[red]✗ {env}: {exc}[/]")
                failed.append(env)

    if failed:
        console.print(f"\n[red]✗ Failed on: {', '.join(failed)}[/]")
        return False

    console.print(f"\n[green]✓ All {len(members)} environments completed[/]")
    return True


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
@click.option("-G", "--env-group", "env_group", default=None, help="Target environment group (fleet)")
@click.option("-p", "--platform", "platform_name", default=None, help="Target platform (e.g. desktop, web)")
@click.option("--var", multiple=True, callback=parse_var, help="Override variable: --var KEY=VALUE")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx, taskfile_path, env_name, env_group, platform_name, var, dry_run, verbose):
    """taskfile — Universal task runner with multi-environment deploy.

    \b
    Run tasks:     taskfile run build deploy
    List tasks:    taskfile list
    Init project:  taskfile init
    Quick run:     taskfile <task_name> --env prod --platform web
    Fleet deploy:  taskfile -G kiosks run deploy-kiosk --var TAG=v1.0
    """
    ctx.ensure_object(dict)
    ctx.obj["taskfile_path"] = taskfile_path
    ctx.obj["env_name"] = env_name
    ctx.obj["env_group"] = env_group
    ctx.obj["platform_name"] = platform_name
    ctx.obj["var"] = var
    ctx.obj["dry_run"] = dry_run
    ctx.obj["verbose"] = verbose

    # If no subcommand, check if first arg is a task name
    if ctx.invoked_subcommand is None:
        # Show help if no args at all
        click.echo(ctx.get_help())


@main.command()
@click.argument("tasks", nargs=-1, required=True)
@click.option("--tags", "run_tags", default=None, help="Run only tasks matching these tags (comma-separated)")
@click.pass_context
def run(ctx, tasks, run_tags):
    """Run one or more tasks.

    \b
    Examples:
        taskfile run build
        taskfile run build deploy --env prod
        taskfile run release --var TAG=v1.2.3
        taskfile run deploy --env prod --dry-run
        taskfile -G kiosks run deploy-kiosk --var TAG=v1.0
        taskfile run --tags ci build test lint
    """
    opts = ctx.obj
    env_group = opts.get("env_group")
    tag_filter = [t.strip() for t in run_tags.split(",")] if run_tags else None

    try:
        if env_group:
            success = _run_env_group(
                taskfile_path=opts["taskfile_path"],
                env_group=env_group,
                task_names=list(tasks),
                platform_name=opts["platform_name"],
                var_overrides=opts["var"],
                dry_run=opts["dry_run"],
                verbose=opts["verbose"],
            )
        else:
            runner = TaskfileRunner(
                taskfile_path=opts["taskfile_path"],
                env_name=opts["env_name"],
                platform_name=opts["platform_name"],
                var_overrides=opts["var"],
                dry_run=opts["dry_run"],
                verbose=opts["verbose"],
            )
            task_list = list(tasks)
            if tag_filter:
                task_list = _filter_tasks_by_tags(runner.config, task_list, tag_filter)
                if not task_list:
                    console.print(f"[yellow]No tasks match tags: {', '.join(tag_filter)}[/]")
                    sys.exit(0)
            success = runner.run(task_list)
        sys.exit(0 if success else 1)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


def _filter_tasks_by_tags(config, task_names: list[str], tags: list[str]) -> list[str]:
    """Filter task names to only those whose tags overlap with the requested tags."""
    filtered = []
    for name in task_names:
        task = config.tasks.get(name)
        if task and task.tags and any(t in task.tags for t in tags):
            filtered.append(name)
        elif task and not task.tags:
            # Tasks without tags are included when explicit task names given
            filtered.append(name)
    return filtered


@main.command(name="list")
@click.pass_context
def list_tasks(ctx):
    """List available tasks and environments."""
    opts = ctx.obj
    try:
        config = load_taskfile(opts["taskfile_path"])
        runner = TaskfileRunner(config=config, env_name=opts["env_name"], platform_name=opts["platform_name"])
        runner.list_tasks()
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


@main.command()
@click.option("--template", type=click.Choice(["minimal", "web", "podman", "codereview", "full", "multiplatform", "publish", "kubernetes", "terraform", "iot"]), default="full")
@click.option("--force", is_flag=True, help="Overwrite existing Taskfile")
def init(template, force):
    """Create a new Taskfile.yml in the current directory.

    \b
    Templates:
        minimal        — basic build/deploy tasks
        web            — web app with Docker + Traefik
        podman         — Podman Quadlet + Traefik (low RAM)
        codereview     — 3-stage: local(docker) → prod(podman quadlet)
        full           — all features, multi-env example
        multiplatform  — desktop+web × local+prod deployment
        publish        — multi-registry publish (PyPI+npm+Docker+GitHub)
        kubernetes     — Kubernetes + Helm multi-cluster deployment
        terraform      — Terraform IaC multi-environment
        iot            — IoT/edge fleet with rolling/canary/parallel
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
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
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
        if task.platform_filter:
            console.print(f"  [dim]Platforms:[/] {', '.join(task.platform_filter)}")
        if task.condition:
            console.print(f"  [dim]Condition:[/] {task.condition}")
        if task.parallel:
            console.print(f"  [dim]Parallel:[/] yes (deps run concurrently)")
        if task.ignore_errors:
            console.print(f"  [dim]Ignore errors:[/] yes")
        if task.retries:
            console.print(f"  [dim]Retries:[/] {task.retries} (delay: {task.retry_delay}s)")
        if task.timeout:
            console.print(f"  [dim]Timeout:[/] {task.timeout}s")
        if task.tags:
            console.print(f"  [dim]Tags:[/] {', '.join(task.tags)}")
        if task.register:
            console.print(f"  [dim]Register:[/] {task.register}")

        console.print(f"\n  [bold]Commands:[/]")
        for cmd in task.commands:
            console.print(f"    → {cmd}")

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


@main.command(name="import")
@click.argument("source", type=click.Path(exists=True))
@click.option("--type", "source_type", type=click.Choice(["github-actions", "gitlab-ci", "makefile", "shell", "dockerfile"]), default=None, help="Source file type (auto-detected if omitted)")
@click.option("-o", "--output", "output_path", default="Taskfile.yml", help="Output path (default: Taskfile.yml)")
@click.option("--force", is_flag=True, help="Overwrite existing output file")
def import_cmd(source, source_type, output_path, force):
    """Import CI/CD config, Makefile, or script INTO Taskfile.yml.

    \b
    Supported sources:
        github-actions  — .github/workflows/*.yml
        gitlab-ci       — .gitlab-ci.yml
        makefile         — Makefile / GNUmakefile
        shell            — *.sh (functions become tasks)
        dockerfile       — Dockerfile (stages become tasks)

    \b
    Examples:
        taskfile import .github/workflows/ci.yml
        taskfile import .gitlab-ci.yml --type gitlab-ci
        taskfile import Makefile -o Taskfile.yml
        taskfile import deploy.sh --type shell
    """
    from taskfile.importer import import_file

    outpath = Path(output_path)
    if outpath.exists() and not force:
        console.print(f"[yellow]{outpath} already exists. Use --force to overwrite.[/]")
        sys.exit(1)

    try:
        result = import_file(source, source_type)
        outpath.write_text(result, encoding="utf-8")
        console.print(f"[green]✓ Imported {source} → {outpath}[/]")
        console.print("[dim]  Review and customize the generated Taskfile, then run: taskfile list[/]")
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

