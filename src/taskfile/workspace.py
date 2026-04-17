"""Workspace management — operations across multiple local projects.

Discovers projects within a given path (with depth limit), filters them by
manifest contents (Taskfile.yml tasks, app.doql.css workflows), and provides
group operations: run, doctor, validate, deploy, status.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Folders that should never be considered as projects
EXCLUDED_FOLDERS = frozenset({
    'venv', '.venv', 'node_modules', '__pycache__',
    '.git', '.idea', '.pytest_cache', '.ruff_cache',
    'dist', 'build', '.code2llm_cache',
    'oql-run-logs', 'iql-run-logs', 'refactor_output',
    'logs',
})

# Markers that identify a folder as a real project
PROJECT_MARKERS = (
    'pyproject.toml',
    'package.json',
    'Dockerfile',
    'setup.py',
    'Makefile',
    'Taskfile.yml',
)


@dataclass
class Project:
    """Representation of a discovered project."""

    path: Path
    name: str
    has_taskfile: bool = False
    has_doql: bool = False
    has_docker_compose: bool = False
    has_dockerfile: bool = False
    has_git: bool = False
    taskfile_tasks: list[str] = field(default_factory=list)
    doql_workflows: list[str] = field(default_factory=list)

    @property
    def has_task(self) -> bool:
        """Project has at least one task."""
        return bool(self.taskfile_tasks)

    def has_task_named(self, name: str) -> bool:
        """Check if a task with given name exists."""
        return name in self.taskfile_tasks

    def has_workflow_named(self, name: str) -> bool:
        """Check if a doql workflow with given name exists."""
        return name in self.doql_workflows


def _parse_taskfile_tasks(content: str) -> list[str]:
    """Extract task names from Taskfile.yml content (only from tasks: section)."""
    tasks: list[str] = []
    in_tasks = False
    for line in content.split('\n'):
        if line.rstrip() == 'tasks:':
            in_tasks = True
            continue
        if in_tasks:
            if re.match(r'^[a-z]', line) and not line.startswith(' '):
                break
            m = re.match(r'^  ([a-z][a-z0-9_-]*):', line)
            if m:
                tasks.append(m.group(1))
    return tasks


def _parse_doql_workflows(content: str) -> list[str]:
    """Extract workflow names from app.doql.css content."""
    return re.findall(r'workflow\[name="([^"]+)"\]', content)


def _is_project_folder(project_dir: Path) -> bool:
    """Determine if a folder is a real project (has build/config markers)."""
    for marker in PROJECT_MARKERS:
        if (project_dir / marker).exists():
            return True
    return False


def _analyze_project(project_dir: Path) -> Project:
    """Build a Project from a directory by inspecting its manifests."""
    project = Project(path=project_dir, name=project_dir.name)

    taskfile = project_dir / 'Taskfile.yml'
    doql = project_dir / 'app.doql.css'

    project.has_taskfile = taskfile.exists()
    project.has_doql = doql.exists()
    project.has_docker_compose = (project_dir / 'docker-compose.yml').exists()
    project.has_dockerfile = (project_dir / 'Dockerfile').exists()
    project.has_git = (project_dir / '.git').exists()

    if project.has_taskfile:
        try:
            project.taskfile_tasks = _parse_taskfile_tasks(taskfile.read_text())
        except OSError:
            pass

    if project.has_doql:
        try:
            project.doql_workflows = _parse_doql_workflows(doql.read_text())
        except OSError:
            pass

    return project


def discover_projects(
    root: Path,
    max_depth: int = 2,
) -> list[Project]:
    """Discover all project folders under `root` up to `max_depth` levels deep.

    Args:
        root: Base directory to start scanning.
        max_depth: Maximum recursion depth (1 = direct subdirs, 2 = subdirs of subdirs, etc.)

    Returns:
        List of Project objects for each discovered project, sorted by path.
    """
    projects: list[Project] = []
    root = root.resolve()

    def _walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.startswith('.'):
                continue
            if entry.name in EXCLUDED_FOLDERS:
                continue
            if _is_project_folder(entry):
                projects.append(_analyze_project(entry))
            elif depth < max_depth:
                # Dive deeper only if we haven't reached max depth
                _walk(entry, depth + 1)

    _walk(root, 1)
    # Deduplicate: when the same project name appears at different depths,
    # keep the shallowest copy (closest to root).
    seen: dict[str, Project] = {}
    for p in projects:
        depth = len(p.path.relative_to(root).parts)
        existing = seen.get(p.name)
        if existing is None:
            seen[p.name] = p
        else:
            existing_depth = len(existing.path.relative_to(root).parts)
            if depth < existing_depth:
                seen[p.name] = p
    projects = sorted(seen.values(), key=lambda p: str(p.path))
    return projects


def filter_projects(
    projects: list[Project],
    has_task: Optional[str] = None,
    has_workflow: Optional[str] = None,
    has_taskfile: Optional[bool] = None,
    has_doql: Optional[bool] = None,
    has_docker: Optional[bool] = None,
    name_pattern: Optional[str] = None,
) -> list[Project]:
    """Filter projects by various criteria."""
    result = projects

    if has_task is not None:
        result = [p for p in result if p.has_task_named(has_task)]

    if has_workflow is not None:
        result = [p for p in result if p.has_workflow_named(has_workflow)]

    if has_taskfile is not None:
        result = [p for p in result if p.has_taskfile == has_taskfile]

    if has_doql is not None:
        result = [p for p in result if p.has_doql == has_doql]

    if has_docker is not None:
        result = [
            p for p in result
            if (p.has_docker_compose or p.has_dockerfile) == has_docker
        ]

    if name_pattern:
        pattern_re = re.compile(name_pattern, re.IGNORECASE)
        result = [p for p in result if pattern_re.search(p.name)]

    return result


@dataclass
class CommandResult:
    """Result of running a command in a project."""

    project: Project
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


def run_in_project(
    project: Project,
    command: list[str],
    timeout: int = 300,
    capture: bool = True,
) -> CommandResult:
    """Run a shell command in a project directory."""
    cmd_str = ' '.join(command)
    try:
        result = subprocess.run(
            command,
            cwd=str(project.path),
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            project=project,
            command=cmd_str,
            returncode=result.returncode,
            stdout=result.stdout or '',
            stderr=result.stderr or '',
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            project=project,
            command=cmd_str,
            returncode=-1,
            stdout='',
            stderr=f'Timeout after {timeout}s',
        )
    except FileNotFoundError as exc:
        return CommandResult(
            project=project,
            command=cmd_str,
            returncode=-2,
            stdout='',
            stderr=f'Command not found: {exc}',
        )


def run_task_in_projects(
    projects: list[Project],
    task_name: str,
    timeout: int = 300,
) -> list[CommandResult]:
    """Run `taskfile <task_name>` in every project that has this task."""
    results = []
    for project in projects:
        if not project.has_task_named(task_name):
            continue
        result = run_in_project(
            project,
            ['taskfile', task_name],
            timeout=timeout,
        )
        results.append(result)
    return results


def parse_taskfile_task_commands(content: str) -> dict[str, list[str]]:
    """Extract task name -> list of commands from Taskfile.yml content."""
    tasks: dict[str, list[str]] = {}
    pattern = re.compile(
        r'^  ([a-z][a-z0-9_-]*):\s*\n'
        r'(?:    desc:[^\n]*\n)?'
        r'    cmds:\s*\n'
        r'((?:    - [^\n]+\n)+)',
        re.MULTILINE,
    )
    for match in pattern.finditer(content):
        name = match.group(1)
        cmds_block = match.group(2)
        cmds = re.findall(r'    - (.+)', cmds_block)
        cleaned = []
        for cmd in cmds:
            c = cmd.strip()
            if c.startswith("'") and c.endswith("'"):
                c = c[1:-1].replace("''", "'")
            elif c.startswith('"') and c.endswith('"'):
                c = c[1:-1]
            cleaned.append(c)
        tasks[name] = cleaned
    return tasks


@dataclass
class FixResult:
    """Result of applying fixes to a project."""

    project: Project
    filled_workflows: int = 0
    removed_orphan_workflows: int = 0
    added_missing_workflows: int = 0
    removed_import_hint: bool = False
    removed_workflow_names: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return (
            self.filled_workflows > 0
            or self.removed_orphan_workflows > 0
            or self.added_missing_workflows > 0
            or self.removed_import_hint
        )

    def summary(self) -> str:
        parts = []
        if self.removed_import_hint:
            parts.append("removed import-makefile-hint")
        if self.filled_workflows:
            parts.append(f"filled {self.filled_workflows} empty workflows")
        if self.removed_orphan_workflows:
            parts.append(f"removed {self.removed_orphan_workflows} orphan workflows")
        if self.added_missing_workflows:
            parts.append(f"added {self.added_missing_workflows} missing workflows")
        return ", ".join(parts) if parts else "no changes"


def _remove_import_makefile_hint(taskfile_path: Path) -> bool:
    """Remove import-makefile-hint task if no Makefile exists."""
    if not taskfile_path.exists():
        return False
    if (taskfile_path.parent / 'Makefile').exists():
        return False

    content = taskfile_path.read_text()
    if 'import-makefile-hint' not in content:
        return False

    pattern = re.compile(
        r'  import-makefile-hint:\s*\n'
        r'(?:    [^\n]*\n)+',
        re.MULTILINE,
    )
    new_content = pattern.sub('', content)
    if new_content != content:
        taskfile_path.write_text(new_content)
        return True
    return False


def _fix_doql_workflows(
    doql_path: Path,
    taskfile_tasks: dict[str, list[str]],
) -> tuple[int, list[str], int]:
    """Fill empty workflows, remove orphans, add missing.

    Returns: (filled_count, removed_names, added_count).
    """
    if not doql_path.exists():
        return 0, [], 0

    content = doql_path.read_text()
    original = content

    filled = 0
    removed_names: list[str] = []

    workflow_pattern = re.compile(
        r'workflow\[name="([^"]+)"\]\s*\{([^}]*)\}',
        re.DOTALL,
    )

    def replace_workflow(match: re.Match) -> str:
        nonlocal filled
        name = match.group(1)
        body = match.group(2)

        if 'step-1:' in body:
            return match.group(0)

        if name in taskfile_tasks:
            cmds = taskfile_tasks[name]
            if cmds:
                steps = '\n'.join(
                    f'  step-{i+1}: run cmd={cmd};' for i, cmd in enumerate(cmds)
                )
                filled += 1
                return (
                    f'workflow[name="{name}"] {{\n'
                    f'  trigger: "manual";\n'
                    f'{steps}\n'
                    f'}}'
                )

        removed_names.append(name)
        return ''

    content = workflow_pattern.sub(replace_workflow, content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip() + '\n'

    existing = set(re.findall(r'workflow\[name="([^"]+)"\]', content))

    added = 0
    missing = [
        t for t in taskfile_tasks
        if t not in existing and t != 'import-makefile-hint'
    ]
    if missing:
        new_workflows = []
        for task_name in missing:
            cmds = taskfile_tasks[task_name]
            if not cmds:
                continue
            steps = '\n'.join(
                f'  step-{i+1}: run cmd={cmd};' for i, cmd in enumerate(cmds)
            )
            new_workflows.append(
                f'workflow[name="{task_name}"] {{\n'
                f'  trigger: "manual";\n'
                f'{steps}\n'
                f'}}\n'
            )
            added += 1

        if new_workflows:
            if 'deploy {' in content:
                content = content.replace(
                    'deploy {',
                    '\n'.join(new_workflows) + '\ndeploy {',
                    1,
                )
            else:
                content = content.rstrip() + '\n\n' + '\n'.join(new_workflows)
            content = re.sub(r'\n{3,}', '\n\n', content)

    if content != original:
        doql_path.write_text(content)

    return filled, removed_names, added


def fix_project(project: Project) -> FixResult:
    """Fix errors in a project's Taskfile.yml and app.doql.css.

    - Remove import-makefile-hint if no Makefile exists
    - Fill empty workflows (no step-1) from matching Taskfile task
    - Remove orphan workflows that don't correspond to any task
    - Add missing workflows for tasks that don't have one
    """
    result = FixResult(project=project)

    taskfile = project.path / 'Taskfile.yml'
    doql = project.path / 'app.doql.css'

    if not taskfile.exists():
        return result

    if _remove_import_makefile_hint(taskfile):
        result.removed_import_hint = True

    tasks = parse_taskfile_task_commands(taskfile.read_text())

    if doql.exists():
        filled, removed, added = _fix_doql_workflows(doql, tasks)
        result.filled_workflows = filled
        result.removed_orphan_workflows = len(removed)
        result.removed_workflow_names = removed
        result.added_missing_workflows = added

    # Refresh project metadata after fixes
    updated = _analyze_project(project.path)
    project.taskfile_tasks = updated.taskfile_tasks
    project.doql_workflows = updated.doql_workflows

    return result


def analyze_project(project: Project) -> dict:
    """Analyze a project and return a dict of metrics + issues + recommendations."""
    taskfile = project.path / 'Taskfile.yml'
    doql = project.path / 'app.doql.css'

    issues: list[str] = []
    recommendations: list[str] = []

    # Taskfile analysis
    taskfile_tasks_count = len(project.taskfile_tasks)
    has_pipeline = False
    has_docker = False
    has_environments = False
    if taskfile.exists():
        content = taskfile.read_text()
        has_pipeline = 'pipeline:' in content
        has_docker = 'docker' in content.lower()
        has_environments = 'environments:' in content
        if taskfile_tasks_count < 3:
            issues.append("Very few tasks (<3)")
            recommendations.append("Add standard tasks: lint, test, build")
        if has_docker and 'health' not in content:
            recommendations.append("Add health check task")
        if taskfile_tasks_count > 10 and not has_pipeline:
            recommendations.append("Add pipeline section for CI/CD")
    else:
        issues.append("Missing Taskfile.yml")

    # doql analysis
    doql_workflows_count = len(project.doql_workflows)
    has_deploy = False
    if doql.exists():
        content = doql.read_text()
        has_deploy = 'deploy {' in content
        if 'app {' not in content:
            issues.append("Missing app { } section in doql")
        # Check for empty workflows
        for wf_match in re.finditer(
            r'workflow\[name="([^"]+)"\]\s*\{([^}]*)\}',
            content, re.DOTALL,
        ):
            wf_name, wf_body = wf_match.group(1), wf_match.group(2)
            if 'step-1:' not in wf_body and 'step-' not in wf_body:
                issues.append(f"Empty workflow '{wf_name}'")
    else:
        issues.append("Missing app.doql.css")

    # Sync check
    if taskfile.exists() and doql.exists():
        tf_set = set(project.taskfile_tasks)
        wf_set = set(project.doql_workflows)
        missing_in_doql = tf_set - wf_set - {'import-makefile-hint'}
        missing_in_tf = wf_set - tf_set
        if missing_in_doql:
            recommendations.append(
                f"Sync: {len(missing_in_doql)} tasks missing in doql.css"
            )
        if missing_in_tf:
            recommendations.append(
                f"Sync: {len(missing_in_tf)} workflows missing in Taskfile"
            )

    return {
        'path': str(project.path),
        'name': project.name,
        'taskfile_tasks': taskfile_tasks_count,
        'taskfile_has_pipeline': has_pipeline,
        'taskfile_has_docker': has_docker,
        'taskfile_has_environments': has_environments,
        'doql_workflows': doql_workflows_count,
        'doql_has_deploy': has_deploy,
        'has_git': project.has_git,
        'issues': issues,
        'recommendations': recommendations,
    }


def validate_project(project: Project) -> list[str]:
    """Run lightweight validation checks on a project. Returns list of issues."""
    issues = []

    if not project.has_taskfile:
        issues.append('Missing Taskfile.yml')
    elif not project.taskfile_tasks:
        issues.append('Taskfile.yml has no tasks')

    if project.has_doql:
        doql_path = project.path / 'app.doql.css'
        try:
            content = doql_path.read_text()
            # Check for empty workflows (no step-1)
            workflow_blocks = re.findall(
                r'workflow\[name="([^"]+)"\]\s*\{([^}]*(?:\n[^}]*)*)\}',
                content,
            )
            for name, body in workflow_blocks:
                if 'step-1:' not in body and 'step-' not in body:
                    issues.append(f"Empty workflow '{name}' without steps")
            # Check for app section
            if 'app {' not in content:
                issues.append('Missing app { } section in doql')
        except OSError:
            issues.append('Cannot read app.doql.css')

    return issues
