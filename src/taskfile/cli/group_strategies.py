"""Environment group execution strategies (rolling, canary, parallel)."""

from __future__ import annotations

from rich.console import Console

from taskfile.parser import load_taskfile
from taskfile.runner import TaskfileRunner

console = Console()


def run_env_group(
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
