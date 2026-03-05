"""CLI commands for import/export - convert between Taskfile and other formats."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from taskfile.cli.main import main, console
from taskfile.converters import import_file, export_file, detect_format
from taskfile.parser import load_taskfile, TaskfileNotFoundError, TaskfileParseError


@main.command(name="import")
@click.argument("source", type=click.Path(exists=True))
@click.option("--type", "source_type", type=click.Choice([
    "makefile", "github-actions", "npm", "shell", "dockerfile"
]), default=None, help="Source file type (auto-detected if omitted)")
@click.option("-o", "--output", "output_path", default="Taskfile.yml", help="Output path (default: Taskfile.yml)")
@click.option("--force", is_flag=True, help="Overwrite existing output file")
def import_cmd(source, source_type, output_path, force):
    """📥 Import from Makefile, GitHub Actions, npm scripts, etc.

    Converts existing build configurations to Taskfile format.

    \b
    Supported sources:
        makefile        — GNU Make (Makefile, GNUmakefile)
        github-actions  — .github/workflows/*.yml
        npm             — package.json scripts
        shell           — *.sh (functions become tasks)
        dockerfile      — Dockerfile (stages become tasks)

    \b
    Examples:
        taskfile import Makefile
        taskfile import .github/workflows/ci.yml --type github-actions
        taskfile import package.json --force
        taskfile import Makefile -o Taskfile.yml
    """
    source_path = Path(source)
    outpath = Path(output_path)
    
    if outpath.exists() and not force:
        console.print(f"[yellow]{outpath} already exists. Use --force to overwrite.[/]")
        sys.exit(1)
    
    # Auto-detect type if not specified
    if source_type is None:
        detected = detect_format(source_path)
        if detected:
            source_type = detected
            console.print(f"[dim]Auto-detected format: {source_type}[/]")
        else:
            console.print("[red]Could not auto-detect file type. Please specify with --type[/]")
            sys.exit(1)
    
    try:
        # Import the file
        config_dict = import_file(source_path, source_type)
        
        # Write as YAML
        import yaml
        yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)
        outpath.write_text(yaml_content, encoding="utf-8")
        
        console.print(f"[green]✓ Imported {source} → {outpath}[/]")
        console.print(f"[dim]  Type: {source_type}[/]")
        console.print(f"[dim]  Tasks: {len(config_dict.get('tasks', {}))}[/]")
        console.print("\n[dim]Review the generated Taskfile, then run: taskfile list[/]")
        
    except Exception as e:
        console.print(f"[red]Import failed: {e}[/]")
        sys.exit(1)


@main.command(name="export")
@click.argument("target_type", type=click.Choice([
    "makefile", "github-actions", "npm", "docker-compose"
]))
@click.option("-o", "--output", "output_path", default=None, help="Output file path")
@click.option("--workflow-name", default="ci", help="Workflow name for GitHub Actions export")
@click.option("--project-name", default="my-project", help="Project name for npm export")
@click.option("-f", "--file", "taskfile_path", default=None, help="Input Taskfile path")
@click.pass_context
def export_cmd(ctx, target_type, output_path, workflow_name, project_name, taskfile_path):
    """📤 Export Taskfile to other formats.

    Convert Taskfile to Makefile, GitHub Actions, npm scripts, etc.

    \b
    Supported targets:
        makefile        — GNU Make format
        github-actions  — GitHub Actions workflow (.github/workflows/)
        npm             — package.json scripts
        docker-compose  — docker-compose.yml services

    \b
    Examples:
        taskfile export makefile -o Makefile
        taskfile export github-actions -o .github/workflows/ci.yml
        taskfile export npm --project-name my-app
        taskfile export docker-compose -o docker-compose.yml
    """
    # Determine output path if not specified
    if output_path is None:
        defaults = {
            "makefile": "Makefile",
            "github-actions": ".github/workflows/ci.yml",
            "npm": "package.json",
            "docker-compose": "docker-compose.yml",
        }
        output_path = defaults.get(target_type, f"exported.{target_type}")
    
    outpath = Path(output_path)
    
    try:
        # Load Taskfile
        config = load_taskfile(taskfile_path)
        
        # Export to target format
        content = export_file(
            config,
            target_type,
            workflow_name=workflow_name,
            project_name=project_name,
        )
        
        # Create parent directories if needed
        outpath.parent.mkdir(parents=True, exist_ok=True)
        
        # Write output
        outpath.write_text(content, encoding="utf-8")
        
        console.print(f"[green]✓ Exported to {outpath}[/]")
        console.print(f"[dim]  Format: {target_type}[/]")
        console.print(f"[dim]  Tasks: {len(config.tasks)}[/]")
        
        # Show format-specific hints
        if target_type == "github-actions":
            console.print("\n[dim]To use:[/]")
            console.print("  git add .github/workflows/ci.yml && git commit -m 'Add CI'")
        elif target_type == "makefile":
            console.print("\n[dim]To use:[/]")
            console.print("  make <target>")
        elif target_type == "npm":
            console.print("\n[dim]To use:[/]")
            console.print("  npm run <script>")
        
    except TaskfileNotFoundError:
        console.print("[red]No Taskfile found in current directory[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Export failed: {e}[/]")
        sys.exit(1)


@main.command()
def detect():
    """🔍 Detect build configuration files in current directory.

    Scans for Makefile, package.json, .github/workflows/, etc.
    and shows what can be imported.
    """
    cwd = Path.cwd()
    found = []
    
    # Check for various config files
    checks = [
        ("Makefile", "makefile"),
        ("GNUmakefile", "makefile"),
        ("package.json", "npm"),
        (".github/workflows/*.yml", "github-actions"),
        ("docker-compose.yml", "docker-compose"),
        ("Dockerfile", "dockerfile"),
        ("setup.py", "python"),
        ("pyproject.toml", "python"),
        ("Cargo.toml", "rust"),
        ("go.mod", "go"),
    ]
    
    for pattern, fmt in checks:
        if '*' in pattern:
            matches = list(cwd.glob(pattern))
            if matches:
                found.append((matches[0], fmt))
        else:
            path = cwd / pattern
            if path.exists():
                found.append((path, fmt))
    
    if not found:
        console.print("[yellow]No recognizable build configuration files found.[/]")
        console.print("\n[dim]Supported formats:[/]")
        console.print("  - Makefile (GNU Make)")
        console.print("  - package.json (npm scripts)")
        console.print("  - .github/workflows/*.yml (GitHub Actions)")
        console.print("  - docker-compose.yml")
        console.print("  - Dockerfile")
        console.print("\n[dim]Create a new Taskfile:[/]")
        console.print("  taskfile init")
        return
    
    console.print(Panel.fit(
        "[bold]Detected build configuration files:[/]",
        border_style="green"
    ))
    
    for path, fmt in found:
        console.print(f"  [green]{path.name}[/] [dim]({fmt})[/]")
    
    console.print("\n[dim]To import:[/]")
    console.print(f"  taskfile import {found[0][0].name}")
    console.print("\n[dim]Or import all:[/]")
    for path, fmt in found:
        console.print(f"  taskfile import {path.name} --type {fmt} --force")
