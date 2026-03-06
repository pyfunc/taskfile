"""Interactive menu commands — setup, watch, graph, serve."""

from __future__ import annotations

import sys

import clickmd as click

from taskfile.cli.main import console, main
from taskfile.parser import TaskfileNotFoundError, TaskfileParseError


@main.group()
def setup():
    """**🛠️ Setup project** — hosts, env, dependencies.

## Commands

| Command | Description |
|---------|-------------|
| `hosts` | Configure deployment hosts (staging/prod) |
| `env` | Configure environment variables (.env) |

## Examples

```bash
# Configure deployment hosts
taskfile setup hosts

# Configure environment variables
taskfile setup env
```
"""


@setup.command()
@click.pass_context
def hosts(ctx):
    """**Configure deployment hosts** (staging/prod) interactively.

Runs the setup-hosts task from Taskfile.yml with interactive prompts
for server addresses, SSH keys, and deployment configuration.

## Example

```bash
taskfile setup hosts
```
"""
    from taskfile.runner import TaskfileRunner

    opts = ctx.obj
    try:
        runner = TaskfileRunner(
            taskfile_path=opts["taskfile_path"],
            env_name=opts["env_name"],
            platform_name=opts["platform_name"],
            var_overrides=opts["var"],
            dry_run=opts["dry_run"],
            verbose=opts["verbose"],
        )

        if "setup-hosts" not in runner.config.tasks:
            console.print("[yellow]⚠ Task 'setup-hosts' not found in Taskfile.yml[/]")
            console.print("[dim]  Run: taskfile list  — to see available tasks[/]")
            sys.exit(1)

        success = runner.run(["setup-hosts"])
        sys.exit(0 if success else 1)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        from taskfile.cli.main import _print_nearby_taskfiles
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


@setup.command()
@click.pass_context
def env(ctx):
    """**Configure environment variables** (.env) interactively.

Runs the setup-env task from Taskfile.yml with interactive prompts
for LLM provider selection, API keys, ports, etc.

## Example

```bash
taskfile setup env
```
"""
    from taskfile.runner import TaskfileRunner

    opts = ctx.obj
    try:
        runner = TaskfileRunner(
            taskfile_path=opts["taskfile_path"],
            env_name=opts["env_name"],
            platform_name=opts["platform_name"],
            var_overrides=opts["var"],
            dry_run=opts["dry_run"],
            verbose=opts["verbose"],
        )

        if "setup-env" not in runner.config.tasks:
            console.print("[yellow]⚠ Task 'setup-env' not found in Taskfile.yml[/]")
            console.print("[dim]  Add setup-env task or use: taskfile setup hosts[/]")
            sys.exit(1)

        success = runner.run(["setup-env"])
        sys.exit(0 if success else 1)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        from taskfile.cli.main import _print_nearby_taskfiles
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


@main.command()
@click.argument("tasks", nargs=-1, required=True)
@click.option("--path", "-p", multiple=True, help="Path(s) to watch (default: current directory)")
@click.option("--debounce", "-d", default=300, help="Debounce time in milliseconds (default: 300)")
@click.pass_context
def watch(ctx, tasks, path, debounce):
    """**👁️ Watch files** and run tasks on changes.

Automatically detects file changes and re-runs specified tasks.
Useful for development workflows like auto-rebuilding on code changes.

## Options

| Option | Description |
|--------|-------------|
| `-p, --path` | Path(s) to watch |
| `-d, --debounce` | Debounce time in ms (default: 300) |

## Examples

```bash
# Watch current dir, run 'build' on changes
taskfile watch build

# Run multiple tasks on change
taskfile watch build test

# Watch only 'src' directory
taskfile watch -p src build

# Watch multiple paths
taskfile watch -p src -p tests test

# 500ms debounce
taskfile watch -d 500 build
```
"""
    from taskfile.watch import watch_tasks
    from taskfile.runner import TaskfileRunner

    opts = ctx.obj
    
    watch_paths = list(path) if path else None
    
    try:
        runner = TaskfileRunner(
            taskfile_path=opts["taskfile_path"],
            env_name=opts["env_name"],
            platform_name=opts["platform_name"],
            var_overrides=opts["var"],
            dry_run=opts["dry_run"],
            verbose=opts["verbose"],
        )
        
        watch_tasks(
            task_names=list(tasks),
            watch_paths=watch_paths,
            runner=runner,
            debounce_ms=debounce,
        )
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        from taskfile.cli.main import _print_nearby_taskfiles
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


@main.command()
@click.argument("task_name", required=False)
@click.option("--dot", "-d", is_flag=True, help="Export to Graphviz DOT format")
@click.option("--output", "-o", type=click.Path(), help="Output file for DOT export")
@click.pass_context
def graph(ctx, task_name, dot, output):
    """**🕸️ Show task dependency graph**.

Visualizes task dependencies as a tree or exports to Graphviz DOT format.
Helps understand the relationships between tasks.

## Options

| Option | Description |
|--------|-------------|
| `-d, --dot` | Export to DOT format |
| `-o, --output` | Output file for DOT export |

## Examples

```bash
# Show all task dependencies
taskfile graph

# Show dependencies for 'build' task only
taskfile graph build

# Export to DOT format
taskfile graph --dot

# Save to file
taskfile graph --dot -o tasks.dot
```
"""
    from taskfile.graph import print_task_tree, print_dependency_list, export_to_dot
    from taskfile.parser import load_taskfile

    opts = ctx.obj
    
    try:
        config = load_taskfile(opts["taskfile_path"])
        
        if dot:
            # Export to DOT format
            from pathlib import Path
            output_path = Path(output) if output else None
            dot_content = export_to_dot(config, output_path)
            
            if output:
                console.print(f"[green]✓ Exported to {output}[/]")
                console.print("[dim]Generate image with: dot -Tpng -o graph.png[/]")
            else:
                console.print(dot_content)
        elif task_name:
            # Show specific task
            print_task_tree(config, task_name)
        else:
            # Show all tasks
            print_task_tree(config)
            
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        from taskfile.cli.main import _print_nearby_taskfiles
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)


@main.command()
@click.option("--port", "-p", default=8080, help="Port to run server on (default: 8080)")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
def serve(port, no_browser):
    """**🌐 Start web dashboard** for managing tasks.

Opens a web UI in your browser for visual task management.
You can view, search, and run tasks from the browser.

## Options

| Option | Description |
|--------|-------------|
| `-p, --port` | Port to run server on (default: 8080) |
| `--no-browser` | Don't auto-open browser |

## Examples

```bash
# Start on default port 8080
taskfile serve

# Use custom port
taskfile serve -p 3000

# Don't auto-open browser
taskfile serve --no-browser
```
"""
    from taskfile.webui import serve_dashboard
    
    console.print(f"[bold green]🌐 Starting Taskfile Web UI...[/]")
    console.print(f"[dim]Port: {port}[/]")
    
    try:
        serve_dashboard(port=port, open_browser=not no_browser)
    except Exception as e:
        console.print(f"[red]Failed to start server: {e}[/]")
        sys.exit(1)
