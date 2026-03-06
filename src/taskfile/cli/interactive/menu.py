"""Interactive menu commands — setup, watch, graph, serve, clean."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import clickmd as click
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt

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
@click.option("--env-file", default=".env", help="Path to .env file (default: .env)")
def hosts(env_file):
    """**Configure deployment hosts** (staging/prod) interactively.

Native interactive prompts for server addresses and SSH users.
No shell scripts required — works out of the box.

## Example

```bash
taskfile setup hosts
```
"""
    from taskfile.deploy_utils import load_env_file, update_env_var

    console.print(Panel.fit(
        "[bold green]🌐 Deployment Hosts Configuration[/]",
        border_style="green",
    ))

    # Load current values
    env_path = Path(env_file)
    if not env_path.exists():
        console.print(f"  [yellow]⚠[/] {env_file} not found — creating...")
        env_path.touch()
    current = load_env_file(env_path)

    console.print("\n[dim]Examples:[/]")
    console.print("  Host:  staging.example.com, 203.0.113.10")
    console.print("  User:  deploy, ubuntu, root")
    console.print("  [dim]Press Enter to keep current value[/]")

    host_vars = [
        ("STAGING_HOST", "Staging host", "staging.example.com"),
        ("PROD_HOST", "Production host", "prod.example.com"),
        ("DEPLOY_USER", "Deploy SSH user", "root"),
    ]

    for var_name, label, default in host_vars:
        current_val = current.get(var_name, "")
        display_default = current_val or default
        new_val = Prompt.ask(f"  {label}", default=display_default)
        update_env_var(var_name, new_val, env_path)
        console.print(f"  [green]✓[/] {var_name}={new_val}")

    console.print(f"\n[green]✅ Hosts saved to {env_file}[/]")
    console.print("\n[dim]Next: taskfile doctor[/]")


@setup.command()
@click.option("--env-file", default=".env", help="Path to .env file (default: .env)")
def env(env_file):
    """**Configure environment variables** (.env) interactively.

Native interactive prompts for ports, project name, and version.
No shell scripts required.

## Example

```bash
taskfile setup env
```
"""
    from taskfile.deploy_utils import load_env_file, update_env_var

    console.print(Panel.fit(
        "[bold green]🔐 Environment Configuration[/]",
        border_style="green",
    ))

    env_path = Path(env_file)
    if not env_path.exists():
        env_path.touch()
    current = load_env_file(env_path)

    # Ports
    console.print("\n[bold]🌐 Ports:[/]")
    port_web = str(IntPrompt.ask(
        "  Web app port",
        default=int(current.get("PORT_WEB", "8000")),
    ))
    update_env_var("PORT_WEB", port_web, env_path)

    port_landing = str(IntPrompt.ask(
        "  Landing page port",
        default=int(current.get("PORT_LANDING", "3000")),
    ))
    update_env_var("PORT_LANDING", port_landing, env_path)

    # Project name
    console.print("\n[bold]📁 Project:[/]")
    project_name = Prompt.ask(
        "  Project name",
        default=current.get("PROJECT_NAME", Path.cwd().name),
    )
    update_env_var("PROJECT_NAME", project_name, env_path)

    # Version
    version = current.get("VERSION", "1.0.0")
    update_env_var("VERSION", version, env_path)

    console.print(f"\n[green]✅ Configuration saved to {env_file}[/]")
    console.print(f"  PORT_WEB={port_web}")
    console.print(f"  PORT_LANDING={port_landing}")
    console.print(f"  PROJECT_NAME={project_name}")
    console.print(f"  VERSION={version}")
    console.print("\n[dim]Next: taskfile setup hosts[/]")


@setup.command()
@click.option("--env-file", default=".env", help="Path to .env file (default: .env)")
def prod(env_file):
    """**Interactive production server setup** — SSH, podman, .env.

All-in-one interactive production setup:
1. Configure server hostname and SSH user
2. Test/setup SSH key authentication
3. Check/install podman on remote
4. Save configuration to .env

## Example

```bash
taskfile setup prod
```
"""
    from taskfile.deploy_utils import (
        load_env_file,
        update_env_var,
        test_ssh_connection,
        setup_ssh_key,
        check_remote_podman,
        install_remote_podman,
        check_remote_disk,
    )

    console.print(Panel.fit(
        "[bold green]🔧 Production Server Setup[/]",
        border_style="green",
    ))

    env_path = Path(env_file)
    if not env_path.exists():
        env_path.touch()
    current = load_env_file(env_path)

    # ─── Collect settings ───
    prod_host = Prompt.ask(
        "  Server hostname",
        default=current.get("PROD_HOST", ""),
    )
    if not prod_host:
        console.print("  [red]✗ Server hostname is required![/]")
        sys.exit(1)

    deploy_user = Prompt.ask(
        "  SSH user",
        default=current.get("DEPLOY_USER", "root"),
    )

    port_web = str(IntPrompt.ask(
        "  Web app port",
        default=int(current.get("PORT_WEB", "8000")),
    ))

    port_landing = str(IntPrompt.ask(
        "  Landing page port",
        default=int(current.get("PORT_LANDING", "3000")),
    ))

    # ─── Test SSH ───
    console.print(f"\n  🔍 Testing SSH to {deploy_user}@{prod_host}...")
    ssh_result = test_ssh_connection(prod_host, deploy_user)

    if ssh_result.success:
        console.print("  [green]✓ SSH key auth works![/]")
    else:
        console.print("  [yellow]⚠ SSH key auth failed. Setting up...[/]")
        if setup_ssh_key(prod_host, deploy_user):
            console.print("  [green]✓ SSH key auth now works![/]")
        else:
            console.print("  [red]✗ Could not set up SSH key.[/]")
            console.print(f"     Try manually: ssh-copy-id {deploy_user}@{prod_host}")

    # ─── Check podman ───
    console.print(f"\n  🔍 Checking podman on {prod_host}...")
    podman_ok, podman_ver = check_remote_podman(prod_host, deploy_user)

    if podman_ok:
        console.print(f"  [green]✓ Podman: {podman_ver}[/]")
    else:
        if Confirm.ask("  ⚠ Podman not found. Install it?", default=True):
            console.print(f"  Installing podman on {prod_host}...")
            if install_remote_podman(prod_host, deploy_user):
                console.print("  [green]✓ Podman installed[/]")
            else:
                console.print("  [red]✗ Installation failed[/]")
                console.print(f"     Try: ssh {deploy_user}@{prod_host} 'apt install -y podman'")

    # ─── Check disk ───
    disk = check_remote_disk(prod_host, deploy_user)
    console.print(f"  💾 Disk available: {disk}")

    # ─── Save to .env ───
    console.print("\n  💾 Saving configuration...")
    update_env_var("PROD_HOST", prod_host, env_path)
    update_env_var("DEPLOY_USER", deploy_user, env_path)
    update_env_var("PORT_WEB", port_web, env_path)
    update_env_var("PORT_LANDING", port_landing, env_path)

    console.print(f"\n[green]✅ Configuration saved to {env_file}[/]")
    console.print(f"  PROD_HOST={prod_host}")
    console.print(f"  DEPLOY_USER={deploy_user}")
    console.print(f"  PORT_WEB={port_web}")
    console.print(f"  PORT_LANDING={port_landing}")
    console.print("\n[dim]Next steps:[/]")
    console.print("  taskfile doctor              — verify everything")
    console.print("  taskfile run build           — build images")
    console.print("  taskfile --env prod deploy   — deploy to production")


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


@main.command()
@click.option("--level", type=click.Choice(["1", "2", "3"]), default=None,
              help="Clean level: 1=apps, 2=apps+venv, 3=full reset")
@click.option("--yes", "assume_yes", is_flag=True, help="Skip confirmation")
def clean(level, assume_yes):
    """**🧹 Clean project artifacts**.

Remove generated files and build artifacts.

## Clean levels

| Level | What is removed |
|-------|-----------------|
| 1 | Generated apps/ only |
| 2 | apps/ + .venv/ |
| 3 | Full reset (everything except README.md) |

## Examples

```bash
# Interactive choice
taskfile clean

# Direct level selection
taskfile clean --level 1

# No confirmation
taskfile clean --level 2 --yes
```
"""
    from taskfile.deploy_utils import clean_project

    if level is None:
        console.print("[bold]🧹 Clean project[/]\n")
        console.print("  1) Generated apps/ only")
        console.print("  2) apps/ + .venv/")
        console.print("  3) Full reset (everything except README.md)")
        level = Prompt.ask("\n  Choose level", choices=["1", "2", "3"], default="1")

    level_int = int(level)
    level_desc = {1: "apps/", 2: "apps/ + .venv/", 3: "full reset"}

    if not assume_yes:
        if not Confirm.ask(f"  Remove {level_desc[level_int]}?", default=False):
            console.print("[dim]Cancelled[/]")
            return

    removed = clean_project(level_int)
    if removed:
        for r in removed:
            console.print(f"  [red]✗[/] {r}")
        console.print(f"\n[green]✅ Cleaned ({len(removed)} items removed)[/]")
    else:
        console.print("[dim]Nothing to clean[/]")


@main.command()
@click.argument("images", nargs=-1)
@click.option("--host", default=None, help="Remote host (default: from PROD_HOST in .env)")
@click.option("--user", default=None, help="SSH user (default: from DEPLOY_USER in .env)")
@click.option("--runtime", default="podman", help="Remote container runtime (default: podman)")
def push(images, host, user, runtime):
    """**📦 Push Docker images to remote server** via SSH.

Transfer locally-built Docker images to a remote server using
`docker save | ssh podman load`. No registry needed.

## Examples

```bash
# Push specific images
taskfile push myapp-web:latest myapp-landing:latest

# Push to specific host
taskfile push --host prod.example.com myapp:latest

# Push with custom runtime
taskfile push --runtime docker myapp:latest
```
"""
    from taskfile.deploy_utils import (
        load_env_file,
        transfer_images_via_ssh,
    )

    env_vars = load_env_file(".env")
    target_host = host or env_vars.get("PROD_HOST")
    target_user = user or env_vars.get("DEPLOY_USER", "root")

    if not target_host:
        console.print("[red]✗ No host specified.[/]")
        console.print("  Use --host or set PROD_HOST in .env")
        console.print("  Run: taskfile setup prod")
        sys.exit(1)

    if not images:
        console.print("[yellow]⚠ No images specified.[/]")
        console.print("  Usage: taskfile push IMAGE [IMAGE...]")
        sys.exit(1)

    console.print(f"[bold]📦 Pushing {len(images)} image(s) → {target_host}[/]\n")

    success = transfer_images_via_ssh(
        images=list(images),
        host=target_host,
        user=target_user,
        remote_runtime=runtime,
    )

    if success:
        console.print(f"\n[green]✅ All images transferred to {target_host}[/]")
    else:
        console.print(f"\n[red]✗ Some transfers failed[/]")
        sys.exit(1)
