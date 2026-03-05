"""Interactive commands for taskfile — doctor, init with choices, env detection."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.table import Table
from rich import box

from taskfile.cli.main import console, main
from taskfile.compose import load_env_file, resolve_variables
from taskfile.parser import load_taskfile, find_taskfile, TaskfileNotFoundError, TaskfileParseError

if TYPE_CHECKING:
    pass


class ProjectDiagnostics:
    """Diagnose and auto-fix common project issues."""

    def __init__(self):
        self.issues: list[tuple[str, str, bool]] = []  # (issue, severity, auto_fixable)
        self.fixed = 0
        self.port_fixes: dict[str, int] = {}

    def check_taskfile(self) -> bool:
        """Check if Taskfile.yml exists and is valid."""
        try:
            path = find_taskfile()
        except TaskfileNotFoundError:
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

    def check_ports(self) -> None:
        """Check docker-compose port conflicts and suggest .env fixes."""
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            return

        try:
            compose = yaml.safe_load(compose_path.read_text()) or {}
        except Exception:
            return

        services = (compose or {}).get("services") or {}
        if not isinstance(services, dict):
            return

        env_path = Path(".env")
        env_vars = load_env_file(env_path) if env_path.exists() else {}
        ctx = {**os.environ, **env_vars}

        for svc_name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            ports = svc.get("ports") or []
            if not isinstance(ports, list):
                continue

            for port_entry in ports:
                if not isinstance(port_entry, str):
                    continue
                host_port, var_name = _parse_compose_host_port(port_entry)
                if host_port is None:
                    continue

                expanded = resolve_variables(str(host_port), ctx)
                try:
                    resolved_host_port = int(expanded)
                except ValueError:
                    continue

                if _is_port_free(resolved_host_port):
                    continue

                suggested = _find_free_port_near(resolved_host_port)
                if suggested is None:
                    continue

                key = var_name or f"PORT_{svc_name.upper()}"
                self.port_fixes[key] = suggested
                self.issues.append(
                    (
                        f"Port {resolved_host_port} for service '{svc_name}' is in use (set {key}={suggested})",
                        "warning",
                        True,
                    )
                )

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

            elif issue.startswith("Port ") and " is in use (set " in issue:
                # Apply all collected port fixes once (avoid repeated prompts per-row)
                if not self.port_fixes:
                    continue

                # Offer two strategies:
                # 1) update .env to a free port (recommended)
                # 2) stop the docker container(s) that publish the conflicting port
                if Confirm.ask("Fix port conflicts by updating .env?", default=True):
                    env_path = Path(".env")
                    for key, port in sorted(self.port_fixes.items()):
                        _upsert_env_value(env_path, key, str(port))
                        console.print(f"[green]✓[/] Set {key}={port} in .env")
                        fixed += 1
                else:
                    # Try to stop containers using the original conflicting ports.
                    # We parse port numbers from issue strings: "Port <n> for service..."
                    conflict_ports: set[int] = set()
                    for msg, _, _ in self.issues:
                        if not (isinstance(msg, str) and msg.startswith("Port ") and " for service " in msg):
                            continue
                        m = re.match(r"^Port\s+(?P<port>\d+)\s+for service", msg)
                        if m:
                            conflict_ports.add(int(m.group("port")))

                    stopped_any = False
                    for p in sorted(conflict_ports):
                        containers = _docker_containers_using_port(p)
                        if not containers:
                            continue
                        console.print(f"[yellow]Port {p} is published by:[/]")
                        for c in containers:
                            console.print(f"  {c['id']}  {c['name']}  {c['ports']}")
                        if Confirm.ask(f"Stop {len(containers)} container(s) to free port {p}?", default=False):
                            _docker_stop([c["id"] for c in containers])
                            console.print(f"[green]✓[/] Stopped container(s) using port {p}")
                            fixed += len(containers)
                            stopped_any = True

                    if not stopped_any:
                        console.print("[dim]No containers stopped. You can rerun with .env fix or stop manually.[/]")

                # Clear so we don't re-apply on next loop iteration
                self.port_fixes.clear()
                # Remove all port issues
                for row in self.issues[:]:
                    if row[0].startswith("Port ") and " is in use (set " in row[0]:
                        self.issues.remove(row)

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


def _parse_compose_host_port(port_entry: str) -> tuple[str | None, str | None]:
    """Parse a docker-compose ports entry and return (host_port_expr, var_name).

    Supports common forms:
        - "8000:8000"
        - "127.0.0.1:8000:8000"
        - "${PORT_WEB:-8000}:8000"
        - "127.0.0.1:${PORT_WEB:-8000}:8000"
        - "8000:8000/tcp"

    Returns:
        host_port_expr: string expression for host port (may include ${VAR:-default})
        var_name: extracted VAR name if host_port_expr is ${VAR...}
    """
    entry = port_entry.strip()
    if not entry:
        return None, None

    # Drop protocol suffix
    entry = entry.split("/", 1)[0]
    parts = entry.split(":")
    if len(parts) < 2:
        return None, None

    # last part is container port; host port is either parts[-2] or parts[-3] (if ip present)
    host_port_expr = parts[-2]
    var_name: str | None = None
    m = re.match(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)", host_port_expr)
    if m:
        var_name = m.group("name")
    return host_port_expr, var_name


def _is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    """Return True if TCP port appears to be free for binding on the local host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False


def _find_free_port_near(start_port: int, span: int = 50) -> int | None:
    """Find a free TCP port near start_port (inclusive)."""
    for p in range(start_port, start_port + span + 1):
        if _is_port_free(p):
            return p
    for p in range(max(1024, start_port - span), start_port):
        if _is_port_free(p):
            return p
    return None


def _upsert_env_value(env_path: Path, key: str, value: str) -> None:
    """Upsert KEY=value into env file, preserving other lines and comments."""
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n")
        return

    lines = env_path.read_text().splitlines(True)
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    updated = False
    new_lines: list[str] = []

    for line in lines:
        if key_re.match(line):
            # Preserve newline style from existing line
            newline = "\n" if not line.endswith("\r\n") else "\r\n"
            new_lines.append(f"{key}={value}{newline}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        new_lines.append(f"{key}={value}\n")

    env_path.write_text("".join(new_lines))


def _docker_containers_using_port(port: int) -> list[dict[str, str]]:
    """Return running docker containers that publish the given host port."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Ports}}"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return []

    containers: list[dict[str, str]] = []
    # Example ports: "0.0.0.0:8002->8002/tcp, [::]:8002->8002/tcp"
    token = f":{int(port)}->"
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        cid, name, ports = parts[0], parts[1], parts[2]
        if token in (ports or ""):
            containers.append({"id": cid, "name": name, "ports": ports})
    return containers


def _docker_stop(container_ids: list[str]) -> None:
    """Stop docker containers by ID."""
    if not container_ids:
        return
    subprocess.run(["docker", "stop", *container_ids], text=True)


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
        - Port conflicts

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
        diagnostics.check_ports()
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
    """👁️  Watch files and run tasks on changes.

    Automatically detects file changes and re-runs specified tasks.
    Useful for development workflows like auto-rebuilding on code changes.

    \b
    Examples:
        taskfile watch build              # Watch current dir, run 'build' on changes
        taskfile watch build test         # Run multiple tasks on change
        taskfile watch -p src build       # Watch only 'src' directory
        taskfile watch -p src -p tests test  # Watch multiple paths
        taskfile watch -d 500 build     # 500ms debounce (default: 300ms)
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
    """🕸️  Show task dependency graph.

    Visualizes task dependencies as a tree or exports to Graphviz DOT format.
    Helps understand the relationships between tasks.

    \b
    Examples:
        taskfile graph                  # Show all task dependencies
        taskfile graph build           # Show dependencies for 'build' task only
        taskfile graph --dot           # Export to DOT format
        taskfile graph --dot -o tasks.dot  # Save to file
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
    """🌐 Start web dashboard for managing tasks.

    Opens a web UI in your browser for visual task management.
    You can view, search, and run tasks from the browser.

    \b
    Examples:
        taskfile serve                    # Start on default port 8080
        taskfile serve -p 3000           # Use custom port
        taskfile serve --no-browser      # Don't auto-open browser
    """
    from taskfile.webui import serve_dashboard
    
    console.print(f"[bold green]🌐 Starting Taskfile Web UI...[/]")
    console.print(f"[dim]Port: {port}[/]")
    
    try:
        serve_dashboard(port=port, open_browser=not no_browser)
    except Exception as e:
        console.print(f"[red]Failed to start server: {e}[/]")
        sys.exit(1)
