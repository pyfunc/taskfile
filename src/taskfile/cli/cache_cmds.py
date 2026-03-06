"""CLI commands for cache management."""

from __future__ import annotations

import clickmd as click
from rich.table import Table
from rich import box

from taskfile.cli.main import console, main
from taskfile.cache import TaskCache, get_project_hash
from taskfile.parser import TaskfileNotFoundError


@main.group()
def cache():
    """💾 Cache management - view, clear, or disable task caching.

    Taskfile caches task outputs to avoid re-running unchanged tasks.
    This speeds up incremental builds and avoids redundant work.

    \b
    Examples:
        taskfile cache show       # Show cache statistics
        taskfile cache clear      # Clear all cache entries
        taskfile cache clear build  # Clear cache for 'build' task only
    """
    pass


@cache.command(name="show")
def cache_show():
    """Show cache statistics and entries."""
    try:
        project_hash = get_project_hash()
        task_cache = TaskCache(project_hash)
        stats = task_cache.get_stats()
        
        console.print(f"\n[bold]Cache Statistics[/]")
        console.print(f"  Cache file: {stats['cache_file']}")
        console.print(f"  Total entries: {stats['total_entries']}")
        console.print(f"  Unique tasks: {stats['unique_tasks']}")
        console.print(f"  Total size: {stats['total_size_bytes'] / 1024:.1f} KB")
        
    except TaskfileNotFoundError:
        console.print("[red]Error:[/] No Taskfile found in current directory")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")


@cache.command(name="clear")
@click.argument("task_name", required=False)
@click.option("--all", "clear_all", is_flag=True, help="Clear all cache entries")
def cache_clear(task_name, clear_all):
    """Clear cache entries.

    Without arguments, clears all cache entries for current project.
    With task_name, clears only entries for that specific task.
    """
    try:
        project_hash = get_project_hash()
        task_cache = TaskCache(project_hash)
        
        if task_name:
            count = task_cache.clear(task_name)
            console.print(f"[green]✓ Cleared {count} cache entries for task '{task_name}'[/]")
        else:
            count = task_cache.clear(None)
            console.print(f"[green]✓ Cleared {count} cache entries[/]")
            
    except TaskfileNotFoundError:
        console.print("[red]Error:[/] No Taskfile found in current directory")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
