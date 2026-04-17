"""CLI interface for taskfile.

Extracted modules:
- group_strategies.py  — rolling/canary/parallel env group execution
- validate_cmd.py      — file validation helpers for --files / --deps
"""

from __future__ import annotations

import sys
from pathlib import Path

import clickmd as click
import click as click_std
from taskfile.cli.click_compat import BadParameter
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
from taskfile.cli.group_strategies import run_env_group as _run_env_group

console = Console()


def _format_nearby_path(path: Path, level: int) -> tuple[str, str]:
    """Format a nearby Taskfile path and hint based on directory level."""
    if level == 0:
        return f"./{path.name}", "[green]← you are here[/]"
    if level < 0:
        parent_parts = [".."] * abs(level)
        rel = "/".join(parent_parts) + f"/{path.name}"
        return rel, f"[yellow]({abs(level)} level{'s' if abs(level) > 1 else ''} up)[/]"
    try:
        rel = str(path.relative_to(Path.cwd()))
    except ValueError:
        rel = str(path)
    return rel, f"[blue]({level} level{'s' if level > 1 else ''} down)[/]"


def _nearby_cd_hint(path: Path, level: int) -> str:
    """Return a 'cd ...' hint for reaching a nearby Taskfile."""
    if level == 0:
        return "taskfile <task>"
    if level < 0:
        return f"cd {'/'.join(['..'] * abs(level))} && taskfile <task>"
    try:
        rel_dir = str(path.parent.relative_to(Path.cwd()))
    except ValueError:
        rel_dir = str(path.parent)
    return f"cd {rel_dir} && taskfile <task>"


def _print_nearby_taskfiles(nearby: list[tuple[Path, int]]) -> None:
    """Print information about nearby Taskfiles and how to use them."""
    if not nearby:
        return
    
    console.print("\n[bold yellow]📍 Found Taskfiles in nearby directories:[/]")
    for path, level in sorted(nearby, key=lambda x: (abs(x[1]), str(x[0]))):
        rel, hint = _format_nearby_path(path, level)
        console.print(f"   {rel} {hint}")
    
    console.print("\n[dim]To use:[/]")
    console.print(f"  {_nearby_cd_hint(nearby[0][0], nearby[0][1])}")


def _suggest_similar_tasks(unknown: str, available: list[str], max_suggestions: int = 3) -> list[str]:
    """Suggest similar task names based on string similarity."""
    from difflib import get_close_matches
    
    # Get close matches using difflib
    matches = get_close_matches(unknown, available, n=max_suggestions, cutoff=0.4)
    
    # Also check for partial matches
    partial_matches = [t for t in available if unknown in t or t in unknown]
    
    # Combine and deduplicate
    all_matches = matches + [p for p in partial_matches if p not in matches]
    
    return all_matches[:max_suggestions]


def _check_unknown_tasks(task_list: list[str], available_tasks: dict) -> None:
    """Check for unknown tasks, print suggestions, and exit if any found."""
    unknown_tasks = [t for t in task_list if t not in available_tasks]
    if not unknown_tasks:
        return
    for unknown in unknown_tasks:
        suggestions = _suggest_similar_tasks(unknown, list(available_tasks.keys()))
        console.print(f"[red]✗ Unknown task:[/] {unknown}")
        if suggestions:
            console.print(f"[dim]  Did you mean: {', '.join(suggestions)}?[/]")
    task_names = sorted(available_tasks.keys())
    console.print(f"\n[yellow]Available tasks:[/] {', '.join(task_names[:20])}")
    if len(task_names) > 20:
        console.print(f"[dim]  ... and {len(task_names) - 20} more[/]")
    sys.exit(1)


def parse_var(ctx, param, value: tuple[str, ...]) -> dict[str, str]:
    """Parse --var KEY=VALUE pairs into a dict."""
    result = {}
    for item in value:
        if "=" not in item:
            raise BadParameter(f"Expected KEY=VALUE, got: {item}")
        key, val = item.split("=", 1)
        result[key.strip()] = val.strip()
    return result


@click.group(invoke_without_command=True)
@click_std.version_option(__version__, prog_name="taskfile")
@click.option("-f", "--file", "taskfile_path", default=None, help="Path to Taskfile.yml")
@click.option("-e", "--env", "env_name", default=None, help="Target environment")
@click.option("-G", "--env-group", "env_group", default=None, help="Target environment group (fleet)")
@click.option("-p", "--platform", "platform_name", default=None, help="Target platform (e.g. desktop, web)")
@click.option("--var", multiple=True, callback=parse_var, help="Override variable: --var KEY=VALUE")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx, taskfile_path, env_name, env_group, platform_name, var, dry_run, verbose):
    """**taskfile** — Universal task runner with multi-environment deploy.

## Quick Start

| Command | Description |
|---------|-------------|
| `taskfile run <task>` | Run a task |
| `taskfile list` | List available tasks |
| `taskfile init` | Create a new Taskfile.yml |

## Examples

**Run tasks:**
```bash
taskfile run build deploy
taskfile run deploy --env prod --var TAG=v1.0
```

**Fleet deploy:**
```bash
taskfile -G kiosks run deploy-kiosk --var TAG=v1.0
```
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
@click.option("--explain", is_flag=True, help="Show execution plan without running (what will happen)")
@click.option("--teach", is_flag=True, help="Educational mode — explain what each step does and why")
@click.pass_context
def run(ctx, tasks, run_tags, explain, teach):
    """**Run one or more tasks** defined in Taskfile.yml.

## Usage

```bash
taskfile run <task> [<task> ...]
```

## Options

| Option | Description |
|--------|-------------|
| `--tags` | Filter tasks by tags (comma-separated) |
| `-e, --env` | Target environment |
| `-p, --platform` | Target platform |
| `--var KEY=VALUE` | Override variables |
| `--dry-run` | Preview without executing |
| `--explain` | Show execution plan without running |
| `--teach` | Educational mode — explain each step |

## Examples

```bash
# Run single task
taskfile run build

# Run multiple tasks
taskfile run build deploy

# Run with environment
taskfile run deploy --env prod

# Run with variable override
taskfile run release --var TAG=v1.2.3

# Run with tags filter
taskfile run --tags ci build test

# Preview execution plan
taskfile run deploy --env prod --explain

# Educational mode
taskfile run deploy --teach
```
"""
    opts = ctx.obj
    tag_filter = [t.strip() for t in run_tags.split(",")] if run_tags else None

    try:
        if explain or teach:
            _run_explain_mode(opts, list(tasks), tag_filter, teach=teach)
        else:
            success = _run_tasks(opts, list(tasks), tag_filter)
            sys.exit(0 if success else 1)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


def _run_explain_mode(opts: dict, task_list: list[str], tag_filter: list[str] | None, *, teach: bool) -> None:
    """Handle --explain / --teach mode: analyze execution plan without running."""
    from taskfile.runner.resolver import TaskResolver
    from taskfile.runner.explainer import (
        TaskExplainer, print_explain_report, print_teach_report,
    )
    config = load_taskfile(opts["taskfile_path"])
    resolver = TaskResolver(
        config,
        env_name=opts["env_name"],
        platform_name=opts["platform_name"],
        var_overrides=opts["var"],
    )
    _check_unknown_tasks(task_list, config.tasks)
    if tag_filter:
        task_list = _filter_tasks_by_tags(config, task_list, tag_filter)
        if not task_list:
            console.print(f"[yellow]No tasks match tags: {', '.join(tag_filter)}[/]")
            sys.exit(0)

    explainer = TaskExplainer(resolver)
    report = explainer.explain(task_list)

    if teach:
        print_teach_report(report, task_list, resolver.env_name, config)
    else:
        print_explain_report(report, task_list, resolver.env_name)

    sys.exit(1 if report.has_errors else 0)


def _run_tasks(opts: dict, task_list: list[str], tag_filter: list[str] | None) -> bool:
    """Execute tasks normally, via env group or single runner. Returns success."""
    env_group = opts.get("env_group")
    if env_group:
        return _run_env_group(
            taskfile_path=opts["taskfile_path"],
            env_group=env_group,
            task_names=task_list,
            platform_name=opts["platform_name"],
            var_overrides=opts["var"],
            dry_run=opts["dry_run"],
            verbose=opts["verbose"],
        )

    runner = TaskfileRunner(
        taskfile_path=opts["taskfile_path"],
        env_name=opts["env_name"],
        platform_name=opts["platform_name"],
        var_overrides=opts["var"],
        dry_run=opts["dry_run"],
        verbose=opts["verbose"],
    )
    _check_unknown_tasks(task_list, runner.config.tasks)

    if tag_filter:
        task_list = _filter_tasks_by_tags(runner.config, task_list, tag_filter)
        if not task_list:
            console.print(f"[yellow]No tasks match tags: {', '.join(tag_filter)}[/]")
            sys.exit(0)
    return runner.run(task_list)


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
    """**List available tasks and environments** from Taskfile.yml.

## Output

Shows:
- **Tasks** with descriptions and dependencies
- **Environments** (local, staging, prod, etc.)
- **Variables** defined in the Taskfile

## Examples

```bash
# List all tasks
taskfile list

# List with specific environment
taskfile --env prod list
```
"""
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
@click.option("--files", "check_files", is_flag=True, help="Check all dependent files (scripts, env, compose)")
@click.option("--deps", "show_deps", is_flag=True, help="Show dependency tree for all tasks")
@click.pass_context
def validate(ctx, check_files, show_deps):
    """**Validate the Taskfile** without running anything.

## Checks Performed

- Task definitions are valid
- Dependencies exist
- Script files are accessible
- Environment configurations

## Options

| Option | Description |
|--------|-------------|
| `--files` | Check all dependent files exist |
| `--deps` | Show dependency tree |

## Examples

```bash
# Basic validation
taskfile validate

# Check all files
taskfile validate --files

# Show dependency tree
taskfile validate --deps
```
"""
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

        # Summary
        script_tasks = [n for n, t in config.tasks.items() if t.script]
        cmd_tasks = [n for n, t in config.tasks.items() if t.commands]
        dep_tasks = [n for n, t in config.tasks.items() if t.deps]
        console.print(
            f"  [dim]{len(config.tasks)} tasks[/] "
            f"({len(cmd_tasks)} with commands, {len(script_tasks)} with scripts), "
            f"[dim]{len(config.environments)} environments[/]"
        )
        if dep_tasks:
            console.print(f"  [dim]{len(dep_tasks)} tasks have dependencies[/]")

        # --files: detailed file checks
        if check_files:
            from taskfile.cli.validate_cmd import validate_dependent_files
            validate_dependent_files(config)

        # --deps: show dependency tree
        if show_deps:
            from taskfile.cli.validate_cmd import print_dependency_tree
            print_dependency_tree(config)

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


# ─── Register extracted command modules ───
import taskfile.cli.info_cmd  # noqa: E402, F401 — registers 'info' command
import taskfile.cli.explain_cmd  # noqa: E402, F401 — registers 'explain' command


if __name__ == "__main__":
    main()

