"""Validation command and file-checking helpers for the CLI."""

from __future__ import annotations


from rich.console import Console

console = Console()


def check_script_files_status(config, taskfile_dir) -> bool:
    """Check script files and print status. Returns True if all found."""
    all_ok = True
    for name, task in sorted(config.tasks.items()):
        if not task.script:
            continue
        script_path = taskfile_dir / task.script
        if script_path.exists():
            console.print(f"  [green]✓[/] {task.script} [dim](task: {name})[/]")
        else:
            console.print(f"  [red]✗[/] {task.script} [dim](task: {name})[/] [red]— not found[/]")
            all_ok = False
    return all_ok


def check_env_files_status(config, taskfile_dir) -> bool:
    """Check env files and print status. Returns True if all found."""
    all_ok = True
    for env_name, env in sorted(config.environments.items()):
        if env.env_file:
            p = taskfile_dir / env.env_file
            if p.exists():
                console.print(f"  [green]✓[/] {env.env_file} [dim](env: {env_name})[/]")
            else:
                console.print(
                    f"  [red]✗[/] {env.env_file} [dim](env: {env_name})[/] [red]— not found[/]"
                )
                all_ok = False
    return all_ok


def check_compose_services(taskfile_dir) -> bool:
    """Check docker-compose.yml services (build contexts, Dockerfiles). Returns True if all OK."""
    import yaml

    compose_path = taskfile_dir / "docker-compose.yml"
    if not compose_path.exists():
        return True

    console.print("  [green]✓[/] docker-compose.yml")
    all_ok = True
    try:
        compose_data = yaml.safe_load(compose_path.read_text()) or {}
        services = compose_data.get("services", {})
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            build = svc_data.get("build")
            if isinstance(build, str):
                build_path = taskfile_dir / build
                if build_path.exists():
                    console.print(f"  [green]✓[/] {build} [dim](service: {svc_name})[/]")
                else:
                    console.print(
                        f"  [red]✗[/] {build} [dim](service: {svc_name})[/] [red]— not found[/]"
                    )
                    all_ok = False
            elif isinstance(build, dict):
                context = build.get("context", ".")
                dockerfile = build.get("dockerfile", "Dockerfile")
                context_path = taskfile_dir / context
                if context_path.exists():
                    console.print(f"  [green]✓[/] {context}/ [dim](context for {svc_name})[/]")
                else:
                    console.print(
                        f"  [red]✗[/] {context}/ [dim](context for {svc_name})[/] [red]— not found[/]"
                    )
                    all_ok = False
                df_path = context_path / dockerfile if context != "." else taskfile_dir / dockerfile
                if df_path.exists():
                    console.print(f"  [green]✓[/] {context}/{dockerfile} [dim]({svc_name})[/]")
                else:
                    console.print(
                        f"  [red]✗[/] {context}/{dockerfile} [dim]({svc_name})[/] [red]— not found[/]"
                    )
                    all_ok = False
    except Exception as e:
        console.print(f"  [yellow]⚠[/] Could not parse docker-compose.yml: {e}")
    return all_ok


def check_common_files(taskfile_dir) -> None:
    """Check common project files presence."""
    for common_file in (".env", ".gitignore", "README.md", "VERSION"):
        p = taskfile_dir / common_file
        if p.exists():
            console.print(f"  [green]✓[/] {common_file}")
        else:
            console.print(f"  [dim]·[/] {common_file} [dim]— not present[/]")


def validate_dependent_files(config) -> None:
    """Check all files referenced by the Taskfile and report status."""
    from pathlib import Path as _Path

    taskfile_dir = _Path(config.source_path).parent if config.source_path else _Path.cwd()
    console.print("\n[bold]📁 Dependent files:[/]")

    ok_scripts = check_script_files_status(config, taskfile_dir)
    ok_envs = check_env_files_status(config, taskfile_dir)
    ok_compose = check_compose_services(taskfile_dir)
    check_common_files(taskfile_dir)

    if ok_scripts and ok_envs and ok_compose:
        console.print("[green]  All referenced files found.[/]")
    else:
        console.print(
            "[yellow]  Some files are missing — run 'taskfile doctor --fix' for auto-fix options[/]"
        )


def print_dependency_tree(config) -> None:
    """Print dependency tree for all tasks."""
    console.print("\n[bold]🌳 Dependency tree:[/]")
    for name, task in sorted(config.tasks.items()):
        if not task.deps:
            console.print(f"  [green]{name}[/]")
        else:
            dep_str = " → ".join(task.deps)
            console.print(f"  [green]{name}[/] [dim]← {dep_str}[/]")
            # Show transitive deps
            visited = set()
            _print_transitive_deps(config, task.deps, visited, depth=2)


def _print_transitive_deps(config, deps: list, visited: set, depth: int) -> None:
    """Recursively print transitive dependencies."""
    for dep_name in deps:
        if dep_name in visited:
            continue
        visited.add(dep_name)
        dep_task = config.tasks.get(dep_name)
        if dep_task and dep_task.deps:
            indent = "  " * depth
            sub_deps = " → ".join(dep_task.deps)
            console.print(f"{indent}[dim]└─ {dep_name} ← {sub_deps}[/]")
            _print_transitive_deps(config, dep_task.deps, visited, depth + 1)
