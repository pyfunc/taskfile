"""## Release command for taskfile

Full deployment cycle orchestration: **tag → build → deploy → health check**

### Overview

This module provides comprehensive release management for multi-platform applications.
It coordinates the entire deployment pipeline from version bumping through health checks.

### Release Pipeline

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  TAG    │ -> │  BUILD  │ -> │ DEPLOY  │ -> │ HEALTH  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

### Supported Platforms

| Platform | Description | Build Tool |
|----------|-------------|------------|
| `desktop` | Desktop applications | PyInstaller/Build |
| `web` | Web applications | Docker/Podman |
| `mobile` | Mobile apps | Native tooling |

### Commands

- `release` - Full release pipeline
- `rollback` - Rollback to previous version

### Dependencies

- `clickmd` - CLI framework with markdown support
- `rich` - Rich console output
- `taskfile.health` - Health check integration
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import clickmd as click
from taskfile.cli.click_compat import confirm
from rich.console import Console
from rich.panel import Panel

from taskfile.cli.main import console, main
from taskfile.health import health_check_all
from taskfile.landing import build_landing_page
from taskfile.parser import TaskfileNotFoundError, TaskfileParseError, load_taskfile

if TYPE_CHECKING:
    pass


def _run_command(cmd: list[str] | str, description: str, dry_run: bool = False) -> bool:
    """Run a shell command with error handling."""
    console.print(f"\n[bold]{description}...[/]")

    if dry_run:
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        console.print(f"  [dim]→ {cmd_str} (dry run)[/]")
        return True

    try:
        if isinstance(cmd, list):
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            console.print("  [green]✓ Success[/]")
            return True
        else:
            console.print(f"  [red]✗ Failed (exit {result.returncode})[/]")
            if result.stderr:
                console.print(f"  [dim]{result.stderr[:200]}[/]")
            return False
    except subprocess.TimeoutExpired:
        console.print("  [red]✗ Timeout[/]")
        return False
    except Exception as e:
        console.print(f"  [red]✗ Error: {e}[/]")
        return False


def _get_current_tag() -> str | None:
    """Get current git tag or None."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def _get_previous_tag() -> str | None:
    """Get previous git tag for rollback."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "HEAD~1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def _resolve_release_config(ctx, tag_version):
    """Load config, resolve app_name, tag, domain, ssh_host."""
    try:
        config = load_taskfile(ctx.obj.get("taskfile_path"))
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    app_name = config.name or "app"
    current_tag = tag_version or _get_current_tag()

    if not current_tag:
        console.print("[red]Error:[/] No tag specified and not on a tagged commit.")
        console.print("       Use --tag v1.0.0 or checkout a tagged commit.")
        sys.exit(1)

    domain = None
    ssh_host = None
    if "prod" in config.environments:
        env = config.environments["prod"]
        domain = env.variables.get("DOMAIN")
        ssh_host = env.ssh_host

    if not domain:
        console.print("[yellow]Warning:[/] No DOMAIN set in prod environment")
        domain = "example.com"

    return config, app_name, current_tag, domain, ssh_host


def _resolve_domain(config, domain_override: str | None = None) -> tuple[str, str | None]:
    """Resolve domain and ssh_host from config or override. Exits on failure."""
    domain = domain_override
    ssh_host = None
    if not domain and "prod" in config.environments:
        env = config.environments["prod"]
        domain = env.variables.get("DOMAIN")
        ssh_host = env.ssh_host
    if not domain:
        console.print("[red]Error:[/] No domain specified. Use --domain or set DOMAIN in .env.prod")
        sys.exit(1)
    return domain, ssh_host


def _show_release_plan(app_name, current_tag, domain, skip_desktop, skip_landing, skip_health):
    """Display the release plan panel."""
    console.print(Panel.fit(
        f"[bold green]Release Plan: {app_name} {current_tag}[/]\n"
        f"[dim]Domain:[/] {domain}\n"
        f"[dim]Steps:[/]\n"
        f"  {'[dim]' if skip_desktop else '[green]'}1.{'[/]'} Build desktop\n"
        f"  {'[dim]' if False else '[green]'}2.{'[/]'} Deploy web (SaaS)\n"
        f"  {'[dim]' if skip_desktop else '[green]'}3.{'[/]'} Upload releases\n"
        f"  {'[dim]' if skip_landing else '[green]'}4.{'[/]'} Deploy landing\n"
        f"  {'[dim]' if skip_health else '[green]'}5.{'[/]'} Health check",
        border_style="green"
    ))


def _confirm_release(dry_run, force):
    """Handle dry-run notice or user confirmation. Exits if cancelled."""
    if dry_run:
        console.print("[yellow]DRY RUN — No changes will be made[/]\n")
    elif not force:
        if not confirm("\nProceed with release?"):
            console.print("[yellow]Release cancelled[/]")
            sys.exit(0)


def _step_build_desktop(dry_run_flag, dry_run):
    """Step 1: Build desktop applications."""
    return _run_command(
        ["taskfile", "--platform", "desktop", "run", "build-desktop"] + dry_run_flag,
        "Step 1/5: Building desktop applications",
        dry_run,
    )


def _step_deploy_web(dry_run_flag, dry_run):
    """Step 2: Deploy web application."""
    return _run_command(
        ["taskfile", "--env", "prod", "--platform", "web", "deploy"] + dry_run_flag,
        "Step 2/5: Deploying web application",
        dry_run,
    )


def _step_upload_releases(current_tag, dry_run_flag, dry_run):
    """Step 3: Upload desktop releases if they exist."""
    if dry_run:
        return True
    release_dir = Path(f"dist/releases/{current_tag}")
    if release_dir.exists():
        return _run_command(
            ["taskfile", "--env", "prod", "run", "upload-releases"] + dry_run_flag,
            "Step 3/5: Uploading desktop releases",
            dry_run,
        )
    console.print(f"\n[yellow]Step 3/5: No releases found at {release_dir}, skipping upload[/]")
    return True


def _step_deploy_landing(app_name, current_tag, domain, dry_run_flag, dry_run):
    """Step 4: Build and deploy landing page."""
    console.print("\n[bold]Step 4/5: Building landing page...[/]")

    if dry_run:
        console.print("  [dim]→ Would generate landing page (dry run)[/]")
        return True

    try:
        build_landing_page(
            output_dir="dist/landing",
            app_name=app_name,
            tag=current_tag,
            domain=domain,
        )
        console.print("  [green]✓ Landing page generated[/]")

        return _run_command(
            ["taskfile", "--env", "prod", "--platform", "landing", "deploy"] + dry_run_flag,
            "Deploying landing page",
            dry_run,
        )
    except Exception as e:
        console.print(f"  [red]✗ Landing page failed: {e}[/]")
        return False


def _step_health_check(domain, ssh_host):
    """Step 5: Run health checks."""
    console.print("\n[bold]Step 5/5: Health check...[/]")
    return health_check_all(
        domain=domain,
        ssh_host=ssh_host,
        exit_on_error=False,
    )


def _print_release_summary(success, current_tag, domain):
    """Print final release success/failure panel and exit."""
    if success:
        console.print(Panel.fit(
            f"[bold green]✅ Release {current_tag} complete![/]\n\n"
            f"[dim]Web app:[/]    https://app.{domain}\n"
            f"[dim]Landing:[/]    https://{domain}\n"
            f"[dim]Downloads:[/]  https://{domain}/releases/{current_tag}/",
            border_style="green"
        ))
        sys.exit(0)
    else:
        console.print(Panel.fit(
            f"[bold red]⚠️ Release {current_tag} completed with errors[/]\n\n"
            f"Check the output above for details.\n"
            f"You may need to run individual steps manually.",
            border_style="red"
        ))
        sys.exit(1)


@main.command()
@click.option("--tag", "tag_version", help="Version tag to release (e.g., v1.0.0)")
@click.option("--skip-desktop", is_flag=True, help="Skip desktop build")
@click.option("--skip-landing", is_flag=True, help="Skip landing page deploy")
@click.option("--skip-health", is_flag=True, help="Skip health check")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("--force", is_flag=True, help="Force release even if checks fail")
@click.pass_context
def release(ctx, tag_version, skip_desktop, skip_landing, skip_health, dry_run, force):
    """Full release — build all, deploy all, update landing.

    Orchestrates the complete release pipeline:
    1. Create git tag (if specified)
    2. Build desktop applications
    3. Build and deploy web (SaaS)
    4. Upload desktop binaries
    5. Build and deploy landing page
    6. Run health checks

    \b
    Examples:
        taskfile release --tag v1.0.0
        taskfile release --skip-desktop --dry-run
        taskfile release --force  # Skip confirmation prompts
    """
    config, app_name, current_tag, domain, ssh_host = _resolve_release_config(ctx, tag_version)

    _show_release_plan(app_name, current_tag, domain, skip_desktop, skip_landing, skip_health)
    _confirm_release(dry_run, force)

    dry_run_flag = ["--dry-run"] if dry_run else []
    success = True

    if not skip_desktop:
        success = _step_build_desktop(dry_run_flag, dry_run) and success

    success = _step_deploy_web(dry_run_flag, dry_run) and success

    if not skip_desktop:
        success = _step_upload_releases(current_tag, dry_run_flag, dry_run) and success

    if not skip_landing:
        success = _step_deploy_landing(app_name, current_tag, domain, dry_run_flag, dry_run) and success

    if not skip_health and not dry_run:
        success = _step_health_check(domain, ssh_host) and success

    _print_release_summary(success, current_tag, domain)


@main.command()
@click.option("--to", "target_tag", help="Target tag for rollback (default: previous tag)")
@click.option("--domain", help="Domain name (overrides Taskfile config)")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.pass_context
def rollback(ctx, target_tag, domain, dry_run):
    """Rollback to previous version.

    Deploys the previous (or specified) version of the web application.

    \b
    Examples:
        taskfile rollback              # Rollback to previous tag
        taskfile rollback --to v1.0.0  # Rollback to specific version
        taskfile rollback --dry-run    # Preview changes
    """
    try:
        config = load_taskfile(ctx.obj.get("taskfile_path"))
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    # Determine target tag
    rollback_tag = target_tag or _get_previous_tag()
    if not rollback_tag:
        console.print("[red]Error:[/] No previous tag found for rollback")
        sys.exit(1)

    check_domain, ssh_host = _resolve_domain(config, domain)

    console.print(Panel.fit(
        f"[bold yellow]⚠️ Rollback to {rollback_tag}[/]\n"
        f"[dim]Domain:[/] {check_domain}\n"
        f"[dim]This will:[/] Deploy previous version of web app",
        border_style="yellow"
    ))

    if dry_run:
        console.print("\n[yellow]DRY RUN — No changes will be made[/]")
        console.print(f"  [dim]→ Would deploy web app with TAG={rollback_tag}[/]")
        sys.exit(0)

    if not confirm("\nProceed with rollback?"):
        console.print("[yellow]Rollback cancelled[/]")
        sys.exit(0)

    # Deploy with previous tag
    success = _run_command(
        ["taskfile", "--env", "prod", "--platform", "web", "deploy", "--var", f"TAG={rollback_tag}"],
        f"Rolling back to {rollback_tag}",
    )

    if success:
        # Run health check
        health_ok = health_check_all(
            domain=check_domain,
            ssh_host=ssh_host,
            exit_on_error=False,
        )

        if health_ok:
            console.print(f"\n[bold green]✅ Rolled back to {rollback_tag}[/]")
            sys.exit(0)
        else:
            console.print(f"\n[bold yellow]⚠️ Rolled back to {rollback_tag} but health check failed[/]")
            sys.exit(1)
    else:
        console.print(f"\n[bold red]✗ Rollback to {rollback_tag} failed[/]")
        sys.exit(1)
