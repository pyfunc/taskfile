"""Interactive commands for taskfile — doctor, init with choices, env detection."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.table import Table
from rich import box

from taskfile.cli.main import console, main
from taskfile.parser import load_taskfile, find_taskfile

if TYPE_CHECKING:
    pass


class ProjectDiagnostics:
    """Diagnose and auto-fix common project issues."""

    def __init__(self):
        self.issues: list[tuple[str, str, bool]] = []  # (issue, severity, auto_fixable)
        self.fixed = 0

    def check_taskfile(self) -> bool:
        """Check if Taskfile.yml exists and is valid."""
        path = find_taskfile()
        if not path:
            self.issues.append(("Taskfile.yml not found", "error", True))
            return False
        try:
            load_taskfile(path)
            return True
        except Exception as e:
            self.issues.append((f"Taskfile.yml parse error: {e}", "error", False))
            return False

    def check_env_files(self) -> None:
        """Check environment files."""
        for env_file in [".env", ".env.local", ".env.prod"]:
            if Path(env_file).exists():
                content = Path(env_file).read_text()
                if "OPENROUTER_API_KEY=" in content and "OPENROUTER_API_KEY=\n" in content:
                    self.issues.append((f"{env_file}: OPENROUTER_API_KEY is empty", "warning", True))

    def check_docker(self) -> None:
        """Check if Docker is available."""
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.issues.append(("Docker not installed or not running", "warning", False))

    def check_ssh_keys(self) -> None:
        """Check SSH keys."""
        ssh_dir = Path.home() / ".ssh"
        if not ssh_dir.exists():
            self.issues.append(("~/.ssh directory not found", "error", True))
            return

        keys = list(ssh_dir.glob("id_*"))
        if not keys:
            self.issues.append(("No SSH keys found (~/.ssh/id_*)", "warning", False))

    def check_git(self) -> None:
        """Check if in git repo."""
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.issues.append(("Not a git repository", "info", True))

    def auto_fix(self) -> int:
        """Attempt to fix auto-fixable issues."""
        fixed = 0
        for issue, severity, auto_fixable in self.issues[:]:
            if not auto_fixable:
                continue

            if issue == "Taskfile.yml not found":
                if Confirm.ask("Create Taskfile.yml?", default=True):
                    from taskfile.scaffold import generate_taskfile
                    Path("Taskfile.yml").write_text(generate_taskfile("minimal"))
                    console.print("[green]✓ Created Taskfile.yml[/]")
                    fixed += 1
                    self.issues.remove((issue, severity, auto_fixable))

            elif issue == "Not a git repository":
                if Confirm.ask("Initialize git repository?", default=False):
                    subprocess.run(["git", "init"], capture_output=True)
                    console.print("[green]✓ Initialized git repository[/]")
                    fixed += 1
                    self.issues.remove((issue, severity, auto_fixable))

            elif ".env: OPENROUTER_API_KEY is empty" in issue:
                console.print("[yellow]⚠[/] Set OPENROUTER_API_KEY:")
                console.print("  1. Get key from https://openrouter.ai/settings/keys")
                console.print("  2. Add to .env: OPENROUTER_API_KEY=sk-or-v1-...")

        return fixed

    def print_report(self) -> None:
        """Print diagnostic report."""
        if not self.issues:
            console.print(Panel(
                "[bold green]✓ All checks passed![/]\n"
                "Your project is ready to use.",
                border_style="green"
            ))
            return

        table = Table(title="Project Diagnostics", box=box.ROUNDED)
        table.add_column("Issue", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Auto-fix", style="cyan")

        for issue, severity, auto_fixable in self.issues:
            severity_style = {"error": "[red]●[/]", "warning": "[yellow]●[/]", "info": "[blue]ℹ[/]"}.get(severity, "●")
            fix_status = "[green]Yes[/]" if auto_fixable else "[dim]No[/]"
            table.add_row(issue, f"{severity_style} {severity}", fix_status)

        console.print(table)


def _detect_project_type() -> str:
    """Detect project type from files in directory."""
    if Path("pyproject.toml").exists() or Path("setup.py").exists():
        return "python"
    if Path("package.json").exists():
        return "nodejs"
    if Path("Cargo.toml").exists():
        return "rust"
    if Path("go.mod").exists():
        return "go"
    if Path("composer.json").exists():
        return "php"
    return "generic"


def _suggest_template(project_type: str) -> str:
    """Suggest template based on project type."""
    suggestions = {
        "python": "full",
        "nodejs": "web",
        "rust": "minimal",
        "go": "minimal",
        "php": "web",
        "generic": "minimal",
    }
    return suggestions.get(project_type, "minimal")


def _collect_env_config_interactive() -> dict[str, str]:
    """Collect environment configuration interactively."""
    config = {}

    console.print(Panel.fit(
        "[bold green]Environment Configuration[/]\n[dim]Press Enter to skip or use defaults[/]",
        border_style="green"
    ))

    # Detect defaults from environment
    default_domain = os.environ.get("DOMAIN", "localhost")
    default_port = os.environ.get("PORT", "8000")

    config["DOMAIN"] = Prompt.ask("Domain", default=default_domain)
    config["PORT"] = str(IntPrompt.ask("Port", default=int(default_port)))

    # API Keys
    if Confirm.ask("Configure OpenRouter?", default=False):
        api_key = Prompt.ask("OPENROUTER_API_KEY", default=os.environ.get("OPENROUTER_API_KEY", ""))
        config["OPENROUTER_API_KEY"] = api_key

    # Deployment hosts
    if Confirm.ask("Configure deployment hosts?", default=False):
        console.print("\n[dim]Staging environment:[/]")
        config["STAGING_HOST"] = Prompt.ask("  Staging host", default="staging.example.com")
        config["STAGING_USER"] = Prompt.ask("  Staging user", default="deploy")

        console.print("\n[dim]Production environment:[/]")
        config["PROD_HOST"] = Prompt.ask("  Production host", default="prod.example.com")
        config["PROD_USER"] = Prompt.ask("  Production user", default="deploy")

    return config


def _write_env_file(config: dict[str, str], env_name: str = "local") -> None:
    """Write environment file."""
    filename = f".env.{env_name}" if env_name != "local" else ".env"
    filepath = Path(filename)

    lines = [f"# Auto-generated by taskfile init\n"]
    for key, value in sorted(config.items()):
        lines.append(f"{key}={value}")

    content = "\n".join(lines) + "\n"

    if filepath.exists():
        if not Confirm.ask(f"{filename} exists. Overwrite?", default=False):
            console.print(f"[yellow]Skipping {filename}[/]")
            return

    filepath.write_text(content)
    console.print(f"[green]✓ Created {filename}[/]")


def _collect_init_choices() -> dict[str, any]:
    """Collect all init choices from user."""
    choices = {}

    # Project type detection
    project_type = _detect_project_type()
    suggested_template = _suggest_template(project_type)

    console.print(Panel.fit(
        f"[bold green]Taskfile Project Init[/]\n"
        f"[dim]Detected project type: {project_type}[/]",
        border_style="green"
    ))

    # Template selection with preview
    templates = {
        "minimal": "Basic build/deploy tasks",
        "web": "Web app with Docker + Traefik",
        "podman": "Podman Quadlet (low RAM)",
        "full": "All features, multi-env",
        "multiplatform": "Desktop+Web × Local+Prod",
        "publish": "Multi-registry publish",
        "kubernetes": "K8s + Helm multi-cluster",
        "terraform": "Terraform IaC multi-env",
        "iot": "IoT fleet with strategies",
    }

    console.print("\n[bold]Available templates:[/]")
    for key, desc in templates.items():
        marker = " [green]← suggested[/]" if key == suggested_template else ""
        console.print(f"  [cyan]{key:12}[/] — {desc}{marker}")

    choices["template"] = Prompt.ask(
        "\nSelect template",
        default=suggested_template,
        choices=list(templates.keys())
    )

    # Environment configuration
    if Confirm.ask("\nConfigure environment variables?", default=True):
        choices["env_config"] = _collect_env_config_interactive()
    else:
        choices["env_config"] = {}

    # Additional options
    choices["create_gitignore"] = Confirm.ask(
        "Create .gitignore?",
        default=not Path(".gitignore").exists()
    )

    choices["init_git"] = Confirm.ask(
        "Initialize git repository?",
        default=not Path(".git").exists()
    )

    return choices


def _create_gitignore() -> None:
    """Create sensible .gitignore."""
    content = """# Environment files
.env
.env.local
.env.prod
.env.staging

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
.pytest_cache/

# Node
node_modules/
dist/
build/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db
"""
    Path(".gitignore").write_text(content)
    console.print("[green]✓ Created .gitignore[/]")


@main.command()
@click.option("--fix", is_flag=True, help="Auto-fix issues where possible")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def doctor(fix, verbose):
    """🔧 Diagnose project and suggest fixes.

    Checks:
        - Taskfile.yml existence and validity
        - Environment files configuration
        - Docker availability
        - SSH keys setup
        - Git repository status

    \b
    Examples:
        taskfile doctor           # Run diagnostics
        taskfile doctor --fix     # Auto-fix issues
        taskfile doctor -v        # Verbose output
    """
    diagnostics = ProjectDiagnostics()

    console.print(Panel.fit(
        "[bold blue]🔧 Taskfile Doctor[/]\n[dim]Running diagnostics...[/]",
        border_style="blue"
    ))

    with console.status("[bold green]Checking project...[/]"):
        diagnostics.check_taskfile()
        diagnostics.check_env_files()
        diagnostics.check_docker()
        diagnostics.check_ssh_keys()
        diagnostics.check_git()

    diagnostics.print_report()

    if fix and diagnostics.issues:
        console.print("\n[bold]Attempting auto-fix...[/]")
        fixed = diagnostics.auto_fix()
        if fixed > 0:
            console.print(f"[green]✓ Fixed {fixed} issue(s)[/]")

    # Summary
    if not diagnostics.issues:
        console.print("\n[bold green]Your project is ready! 🚀[/]")
        console.print("\n[dim]Next steps:[/]")
        console.print("  taskfile list       — See available tasks")
        console.print("  taskfile run build  — Build your project")
    else:
        error_count = sum(1 for _, s, _ in diagnostics.issues if s == "error")
        if error_count > 0:
            console.print(f"\n[red]Found {error_count} error(s) that need attention[/]")
            sys.exit(1)


@main.command()
@click.option("--template", type=click.Choice([
    "minimal", "web", "podman", "codereview", "full",
    "multiplatform", "publish", "kubernetes", "terraform", "iot"
]), default=None, help="Project template")
@click.option("--force", is_flag=True, help="Overwrite existing files")
@click.option("--interactive", "-i", is_flag=True, help="Interactive setup with prompts")
def init(template, force, interactive):
    """✨ Create a new Taskfile.yml with interactive setup.

    Without --interactive: uses template argument or minimal
    With --interactive: prompts for all configuration options

    \b
    Examples:
        taskfile init                           # Minimal template
        taskfile init --template web            # Web app template
        taskfile init -i                        # Full interactive setup
        taskfile init -i --force                # Overwrite existing
    """
    outpath = Path("Taskfile.yml")

    if outpath.exists() and not force:
        console.print(f"[yellow]{outpath} already exists. Use --force to overwrite.[/]")
        if not Confirm.ask("Continue anyway?", default=False):
            sys.exit(1)

    # Interactive mode
    if interactive or template is None:
        choices = _collect_init_choices()
        template = choices["template"]
    else:
        choices = {"env_config": {}, "create_gitignore": False, "init_git": False}

    # Generate Taskfile
    from taskfile.scaffold import generate_taskfile
    content = generate_taskfile(template)
    outpath.write_text(content)
    console.print(f"[green]✓ Created Taskfile.yml (template: {template})[/]")

    # Write environment files
    if choices.get("env_config"):
        _write_env_file(choices["env_config"], "local")
        if any(k.startswith("STAGING_") for k in choices["env_config"]):
            staging_config = {k: v for k, v in choices["env_config"].items() if "STAGING" in k or "PROD" in k}
            if staging_config:
                _write_env_file(staging_config, "prod")

    # Create .gitignore
    if choices.get("create_gitignore"):
        _create_gitignore()

    # Init git
    if choices.get("init_git"):
        try:
            subprocess.run(["git", "init"], capture_output=True, check=True)
            console.print("[green]✓ Initialized git repository[/]")
        except Exception as e:
            console.print(f"[yellow]⚠ Git init failed: {e}[/]")

    # Summary
    console.print("\n[bold green]✨ Project initialized! 🚀[/]")
    console.print("\n[dim]Next steps:[/]")
    console.print("  taskfile doctor     — Check setup")
    console.print("  taskfile list       — See available tasks")
    console.print("  taskfile run build  — Build your project")


@main.group()
def setup():
    """🛠️  Setup project - hosts, env, dependencies.

    Quick setup commands for common configuration tasks.

    \b
    Examples:
        taskfile setup hosts    # Configure deployment hosts
        taskfile setup env      # Configure environment variables
    """
    pass


@setup.command()
@click.pass_context
def hosts(ctx):
    """Configure deployment hosts (staging/prod) interactively.

    Runs the setup-hosts task from Taskfile.yml with interactive prompts.

    \b
    Example:
        taskfile setup hosts
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
    """Configure environment variables (.env) interactively.

    Runs the setup-env task from Taskfile.yml with interactive prompts
    for LLM provider selection, API keys, ports, etc.

    \b
    Example:
        taskfile setup env
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
            console.print("[dim]  Add setup-env task or use: taskfile run setup-hosts[/]")
            sys.exit(1)

        success = runner.run(["setup-env"])
        sys.exit(0 if success else 1)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        from taskfile.cli.main import _print_nearby_taskfiles
        if isinstance(e, TaskfileNotFoundError):
            _print_nearby_taskfiles(e.nearby)
        sys.exit(1)
