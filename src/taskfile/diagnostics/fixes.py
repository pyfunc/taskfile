"""Layer 4: Algorithmic fixes — apply deterministic fixes for known issues.

Each fix function receives an Issue and returns True if fixed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from taskfile.diagnostics.models import Issue, IssueCategory, FixStrategy

console = Console()


def apply_fixes(issues: list[Issue], interactive: bool = True) -> int:
    """Apply all fixable issues. Returns count of fixed issues."""
    fixed = 0
    for issue in issues:
        if issue.fix_strategy == FixStrategy.AUTO:
            if apply_single_fix(issue, interactive=False):
                fixed += 1
        elif issue.fix_strategy == FixStrategy.CONFIRM and interactive:
            if apply_single_fix(issue, interactive=True):
                fixed += 1
    return fixed


def apply_single_fix(issue: Issue, interactive: bool = True) -> bool:
    """Apply a single fix. Returns True if fixed."""
    # Dispatch based on issue content
    if "env_file not found" in issue.message and issue.context and issue.context.get("example"):
        return _fix_copy_env_example(issue, interactive)
    if "Taskfile.yml not found" in issue.message:
        return _fix_create_taskfile(issue, interactive)
    if "Not a git repository" in issue.message:
        return _fix_init_git(issue, interactive)
    if "PORT_WEB or PORT_LANDING instead of PORT" in issue.message:
        return _fix_rename_port(issue)
    if "Missing required variable" in issue.message:
        return _fix_missing_variable(issue, interactive)
    if issue.fix_command:
        return _fix_run_command(issue, interactive)
    return False


# ─── Specific fix functions ───────────────────────────────────────


def _fix_copy_env_example(issue: Issue, interactive: bool) -> bool:
    """Copy .env.example → .env."""
    ctx = issue.context or {}
    env_file = ctx.get("env_file")
    example = ctx.get("example")
    if not env_file or not example:
        return False

    env_path = Path(env_file)
    example_path = Path(example)
    if not example_path.exists():
        return False

    if interactive:
        console.print(f"[yellow]⚠[/] Missing {env_path.name} — found {example_path.name}")
        if not Confirm.ask(f"Copy {example_path.name} → {env_path.name}?", default=True):
            return False

    env_path.write_text(example_path.read_text())
    console.print(f"[green]✓[/] Created {env_path.name} from {example_path.name}")
    console.print(f"  [dim]Edit {env_path.name} to set your actual values[/]")
    _mark_fixed(issue)
    return True


def _fix_create_taskfile(issue: Issue, interactive: bool) -> bool:
    """Create a minimal Taskfile.yml."""
    if interactive and not Confirm.ask("Create Taskfile.yml?", default=True):
        return False
    try:
        from taskfile.scaffold import generate_taskfile
        Path("Taskfile.yml").write_text(generate_taskfile("minimal"))
        console.print("[green]✓ Created Taskfile.yml[/]")
        _mark_fixed(issue)
        return True
    except Exception as e:
        console.print(f"[red]✗ Failed to create Taskfile.yml: {e}[/]")
        return False


def _fix_init_git(issue: Issue, interactive: bool) -> bool:
    """Initialize git repository."""
    if interactive and not Confirm.ask("Initialize git repository?", default=False):
        return False
    result = subprocess.run(["git", "init"], capture_output=True)
    if result.returncode == 0:
        console.print("[green]✓ Initialized git repository[/]")
        _mark_fixed(issue)
        return True
    return False


def _fix_rename_port(issue: Issue) -> bool:
    """Rename PORT= to PORT_WEB= in .env file."""
    env_file = issue.message.split(":")[0]
    env_path = Path(env_file)
    if not env_path.exists():
        return False

    content = env_path.read_text()
    new_lines = []
    changed = False
    for line in content.splitlines():
        if line.startswith("PORT=") and not line.startswith("PORT_"):
            port_value = line.split("=", 1)[1].strip() or "8000"
            new_lines.append(f"PORT_WEB={port_value}")
            console.print(f"  [green]✓[/] Changed PORT={port_value} → PORT_WEB={port_value}")
            changed = True
        else:
            new_lines.append(line)
    if changed:
        env_path.write_text("\n".join(new_lines) + "\n")
        _mark_fixed(issue)
    return changed


def _fix_missing_variable(issue: Issue, interactive: bool) -> bool:
    """Prompt user for a missing variable value."""
    if not interactive:
        return False

    env_file = issue.message.split(":")[0]
    var_name = issue.message.split("Missing required variable ")[-1].strip()
    env_path = Path(env_file)

    console.print(f"[yellow]⚠[/] Missing {var_name} in {env_file}")
    value = Prompt.ask(f"Enter value for {var_name}", default="")
    if value:
        _upsert_env_value(env_path, var_name, value)
        console.print(f"[green]✓[/] Added {var_name}={value} to {env_file}")
        _mark_fixed(issue)
        return True
    return False


def _fix_run_command(issue: Issue, interactive: bool) -> bool:
    """Run the fix_command from the issue."""
    if not issue.fix_command:
        return False

    if interactive:
        console.print(f"[yellow]⚠[/] {issue.message}")
        console.print(f"  Fix: [cyan]{issue.fix_command}[/]")
        if not Confirm.ask("Run this fix?", default=True):
            return False

    result = subprocess.run(issue.fix_command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        console.print(f"[green]✓[/] Fixed: {issue.message}")
        _mark_fixed(issue)
        return True
    else:
        console.print(f"[red]✗[/] Fix failed: {result.stderr.strip()}")
        return False


# ─── Helpers ──────────────────────────────────────────────────────


def _mark_fixed(issue: Issue) -> None:
    """Mark an issue as fixed (used for report filtering)."""
    if issue.context is None:
        issue.context = {}
    issue.context["_fixed"] = True


def _upsert_env_value(env_path: Path, key: str, value: str) -> None:
    """Upsert KEY=value into env file."""
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n")
        return

    lines = env_path.read_text().splitlines(True)
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    updated = False
    new_lines: list[str] = []

    for line in lines:
        if key_re.match(line):
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
