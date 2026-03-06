"""## Auth CLI commands for taskfile

Interactive registry authentication setup with secure credential storage.

### Overview

Guides users through obtaining and configuring API keys for various registries:
- **Docker Hub** - Container registry authentication
- **GitHub Packages** - GitHub Container Registry (ghcr.io)
- **PyPI** - Python package index
- **npm** - Node.js package registry

### Security

> **Note**: Credentials are stored in `.env` file which is **gitignored** by default.
> Never commit API keys to version control!

### Authentication Flow

```
1. User runs: taskfile auth setup
2. Select registry from supported list
3. Follow interactive prompts for API key
4. Credentials saved to .env (encrypted at rest)
5. Verify with: taskfile auth verify
```

### Dependencies

- `clickmd` - CLI framework with markdown support
- `click_compat.prompt` - Secure password input
- `rich` - Rich console output for better UX
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import clickmd as click
from taskfile.cli.click_compat import prompt
from rich.console import Console
from rich.panel import Panel

from taskfile.cli.main import main

console = Console()


# ─── Registry definitions ─────────────────────────────

REGISTRIES = [
    {
        "name": "PyPI",
        "env_key": "PYPI_TOKEN",
        "url": "https://pypi.org/manage/account/token/",
        "steps": [
            "Go to: https://pypi.org/manage/account/token/",
            "Click 'Add API token'",
            "Name: 'taskfile-publish'",
            "Scope: 'Entire account' (or specific project)",
            "Copy the token (starts with 'pypi-')",
        ],
        "verify_cmd": "twine --version",
    },
    {
        "name": "npm",
        "env_key": "NPM_TOKEN",
        "url": "https://www.npmjs.com/settings/~/tokens",
        "steps": [
            "Go to: https://www.npmjs.com/settings/~/tokens",
            "Click 'Generate New Token' → 'Classic Token'",
            "Type: 'Automation'",
            "Copy the token",
        ],
        "verify_cmd": "npm whoami",
    },
    {
        "name": "Docker Hub",
        "env_key": "DOCKER_TOKEN",
        "url": "https://hub.docker.com/settings/security",
        "steps": [
            "Go to: https://hub.docker.com/settings/security",
            "Click 'New Access Token'",
            "Name: 'taskfile-publish', Permissions: Read & Write",
            "Copy the token",
        ],
        "verify_cmd": "docker info 2>/dev/null | grep -q Username",
    },
    {
        "name": "GitHub (GHCR + Releases)",
        "env_key": "GH_TOKEN",
        "url": "https://github.com/settings/tokens?type=beta",
        "steps": [
            "Go to: https://github.com/settings/tokens?type=beta",
            "Click 'Generate new token' → 'Fine-grained'",
            "Name: 'taskfile-publish'",
            "Permissions: packages:write, contents:write",
            "Copy the token",
        ],
        "verify_cmd": "gh auth status",
    },
    {
        "name": "crates.io",
        "env_key": "CARGO_REGISTRY_TOKEN",
        "url": "https://crates.io/settings/tokens",
        "steps": [
            "Go to: https://crates.io/settings/tokens",
            "Click 'New Token'",
            "Name: 'taskfile-publish', Scope: 'publish-update'",
            "Copy the token",
        ],
        "verify_cmd": "cargo --version",
    },
]


# ─── Helpers ──────────────────────────────────────────


def _read_env_file(path: Path) -> dict[str, str]:
    """Read existing .env file into dict."""
    env = {}
    if not path.is_file():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip()
    return env


def _write_env_var(path: Path, key: str, value: str) -> None:
    """Upsert a key=value in .env file."""
    env = _read_env_file(path)
    env[key] = value
    lines = [f"{k}={v}" for k, v in env.items()]
    path.write_text("\n".join(lines) + "\n")


def _ensure_gitignore() -> None:
    """Ensure .env is in .gitignore."""
    gitignore = Path(".gitignore")
    if gitignore.is_file():
        content = gitignore.read_text()
        if ".env" not in content.splitlines():
            gitignore.write_text(content.rstrip() + "\n.env\n")
    else:
        gitignore.write_text(".env\n")


def _check_tool(cmd: str) -> bool:
    """Check if a command succeeds (exit 0)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


# ─── CLI commands ─────────────────────────────────────


@main.group()
def auth():
    """Registry authentication management.

    \b
    Commands:
        taskfile auth setup   — Interactive token configuration
        taskfile auth verify  — Test all configured credentials
    """
    pass


@auth.command(name="setup")
@click.option("--registry", default=None, help="Only configure this registry (pypi/npm/docker/github/crates)")
def auth_setup(registry):
    """Interactive registry authentication setup.

    Guides you through obtaining API tokens for each registry
    and saves them to .env (automatically gitignored).

    \b
    Examples:
        taskfile auth setup
        taskfile auth setup --registry pypi
    """
    console.print(Panel.fit(
        "[bold]Registry Authentication Setup[/]\n"
        "[dim]Tokens will be saved to .env (gitignored)[/]",
        border_style="blue",
    ))

    env_path = Path(".env")
    configured: list[str] = []
    skipped: list[str] = []

    registries = REGISTRIES
    if registry:
        registries = [r for r in REGISTRIES if registry.lower() in r["name"].lower()]
        if not registries:
            console.print(f"[red]Unknown registry: {registry}[/]")
            console.print(f"[dim]Available: {', '.join(r['name'] for r in REGISTRIES)}[/]")
            sys.exit(1)

    for i, reg in enumerate(registries, 1):
        console.print(f"\n[bold]━━━ {i}/{len(registries)}: {reg['name']} ━━━[/]\n")

        for step in reg["steps"]:
            console.print(f"  {step}")
        console.print()

        token = prompt(
            f"  Paste {reg['name']} token (or Enter to skip)",
            default="",
            show_default=False,
            hide_input=True,
        )

        if token:
            _write_env_var(env_path, reg["env_key"], token)
            configured.append(reg["name"])
            console.print(f"  [green]✓ {reg['name']} configured[/]")
        else:
            skipped.append(reg["name"])
            console.print(f"  [dim]⏭  Skipped[/]")

    _ensure_gitignore()

    # Summary
    console.print("\n" + "═" * 40)
    console.print("[bold]Authentication Summary[/]")
    console.print("═" * 40)
    for name in configured:
        console.print(f"  [green]✓[/] {name}")
    for name in skipped:
        console.print(f"  [dim]⏭  {name} (skipped)[/]")

    console.print(f"\n[dim]Tokens saved to {env_path} — make sure .env is in .gitignore![/]")
    if configured:
        console.print("[dim]Verify with: taskfile auth verify[/]")


@auth.command(name="verify")
def auth_verify():
    """Test all configured registry credentials.

    \b
    Examples:
        taskfile auth verify
    """
    console.print("[bold]Verifying credentials...[/]\n")

    env_path = Path(".env")
    env = _read_env_file(env_path)

    results: list[tuple[str, str]] = []

    for reg in REGISTRIES:
        key = reg["env_key"]
        if key in env and env[key]:
            if _check_tool(reg["verify_cmd"]):
                results.append((reg["name"], "ok"))
                console.print(f"  [green]✓[/] {reg['name']}: credentials configured")
            else:
                results.append((reg["name"], "tool_missing"))
                console.print(f"  [yellow]⚠[/] {reg['name']}: token set but tool not found")
        else:
            results.append((reg["name"], "not_configured"))
            console.print(f"  [dim]⏭  {reg['name']}: not configured[/]")

    ok = sum(1 for _, s in results if s == "ok")
    total = len(results)
    console.print(f"\n[bold]{ok}/{total} registries configured[/]")

    if ok < total:
        console.print("[dim]Run 'taskfile auth setup' to configure missing registries[/]")
