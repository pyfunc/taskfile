"""CLI commands for workspace (multi-project) operations.

Allows discovery, filtering, and group operations (run, doctor, validate, deploy)
across multiple local projects within a specified directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import clickmd as click
from rich import box
from rich.console import Console
from rich.table import Table

from taskfile.cli.main import main
from taskfile.workspace import (
    CommandResult,
    Project,
    analyze_project,
    discover_projects,
    filter_projects,
    fix_project,
    run_in_project,
    run_task_in_projects,
    validate_project,
)

console = Console()


# ─── Helpers ──────────────────────────────────────────


def _load_projects(
    root: str,
    depth: int,
    has_task: str | None = None,
    has_workflow: str | None = None,
    has_taskfile: bool | None = None,
    has_doql: bool | None = None,
    has_docker: bool | None = None,
    name: str | None = None,
) -> list[Project]:
    """Discover projects and apply filters."""
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        console.print(f"[red]Error:[/] Path does not exist: {root_path}")
        sys.exit(1)

    projects = discover_projects(root_path, max_depth=depth)
    return filter_projects(
        projects,
        has_task=has_task,
        has_workflow=has_workflow,
        has_taskfile=has_taskfile,
        has_doql=has_doql,
        has_docker=has_docker,
        name_pattern=name,
    )


def _print_summary_line(projects: list[Project], root: str) -> None:
    """Print a concise summary of discovered projects."""
    total = len(projects)
    with_tf = sum(1 for p in projects if p.has_taskfile)
    with_doql = sum(1 for p in projects if p.has_doql)
    console.print(
        f"[dim]Scanned:[/] {root}  "
        f"[bold]{total}[/] projects  "
        f"[green]{with_tf}[/] Taskfile  "
        f"[cyan]{with_doql}[/] doql"
    )


# ─── CLI group ────────────────────────────────────────


@main.group()
def workspace():
    """Manage multiple local projects at once.

    \b
    Discover all projects within a path, filter by manifest contents,
    and run group operations (run, doctor, validate, deploy, status).

    \b
    Examples:
        taskfile workspace list --root /home/tom/github/semcod
        taskfile workspace list --has-task test
        taskfile workspace run test --root /home/tom/github/semcod
        taskfile workspace doctor --root /home/tom/github/semcod
        taskfile workspace validate --root /home/tom/github/semcod
    """
    pass


# ─── workspace list ───────────────────────────────────


@workspace.command(name="list")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth (default: 2)")
@click.option("--has-task", default=None, help="Only projects with this task")
@click.option("--has-workflow", default=None, help="Only projects with this doql workflow")
@click.option("--taskfile-only", is_flag=True, help="Only projects with Taskfile.yml")
@click.option("--doql-only", is_flag=True, help="Only projects with app.doql.css")
@click.option("--docker-only", is_flag=True, help="Only projects with Docker")
@click.option("--name", default=None, help="Filter by name pattern (regex)")
@click.option("--tasks", is_flag=True, help="Show tasks column")
@click.option("--workflows", is_flag=True, help="Show workflows column")
def workspace_list(
    root, depth, has_task, has_workflow,
    taskfile_only, doql_only, docker_only, name,
    tasks, workflows,
):
    """List all projects matching filters."""
    projects = _load_projects(
        root=root,
        depth=depth,
        has_task=has_task,
        has_workflow=has_workflow,
        has_taskfile=True if taskfile_only else None,
        has_doql=True if doql_only else None,
        has_docker=True if docker_only else None,
        name=name,
    )

    if not projects:
        console.print("[yellow]No projects match the filters.[/]")
        return

    table = Table(title=f"Projects in {root}", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="green")
    table.add_column("Path", style="dim")
    table.add_column("TF", justify="center")
    table.add_column("doql", justify="center")
    table.add_column("Docker", justify="center")
    if tasks:
        table.add_column("Tasks", style="cyan")
    if workflows:
        table.add_column("Workflows", style="magenta")

    for i, project in enumerate(projects, 1):
        row = [
            str(i),
            project.name,
            str(project.path),
            "✓" if project.has_taskfile else "—",
            "✓" if project.has_doql else "—",
            "✓" if (project.has_docker_compose or project.has_dockerfile) else "—",
        ]
        if tasks:
            row.append(", ".join(project.taskfile_tasks[:5]) + ("…" if len(project.taskfile_tasks) > 5 else ""))
        if workflows:
            row.append(", ".join(project.doql_workflows[:5]) + ("…" if len(project.doql_workflows) > 5 else ""))
        table.add_row(*row)

    console.print(table)
    _print_summary_line(projects, root)


# ─── workspace tasks ──────────────────────────────────


@workspace.command(name="tasks")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
def workspace_tasks(root, depth):
    """Show all unique tasks across projects with their counts."""
    projects = _load_projects(root=root, depth=depth)

    from collections import Counter
    counter: Counter[str] = Counter()
    for p in projects:
        for task in p.taskfile_tasks:
            counter[task] += 1

    if not counter:
        console.print("[yellow]No tasks found.[/]")
        return

    table = Table(title=f"Task frequency across {len(projects)} projects", box=box.ROUNDED)
    table.add_column("Task", style="cyan")
    table.add_column("Projects", justify="right", style="green")
    table.add_column("%", justify="right", style="dim")

    for task, count in counter.most_common():
        pct = f"{100 * count / len(projects):.0f}%"
        table.add_row(task, str(count), pct)

    console.print(table)


# ─── workspace workflows ──────────────────────────────


@workspace.command(name="workflows")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
def workspace_workflows(root, depth):
    """Show all unique doql workflows across projects with their counts."""
    projects = _load_projects(root=root, depth=depth)

    from collections import Counter
    counter: Counter[str] = Counter()
    for p in projects:
        for wf in p.doql_workflows:
            counter[wf] += 1

    if not counter:
        console.print("[yellow]No workflows found.[/]")
        return

    table = Table(title=f"Workflow frequency across {len(projects)} projects", box=box.ROUNDED)
    table.add_column("Workflow", style="magenta")
    table.add_column("Projects", justify="right", style="green")
    table.add_column("%", justify="right", style="dim")

    for wf, count in counter.most_common():
        pct = f"{100 * count / len(projects):.0f}%"
        table.add_row(wf, str(count), pct)

    console.print(table)


# ─── workspace run ────────────────────────────────────


@workspace.command(name="run")
@click.argument("task_name")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
@click.option("--name", default=None, help="Filter projects by name (regex)")
@click.option("--timeout", default=300, type=int, help="Per-project timeout (seconds)")
@click.option("--dry-run", is_flag=True, help="Show what would run without executing")
@click.option("--fail-fast", is_flag=True, help="Stop on first failure")
@click.option("--continue-on-error", is_flag=True, help="Show summary at end; continue on failures")
def workspace_run(task_name, root, depth, name, timeout, dry_run, fail_fast, continue_on_error):
    """Run a task in every project that has it.

    \b
    Examples:
        taskfile workspace run test --root /home/tom/github/semcod
        taskfile workspace run lint --root /home/tom/github/semcod --name 'algi.*'
        taskfile workspace run build --dry-run
    """
    projects = _load_projects(
        root=root,
        depth=depth,
        has_task=task_name,
        name=name,
    )

    if not projects:
        console.print(f"[yellow]No projects have task '{task_name}'[/]")
        return

    console.print(f"[bold]Running '{task_name}' in {len(projects)} project(s)[/]")
    _print_summary_line(projects, root)

    if dry_run:
        console.print("\n[yellow]DRY RUN — commands that would execute:[/]\n")
        for p in projects:
            console.print(f"  cd {p.path} && taskfile {task_name}")
        return

    results: list[CommandResult] = []
    for i, project in enumerate(projects, 1):
        console.print(
            f"\n[bold cyan]━━━ [{i}/{len(projects)}] {project.name} ━━━[/]"
        )
        console.print(f"[dim]  {project.path}[/]")
        result = run_in_project(
            project,
            ['taskfile', task_name],
            timeout=timeout,
            capture=not (fail_fast and len(projects) == 1),
        )
        results.append(result)

        if result.success:
            console.print(f"[green]  ✓ OK[/]")
        else:
            console.print(f"[red]  ✗ FAILED (rc={result.returncode})[/]")
            if result.stderr:
                tail = result.stderr.strip().splitlines()[-5:]
                for line in tail:
                    console.print(f"[red]    {line}[/]")
            if fail_fast:
                console.print("\n[red]Stopped (--fail-fast)[/]")
                break

    # Summary
    ok = sum(1 for r in results if r.success)
    console.print(f"\n[bold]Summary: [green]{ok}[/]/{len(results)} successful[/]")

    if ok < len(results):
        console.print("\n[red]Failed projects:[/]")
        for r in results:
            if not r.success:
                console.print(f"  [red]✗[/] {r.project.name} ({r.project.path})")
        sys.exit(1)


# ─── workspace doctor ─────────────────────────────────


@workspace.command(name="doctor")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
@click.option("--timeout", default=60, type=int, help="Per-project timeout")
@click.option("--verbose", "-v", is_flag=True, help="Show full output")
def workspace_doctor(root, depth, timeout, verbose):
    """Run 'taskfile doctor' in every project."""
    projects = _load_projects(root=root, depth=depth, has_taskfile=True)

    if not projects:
        console.print("[yellow]No projects with Taskfile.yml found[/]")
        return

    console.print(f"[bold]Running doctor in {len(projects)} project(s)[/]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Project", style="green")
    table.add_column("Status", justify="center")
    table.add_column("Issues", style="yellow")

    for i, project in enumerate(projects, 1):
        result = run_in_project(
            project,
            ['taskfile', 'doctor'],
            timeout=timeout,
        )
        if result.success:
            status = "[green]✓ OK[/]"
            issues = "—"
        else:
            status = "[red]✗ FAIL[/]"
            # Extract summary line from output
            out = result.stdout + result.stderr
            issue_lines = [
                ln.strip() for ln in out.splitlines()
                if any(k in ln.lower() for k in ['error', 'issue', 'warning'])
            ][:3]
            issues = '; '.join(issue_lines) or f'rc={result.returncode}'
            if len(issues) > 60:
                issues = issues[:57] + '...'

        table.add_row(str(i), project.name, status, issues)

        if verbose:
            console.print(f"\n[bold]{project.name}[/]")
            console.print(result.stdout or result.stderr)

    console.print(table)


# ─── workspace validate ───────────────────────────────


@workspace.command(name="validate")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
@click.option("--strict", is_flag=True, help="Exit with code 1 on any issue")
def workspace_validate(root, depth, strict):
    """Validate manifests (Taskfile.yml + app.doql.css) in all projects."""
    projects = _load_projects(root=root, depth=depth)

    if not projects:
        console.print("[yellow]No projects found[/]")
        return

    root_path = Path(root).resolve()

    table = Table(title=f"Manifest validation — {len(projects)} projects", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Project", style="green")
    table.add_column("TF tasks", justify="right")
    table.add_column("doql workflows", justify="right")
    table.add_column("Issues", style="yellow")

    total_issues = 0
    for i, project in enumerate(projects, 1):
        issues = validate_project(project)
        total_issues += len(issues)
        issues_str = '; '.join(issues) if issues else "[green]—[/]"
        if len(issues_str) > 60:
            issues_str = issues_str[:57] + '...'
        try:
            rel = project.path.relative_to(root_path)
            name_display = str(rel)
        except ValueError:
            name_display = project.name
        table.add_row(
            str(i),
            name_display,
            str(len(project.taskfile_tasks)),
            str(len(project.doql_workflows)),
            issues_str,
        )

    console.print(table)
    console.print(
        f"\n[bold]Total: {total_issues} issue(s) across {len(projects)} project(s)[/]"
    )

    if strict and total_issues > 0:
        sys.exit(1)


# ─── workspace status ─────────────────────────────────


@workspace.command(name="status")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
def workspace_status(root, depth):
    """Show overall status of all projects (git, docker, manifests)."""
    projects = _load_projects(root=root, depth=depth)

    if not projects:
        console.print("[yellow]No projects found[/]")
        return

    table = Table(title=f"Workspace status — {root}", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Project", style="green")
    table.add_column("Git", justify="center")
    table.add_column("TF", justify="center")
    table.add_column("doql", justify="center")
    table.add_column("Docker", justify="center")
    table.add_column("Tasks", justify="right")
    table.add_column("Workflows", justify="right")

    for i, project in enumerate(projects, 1):
        table.add_row(
            str(i),
            project.name,
            "✓" if project.has_git else "—",
            "✓" if project.has_taskfile else "—",
            "✓" if project.has_doql else "—",
            "✓" if (project.has_docker_compose or project.has_dockerfile) else "—",
            str(len(project.taskfile_tasks)),
            str(len(project.doql_workflows)),
        )

    console.print(table)
    _print_summary_line(projects, root)


# ─── workspace deploy ─────────────────────────────────


@workspace.command(name="deploy")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
@click.option("--name", default=None, help="Filter projects by name (regex)")
@click.option("--timeout", default=600, type=int, help="Per-project timeout")
@click.option("--dry-run", is_flag=True, help="Show deploy plan without executing")
def workspace_deploy(root, depth, name, timeout, dry_run):
    """Deploy (docker-compose up) all projects with Docker setup.

    Runs 'taskfile up' if available, else 'docker compose up -d'.
    """
    projects = _load_projects(
        root=root,
        depth=depth,
        has_docker=True,
        name=name,
    )

    if not projects:
        console.print("[yellow]No Docker-enabled projects found[/]")
        return

    console.print(f"[bold]Deploying {len(projects)} project(s)[/]")

    if dry_run:
        console.print("\n[yellow]DRY RUN:[/]\n")
        for p in projects:
            if p.has_task_named('up'):
                console.print(f"  cd {p.path} && taskfile up")
            else:
                console.print(f"  cd {p.path} && docker compose up -d")
        return

    success = 0
    for i, project in enumerate(projects, 1):
        console.print(f"\n[bold cyan]━━━ [{i}/{len(projects)}] {project.name} ━━━[/]")

        if project.has_task_named('up'):
            cmd = ['taskfile', 'up']
        else:
            cmd = ['docker', 'compose', 'up', '-d']

        result = run_in_project(project, cmd, timeout=timeout)
        if result.success:
            console.print(f"[green]  ✓ Deployed[/]")
            success += 1
        else:
            console.print(f"[red]  ✗ Failed (rc={result.returncode})[/]")
            if result.stderr:
                tail = result.stderr.strip().splitlines()[-3:]
                for line in tail:
                    console.print(f"[red]    {line}[/]")

    console.print(
        f"\n[bold]Deployed: [green]{success}[/]/{len(projects)}[/]"
    )

    if success < len(projects):
        sys.exit(1)


# ─── workspace fix ────────────────────────────────────


@workspace.command(name="fix")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
@click.option("--name", default=None, help="Filter projects by name (regex)")
@click.option("--dry-run", is_flag=True, help="Show what would change without applying")
def workspace_fix(root, depth, name, dry_run):
    """Fix common errors in Taskfile.yml and app.doql.css across projects.

    \b
    Fixes applied:
    - Remove import-makefile-hint if no Makefile exists
    - Fill empty workflows (no step-1) from matching Taskfile task
    - Remove orphan workflows that don't correspond to any task
    - Add missing workflows for tasks that don't have one

    \b
    Examples:
        taskfile workspace fix --root /home/tom/github/semcod
        taskfile workspace fix --root . --dry-run
    """
    projects = _load_projects(root=root, depth=depth, name=name)

    if not projects:
        console.print("[yellow]No projects found[/]")
        return

    if dry_run:
        console.print("[yellow]DRY RUN — no changes will be written[/]\n")

    changed = 0
    for project in projects:
        if dry_run:
            # Simulate by copying files? For simplicity just analyze issues
            issues = validate_project(project)
            if issues:
                console.print(f"[cyan]{project.name}[/]: {'; '.join(issues)}")
                changed += 1
            continue

        result = fix_project(project)
        if result.changed:
            console.print(f"[green]{project.name}[/]: {result.summary()}")
            if result.removed_workflow_names:
                console.print(
                    f"[dim]    orphans: {result.removed_workflow_names}[/]"
                )
            changed += 1

    console.print(
        f"\n[bold]Fixed {changed}/{len(projects)} project(s)[/]"
    )


# ─── workspace analyze ────────────────────────────────


@workspace.command(name="analyze")
@click.option("--root", "-r", default=".", help="Base path to scan")
@click.option("--depth", "-d", default=2, type=int, help="Max scan depth")
@click.option("--output", "-o", default=None, help="Write CSV to file instead of stdout table")
def workspace_analyze(root, depth, output):
    """Analyze all projects and output metrics + issues + recommendations.

    \b
    Prints a table to stdout by default, or writes CSV with --output.

    \b
    Examples:
        taskfile workspace analyze --root /home/tom/github/semcod
        taskfile workspace analyze -r /home/tom/github/semcod -o analysis.csv
    """
    import csv

    projects = _load_projects(root=root, depth=depth)
    if not projects:
        console.print("[yellow]No projects found[/]")
        return

    analyses = [analyze_project(p) for p in projects]

    if output:
        fieldnames = [
            'path', 'name',
            'taskfile_tasks', 'taskfile_has_pipeline', 'taskfile_has_docker',
            'taskfile_has_environments',
            'doql_workflows', 'doql_has_deploy', 'has_git',
            'issues', 'recommendations',
        ]
        with open(output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for a in analyses:
                row = dict(a)
                row['issues'] = ' | '.join(row['issues'])
                row['recommendations'] = ' | '.join(row['recommendations'])
                writer.writerow(row)
        console.print(f"[green]Wrote CSV:[/] {output}  ({len(analyses)} rows)")
        return

    # Print table
    table = Table(title=f"Analysis — {len(analyses)} projects", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Project", style="green")
    table.add_column("Tasks", justify="right")
    table.add_column("Workflows", justify="right")
    table.add_column("Pipeline", justify="center")
    table.add_column("Issues", style="red")
    table.add_column("Recs", style="yellow")

    total_issues = 0
    total_recs = 0
    for i, a in enumerate(analyses, 1):
        total_issues += len(a['issues'])
        total_recs += len(a['recommendations'])
        issues_str = '; '.join(a['issues']) if a['issues'] else '—'
        recs_str = '; '.join(a['recommendations']) if a['recommendations'] else '—'
        if len(issues_str) > 40:
            issues_str = issues_str[:37] + '...'
        if len(recs_str) > 50:
            recs_str = recs_str[:47] + '...'
        table.add_row(
            str(i),
            a['name'],
            str(a['taskfile_tasks']),
            str(a['doql_workflows']),
            '✓' if a['taskfile_has_pipeline'] else '—',
            issues_str,
            recs_str,
        )

    console.print(table)
    console.print(
        f"\n[bold]{len(analyses)} projects · "
        f"[red]{total_issues} issues[/] · "
        f"[yellow]{total_recs} recommendations[/]"
    )
