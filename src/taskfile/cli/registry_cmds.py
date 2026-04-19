"""CLI commands for task registry - install, search, manage packages."""

from __future__ import annotations

import sys
from pathlib import Path

import clickmd as click
from rich.table import Table
from rich import box

from taskfile.cli.main import main, console
from taskfile.registry import RegistryClient


@main.group()
def pkg():
    """📦 Package management - install tasks from registry.

    Install and manage task packages from remote sources like npm.
    Share and reuse tasks across projects.

    \b
    Examples:
        taskfile pkg search docker      # Search for docker-related tasks
        taskfile pkg install tom-sapletta/web-tasks  # Install from GitHub
        taskfile pkg list               # List installed packages
        taskfile pkg uninstall web-tasks  # Remove package
    """
    pass


@pkg.command(name="search")
@click.argument("query")
@click.option("--limit", "-n", default=20, help="Maximum number of results")
@click.option("--registry", "-r", default=None, help="Registry URL")
def pkg_search(query, limit, registry):
    """Search for packages in the registry.

    Searches GitHub repositories with 'taskfile' topic.
    """
    client = RegistryClient(registry)

    try:
        console.print(f"[dim]Searching for '{query}'...[/]")
        packages = client.search(query, limit)

        if not packages:
            console.print(f"[yellow]No packages found for '{query}'[/]")
            return

        # Display results
        table = Table(title=f"Search results for '{query}'", box=box.ROUNDED)
        table.add_column("Package", style="green", no_wrap=True)
        table.add_column("Description", style="dim")
        table.add_column("Author", style="cyan")

        for pkg in packages:
            table.add_row(
                pkg.name,
                pkg.description[:60] + "..." if len(pkg.description) > 60 else pkg.description,
                pkg.author,
            )

        console.print(table)
        console.print("\n[dim]To install:[/]")
        console.print(f"  taskfile pkg install {packages[0].name}")

    except Exception as e:
        console.print(f"[red]Search failed: {e}[/]")
        sys.exit(1)


@pkg.command(name="install")
@click.argument("package_name")
@click.option("--version", "-v", default=None, help="Specific version to install")
@click.option("--save", "-S", is_flag=True, default=True, help="Save to taskfile.json")
@click.option("--no-save", is_flag=True, help="Don't save to taskfile.json")
@click.option("--registry", "-r", default=None, help="Registry URL")
def pkg_install(package_name, version, save, no_save, registry):
    """Install a package from the registry.

    Package names can be:
        - GitHub repo: user/repo or github:user/repo
        - Direct URL: https://example.com/tasks.yml

    \b
    Examples:
        taskfile pkg install tom-sapletta/web-tasks
        taskfile pkg install github:docker/build-tasks -v v1.2.0
        taskfile pkg install https://example.com/deploy.yml --no-save
    """
    client = RegistryClient(registry)

    try:
        console.print(f"[dim]Installing {package_name}...[/]")

        pkg_dir = client.install(
            package_name,
            version=version,
            save=save and not no_save,
        )

        console.print(f"[green]✓ Installed {package_name}[/]")
        console.print(f"[dim]  Location: {pkg_dir}[/]")

        # Check for installed tasks
        taskfile_path = pkg_dir / "Taskfile.yml"
        if taskfile_path.exists():
            try:
                import yaml

                with open(taskfile_path) as f:
                    config = yaml.safe_load(f)

                tasks = list(config.get("tasks", {}).keys())
                if tasks:
                    console.print("\n[dim]Available tasks:[/]")
                    for task in tasks[:5]:
                        console.print(f"  - {task}")
                    if len(tasks) > 5:
                        console.print(f"  ... and {len(tasks) - 5} more")

                    console.print("\n[dim]To run:[/]")
                    console.print(f"  taskfile run {tasks[0]}")

            except Exception:
                pass

    except Exception as e:
        console.print(f"[red]Installation failed: {e}[/]")
        sys.exit(1)


@pkg.command(name="list")
@click.option("--all", "-a", is_flag=True, help="Show all packages including cached")
def pkg_list(all):
    """List installed packages."""
    client = RegistryClient()

    try:
        installed = client.list_installed()

        if not installed:
            console.print("[yellow]No packages installed[/]")
            console.print("\n[dim]To install a package:[/]")
            console.print("  taskfile pkg search <query>")
            console.print("  taskfile pkg install <package>")
            return

        table = Table(title="Installed packages", box=box.ROUNDED)
        table.add_column("Package", style="green")
        table.add_column("Location", style="dim")

        for name, path in installed:
            table.add_row(name, str(path))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to list packages: {e}[/]")
        sys.exit(1)


@pkg.command(name="uninstall")
@click.argument("package_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def pkg_uninstall(package_name, yes):
    """Uninstall a package.

    \b
    Example:
        taskfile pkg uninstall web-tasks
    """
    client = RegistryClient()

    if not yes:
        from rich.console import Console

        console = Console()
        response = console.input(f"Uninstall {package_name}? [y/N] ")
        if response.lower() not in ("y", "yes"):
            console.print("[dim]Cancelled[/]")
            return

    try:
        success = client.uninstall(package_name)

        if success:
            console.print(f"[green]✓ Uninstalled {package_name}[/]")
        else:
            console.print(f"[yellow]Package {package_name} not found[/]")

    except Exception as e:
        console.print(f"[red]Uninstall failed: {e}[/]")
        sys.exit(1)


@pkg.command(name="info")
@click.argument("package_name")
def pkg_info(package_name):
    """Show information about a package.

    \b
    Example:
        taskfile pkg info tom-sapletta/web-tasks
    """
    RegistryClient()

    # Check if installed
    pkg_dir = Path.home() / ".taskfile" / "registry" / "packages" / package_name.replace("/", "-")

    if pkg_dir.exists():
        console.print(f"[bold]{package_name}[/]")
        console.print(f"[dim]Installed at: {pkg_dir}[/]")

        # Try to read package info
        info_file = pkg_dir / "package.json"
        if info_file.exists():
            import json

            info = json.loads(info_file.read_text())

            if "description" in info:
                console.print(f"\n{info['description']}")
            if "version" in info:
                console.print(f"\n[dim]Version: {info['version']}[/]")
            if "tasks" in info:
                console.print(f"\n[dim]Tasks: {', '.join(info['tasks'].keys())}[/]")
    else:
        console.print(f"[yellow]Package {package_name} not installed[/]")
        console.print("\n[dim]To install:[/]")
        console.print(f"  taskfile pkg install {package_name}")
