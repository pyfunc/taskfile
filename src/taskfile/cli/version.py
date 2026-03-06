"""Version management CLI commands for taskfile."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import clickmd as click
from taskfile.cli.click_compat import confirm
from rich.console import Console
from rich.panel import Panel

from taskfile import __version__
from taskfile.cli.main import main
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    find_taskfile,
    load_taskfile,
)

console = Console()


@main.group()
def version():
    """Version management commands.

    \b
    Examples:
        taskfile version bump     # Bump version (patch/minor/major)
        taskfile version show     # Show current version
        taskfile version set 1.0.0  # Set specific version
    """
    pass


@version.command()
@click.argument("part", default="patch", type=click.Choice(["patch", "minor", "major"]))
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def bump(ctx, part, dry_run, force):
    """Bump version number (patch, minor, or major).

    Updates VERSION file and optionally creates git tag.

    \b
    Examples:
        taskfile version bump        # Bump patch (0.1.0 -> 0.1.1)
        taskfile version bump minor  # Bump minor (0.1.0 -> 0.2.0)
        taskfile version bump major  # Bump major (0.1.0 -> 1.0.0)
        taskfile version bump --dry-run  # Preview changes
    """
    try:
        taskfile_path = find_taskfile(ctx.obj.get("taskfile_path") if ctx.obj else None)
    except TaskfileNotFoundError:
        console.print("[red]Error:[/] No Taskfile.yml found")
        sys.exit(1)

    project_dir = taskfile_path.parent

    # Read current version
    version_file = project_dir / "VERSION"
    if version_file.exists():
        current = version_file.read_text().strip()
    else:
        # Try to get from Taskfile or git
        current = _get_version_from_git(project_dir) or "0.0.0"

    # Calculate new version
    new_version = _increment_version(current, part)

    if not new_version:
        console.print(f"[red]Error:[/] Invalid version format: {current}")
        sys.exit(1)

    # Show plan
    console.print(Panel.fit(
        f"[bold]Version Bump[/]\n\n"
        f"[dim]Current:[/] {current}\n"
        f"[green]New:[/]     {new_version}\n"
        f"[dim]Part:[/]    {part}",
        border_style="blue"
    ))

    if dry_run:
        console.print("\n[yellow]DRY RUN — No changes made[/]")
        sys.exit(0)

    if not force and not confirm("\nProceed with version bump?"):
        console.print("[yellow]Cancelled[/]")
        sys.exit(0)

    # Update VERSION file
    version_file.write_text(new_version + "\n")
    console.print(f"✓ Updated VERSION: {current} → {new_version}")

    # Update Taskfile if it has version field
    _update_taskfile_version(project_dir / "Taskfile.yml", new_version)

    # Update pyproject.toml if exists
    _update_pyproject_version(project_dir / "pyproject.toml", new_version)

    # Git commit and tag
    if _has_git(project_dir):
        _git_commit_version(project_dir, new_version)
        console.print(f"✓ Created git tag: v{new_version}")

    console.print(f"\n[bold green]✅ Version bumped to {new_version}[/]")


@version.command()
@click.pass_context
def show(ctx):
    """Show current project version.

    \b
    Examples:
        taskfile version show     # Display current version
    """
    try:
        taskfile_path = find_taskfile(ctx.obj.get("taskfile_path") if ctx.obj else None)
    except TaskfileNotFoundError:
        console.print("[red]Error:[/] No Taskfile.yml found")
        sys.exit(1)

    project_dir = taskfile_path.parent

    # Try VERSION file first
    version_file = project_dir / "VERSION"
    if version_file.exists():
        version = version_file.read_text().strip()
        source = "VERSION file"
    else:
        version = _get_version_from_git(project_dir) or "unknown"
        source = "git tag"

    console.print(Panel.fit(
        f"[bold]{version}[/]\n[dim]Source: {source}[/]",
        title="Project Version",
        border_style="green"
    ))


@version.command()
@click.argument("new_version")
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def set(ctx, new_version, dry_run, force):
    """Set specific version number.

    \b
    Examples:
        taskfile version set 1.0.0      # Set to v1.0.0
        taskfile version set 2.1.0-rc1  # Set with prerelease
    """
    if not _is_valid_version(new_version):
        console.print(f"[red]Error:[/] Invalid version format: {new_version}")
        console.print("[dim]Expected: semver format (e.g., 1.0.0, 2.1.0-rc1)[/]")
        sys.exit(1)

    try:
        taskfile_path = find_taskfile(ctx.obj.get("taskfile_path") if ctx.obj else None)
    except TaskfileNotFoundError:
        console.print("[red]Error:[/] No Taskfile.yml found")
        sys.exit(1)

    project_dir = taskfile_path.parent

    # Read current version
    version_file = project_dir / "VERSION"
    current = version_file.read_text().strip() if version_file.exists() else "none"

    # Show plan
    console.print(Panel.fit(
        f"[bold]Set Version[/]\n\n"
        f"[dim]Current:[/] {current}\n"
        f"[green]New:[/]     {new_version}",
        border_style="blue"
    ))

    if dry_run:
        console.print("\n[yellow]DRY RUN — No changes made[/]")
        sys.exit(0)

    if not force and not confirm("\nProceed?"):
        console.print("[yellow]Cancelled[/]")
        sys.exit(0)

    # Update files
    version_file.write_text(new_version + "\n")
    _update_taskfile_version(project_dir / "Taskfile.yml", new_version)
    _update_pyproject_version(project_dir / "pyproject.toml", new_version)

    console.print(f"\n[bold green]✅ Version set to {new_version}[/]")


# Helper functions

def _increment_version(version: str, part: str) -> str | None:
    """Increment version number."""
    # Parse semver
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", version)
    if not match:
        return None

    major, minor, patch, prerelease = match.groups()
    major, minor, patch = int(major), int(minor), int(patch)

    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def _is_valid_version(version: str) -> bool:
    """Check if version string is valid semver."""
    return bool(re.match(r"^\d+\.\d+\.\d+(?:-[\w.]+)?$", version))


def _get_version_from_git(project_dir: Path) -> str | None:
    """Get version from latest git tag."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            return tag.lstrip("v")  # Remove 'v' prefix if present
    except Exception:
        pass
    return None


def _has_git(project_dir: Path) -> bool:
    """Check if project uses git."""
    return (project_dir / ".git").exists()


def _git_commit_version(project_dir: Path, version: str):
    """Commit version changes and create tag."""
    try:
        subprocess.run(
            ["git", "add", "VERSION", "Taskfile.yml", "pyproject.toml"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"chore: bump version to {version}"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "tag", f"v{version}"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]Warning:[/] Git operation failed: {e}")


def _update_taskfile_version(taskfile_path: Path, version: str):
    """Update version in Taskfile.yml if it exists."""
    if not taskfile_path.exists():
        return

    content = taskfile_path.read_text()
    # Look for version field at top level
    if re.search(r"^version:\s*['\"]?([\d.]+)['\"]?", content, re.M):
        new_content = re.sub(
            r"^(version:\s*['\"]?)([\d.]+)(['\"]?)",
            rf"\g<1>{version}\g<3>",
            content,
            flags=re.M,
        )
        taskfile_path.write_text(new_content)
        console.print(f"✓ Updated Taskfile.yml")


def _update_pyproject_version(pyproject_path: Path, version: str):
    """Update version in pyproject.toml if it exists."""
    if not pyproject_path.exists():
        return

    content = pyproject_path.read_text()
    # Update version = "x.y.z" in [project] section
    if 'version = ' in content:
        new_content = re.sub(
            r'^(version\s*=\s*["\'])([\d.]+)(["\'])',
            rf'\g<1>{version}\g<3>',
            content,
            flags=re.M,
        )
        pyproject_path.write_text(new_content)
        console.print(f"✓ Updated pyproject.toml")
