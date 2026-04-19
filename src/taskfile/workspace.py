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
EXCLUDED_FOLDERS = frozenset(
    {
        "venv",
        ".venv",
        "node_modules",
        "__pycache__",
        ".git",
        ".idea",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".code2llm_cache",
        "oql-run-logs",
        "iql-run-logs",
        "refactor_output",
        "logs",
    }
)

# Markers that identify a folder as a real project
PROJECT_MARKERS = (
    "pyproject.toml",
    "package.json",
    "Dockerfile",
    "setup.py",
    "Makefile",
    "Taskfile.yml",
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
    for line in content.split("\n"):
        if line.rstrip() == "tasks:":
            in_tasks = True
            continue
        if in_tasks:
            if re.match(r"^[a-z]", line) and not line.startswith(" "):
                break
            m = re.match(r"^  ([a-z][a-z0-9_-]*):", line)
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

    taskfile = project_dir / "Taskfile.yml"
    doql = project_dir / "app.doql.css"

    project.has_taskfile = taskfile.exists()
    project.has_doql = doql.exists()
    project.has_docker_compose = (project_dir / "docker-compose.yml").exists()
    project.has_dockerfile = (project_dir / "Dockerfile").exists()
    project.has_git = (project_dir / ".git").exists()

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
            if entry.name.startswith("."):
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


def _matches_task_filter(p: Project, task_name: str) -> bool:
    """Check if project has a specific task."""
    return p.has_task_named(task_name)


def _matches_workflow_filter(p: Project, workflow_name: str) -> bool:
    """Check if project has a specific workflow."""
    return p.has_workflow_named(workflow_name)


def _matches_docker_filter(p: Project, has_docker: bool) -> bool:
    """Check if project has docker (Dockerfile or compose)."""
    return (p.has_docker_compose or p.has_dockerfile) == has_docker


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
        result = [p for p in result if _matches_task_filter(p, has_task)]

    if has_workflow is not None:
        result = [p for p in result if _matches_workflow_filter(p, has_workflow)]

    if has_taskfile is not None:
        result = [p for p in result if p.has_taskfile == has_taskfile]

    if has_doql is not None:
        result = [p for p in result if p.has_doql == has_doql]

    if has_docker is not None:
        result = [p for p in result if _matches_docker_filter(p, has_docker)]

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
    cmd_str = " ".join(command)
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
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            project=project,
            command=cmd_str,
            returncode=-1,
            stdout="",
            stderr=f"Timeout after {timeout}s",
        )
    except FileNotFoundError as exc:
        return CommandResult(
            project=project,
            command=cmd_str,
            returncode=-2,
            stdout="",
            stderr=f"Command not found: {exc}",
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
            ["taskfile", task_name],
            timeout=timeout,
        )
        results.append(result)
    return results


def parse_taskfile_task_commands(content: str) -> dict[str, list[str]]:
    """Extract task name -> list of commands from Taskfile.yml content."""
    tasks: dict[str, list[str]] = {}
    pattern = re.compile(
        r"^  ([a-z][a-z0-9_-]*):\s*\n"
        r"(?:    desc:[^\n]*\n)?"
        r"    cmds:\s*\n"
        r"((?:    - [^\n]+\n)+)",
        re.MULTILINE,
    )
    for match in pattern.finditer(content):
        name = match.group(1)
        cmds_block = match.group(2)
        cmds = re.findall(r"    - (.+)", cmds_block)
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
    if (taskfile_path.parent / "Makefile").exists():
        return False

    content = taskfile_path.read_text()
    if "import-makefile-hint" not in content:
        return False

    pattern = re.compile(
        r"  import-makefile-hint:\s*\n"
        r"(?:    [^\n]*\n)+",
        re.MULTILINE,
    )
    new_content = pattern.sub("", content)
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

        if "step-1:" in body:
            return match.group(0)

        if name in taskfile_tasks:
            cmds = taskfile_tasks[name]
            if cmds:
                steps = "\n".join(f"  step-{i + 1}: run cmd={cmd};" for i, cmd in enumerate(cmds))
                filled += 1
                return f'workflow[name="{name}"] {{\n  trigger: "manual";\n{steps}\n}}'

        removed_names.append(name)
        return ""

    content = workflow_pattern.sub(replace_workflow, content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = content.strip() + "\n"

    existing = set(re.findall(r'workflow\[name="([^"]+)"\]', content))

    added = 0
    missing = [t for t in taskfile_tasks if t not in existing and t != "import-makefile-hint"]
    if missing:
        new_workflows = []
        for task_name in missing:
            cmds = taskfile_tasks[task_name]
            if not cmds:
                continue
            steps = "\n".join(f"  step-{i + 1}: run cmd={cmd};" for i, cmd in enumerate(cmds))
            new_workflows.append(
                f'workflow[name="{task_name}"] {{\n  trigger: "manual";\n{steps}\n}}\n'
            )
            added += 1

        if new_workflows:
            if "deploy {" in content:
                content = content.replace(
                    "deploy {",
                    "\n".join(new_workflows) + "\ndeploy {",
                    1,
                )
            else:
                content = content.rstrip() + "\n\n" + "\n".join(new_workflows)
            content = re.sub(r"\n{3,}", "\n\n", content)

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

    taskfile = project.path / "Taskfile.yml"
    doql = project.path / "app.doql.css"

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


@dataclass
class _TaskfileSimpleAnalysis:
    """Simple analysis results from a Taskfile."""

    has_pipeline: bool
    has_docker: bool
    has_environments: bool
    content: str


@dataclass
class _DoqlSimpleAnalysis:
    """Simple analysis results from a DOQL file."""

    has_deploy: bool
    has_app: bool
    empty_workflows: list[str]
    content: str


def _analyze_taskfile_simple(path: Path) -> _TaskfileSimpleAnalysis | None:
    """Analyze Taskfile and return simple metrics or None if missing."""
    if not path.exists():
        return None
    try:
        content = path.read_text()
        return _TaskfileSimpleAnalysis(
            has_pipeline="pipeline:" in content,
            has_docker="docker" in content.lower(),
            has_environments="environments:" in content,
            content=content,
        )
    except OSError:
        return None


def _analyze_doql_simple(path: Path) -> _DoqlSimpleAnalysis | None:
    """Analyze DOQL file and return simple metrics or None if missing."""
    if not path.exists():
        return None
    try:
        content = path.read_text()
        empty_workflows: list[str] = []
        for wf_match in re.finditer(
            r'workflow\[name="([^"]+)"\]\s*\{([^}]*)\}',
            content,
            re.DOTALL,
        ):
            wf_name, wf_body = wf_match.group(1), wf_match.group(2)
            if "step-1:" not in wf_body and "step-" not in wf_body:
                empty_workflows.append(wf_name)
        return _DoqlSimpleAnalysis(
            has_deploy="deploy {" in content,
            has_app="app {" in content,
            empty_workflows=empty_workflows,
            content=content,
        )
    except OSError:
        return None


def _check_sync(
    project: Project, tf: _TaskfileSimpleAnalysis | None, doql: _DoqlSimpleAnalysis | None
) -> list[str]:
    """Check sync between Taskfile and DOQL, return recommendations."""
    recommendations: list[str] = []
    if tf is None or doql is None:
        return recommendations
    tf_set = set(project.taskfile_tasks)
    wf_set = set(project.doql_workflows)
    missing_in_doql = tf_set - wf_set - {"import-makefile-hint"}
    missing_in_tf = wf_set - tf_set
    if missing_in_doql:
        recommendations.append(f"Sync: {len(missing_in_doql)} tasks missing in doql.css")
    if missing_in_tf:
        recommendations.append(f"Sync: {len(missing_in_tf)} workflows missing in Taskfile")
    return recommendations


def analyze_project(project: Project) -> dict:
    """Analyze a project and return a dict of metrics + issues + recommendations."""
    taskfile_path = project.path / "Taskfile.yml"
    doql_path = project.path / "app.doql.css"

    issues: list[str] = []
    recommendations: list[str] = []

    # Taskfile analysis
    tf = _analyze_taskfile_simple(taskfile_path)
    if tf is None:
        issues.append("Missing Taskfile.yml")
        tf_metrics = _TaskfileSimpleAnalysis(False, False, False, "")
    else:
        tf_metrics = tf
        task_count = len(project.taskfile_tasks)
        if task_count < 3:
            issues.append("Very few tasks (<3)")
            recommendations.append("Add standard tasks: lint, test, build")
        if tf.has_docker and "health" not in tf.content:
            recommendations.append("Add health check task")
        if task_count > 10 and not tf.has_pipeline:
            recommendations.append("Add pipeline section for CI/CD")

    # DOQL analysis
    doql = _analyze_doql_simple(doql_path)
    if doql is None:
        issues.append("Missing app.doql.css")
        doql_metrics = _DoqlSimpleAnalysis(False, False, [], "")
    else:
        doql_metrics = doql
        if not doql.has_app:
            issues.append("Missing app { } section in doql")
        for wf_name in doql.empty_workflows:
            issues.append(f"Empty workflow '{wf_name}'")

    # Sync check
    recommendations.extend(_check_sync(project, tf, doql))

    return {
        "path": str(project.path),
        "name": project.name,
        "taskfile_tasks": len(project.taskfile_tasks),
        "taskfile_has_pipeline": tf_metrics.has_pipeline,
        "taskfile_has_docker": tf_metrics.has_docker,
        "taskfile_has_environments": tf_metrics.has_environments,
        "doql_workflows": len(project.doql_workflows),
        "doql_has_deploy": doql_metrics.has_deploy,
        "has_git": project.has_git,
        "issues": issues,
        "recommendations": recommendations,
    }


@dataclass
class _PeerStats:
    """Statistics computed across all projects for comparison."""

    common_tasks: set[str]
    common_workflows: set[str]
    median_tasks: int
    median_workflows: int


@dataclass
class _DoqlAnalysis:
    """Analysis results from parsing a project's DOQL file."""

    entities: list[str]
    databases: list[str]
    interfaces: list[str]
    has_app: bool
    has_deploy: bool
    empty_workflows: list[str]


@dataclass
class _TaskfileAnalysis:
    """Analysis results from parsing a project's Taskfile."""

    has_pipeline: bool
    has_docker: bool
    has_environments: bool


def _compute_peer_stats(projects: list[Project], common_threshold: float) -> _PeerStats:
    """Compute common tasks/workflows and medians across all projects."""
    from collections import Counter
    from statistics import median

    task_freq: Counter[str] = Counter()
    workflow_freq: Counter[str] = Counter()
    for p in projects:
        for task in p.taskfile_tasks:
            task_freq[task] += 1
        for wf in p.doql_workflows:
            workflow_freq[wf] += 1

    threshold_count = max(2, int(len(projects) * common_threshold))
    common_tasks = {t for t, c in task_freq.items() if c >= threshold_count}
    common_workflows = {w for w, c in workflow_freq.items() if c >= threshold_count}

    task_counts = [len(p.taskfile_tasks) for p in projects]
    workflow_counts = [len(p.doql_workflows) for p in projects]
    median_tasks = int(median(task_counts)) if task_counts else 0
    median_workflows = int(median(workflow_counts)) if workflow_counts else 0

    return _PeerStats(common_tasks, common_workflows, median_tasks, median_workflows)


def _analyze_doql_structure(project: Project) -> _DoqlAnalysis:
    """Extract structural information from a project's DOQL file."""
    doql_path = project.path / "app.doql.css"
    if not doql_path.exists():
        return _DoqlAnalysis([], [], [], False, False, [])

    try:
        content = doql_path.read_text()
        entities = re.findall(r'entity\[name="([^"]+)"\]', content)
        databases = re.findall(r'database\[name="([^"]+)"\]', content)
        interfaces = re.findall(r'interface\[type="([^"]+)"\]', content)
        has_app = "app {" in content
        has_deploy = "deploy {" in content

        empty_workflows: list[str] = []
        for wf_m in re.finditer(
            r'workflow\[name="([^"]+)"\]\s*\{([^}]*)\}',
            content,
            re.DOTALL,
        ):
            if "step-1:" not in wf_m.group(2) and "step-" not in wf_m.group(2):
                empty_workflows.append(wf_m.group(1))

        return _DoqlAnalysis(entities, databases, interfaces, has_app, has_deploy, empty_workflows)
    except OSError:
        return _DoqlAnalysis([], [], [], False, False, [])


def _analyze_taskfile_structure(project: Project) -> _TaskfileAnalysis:
    """Extract structural information from a project's Taskfile."""
    taskfile_path = project.path / "Taskfile.yml"
    if not taskfile_path.exists():
        return _TaskfileAnalysis(False, False, False)

    try:
        content = taskfile_path.read_text()
        return _TaskfileAnalysis(
            has_pipeline="pipeline:" in content,
            has_docker="docker" in content.lower(),
            has_environments="environments:" in content,
        )
    except OSError:
        return _TaskfileAnalysis(False, False, False)


def _compute_missing_items(
    project: Project,
    stats: _PeerStats,
    project_tasks: set[str],
    project_workflows: set[str],
) -> tuple[set[str], list[str], list[str], list[str], list[str]]:
    """Compute missing common items and sync issues.
    Returns: (mkhint_exclude, missing_common_tasks, missing_common_workflows, missing_in_doql, orphan_workflows)
    """
    has_makefile = (project.path / "Makefile").exists()
    mkhint_exclude: set[str] = set() if has_makefile else {"import-makefile-hint"}
    missing_common_tasks = sorted((stats.common_tasks - project_tasks) - mkhint_exclude)
    missing_common_workflows = sorted((stats.common_workflows - project_workflows) - mkhint_exclude)
    missing_in_doql = sorted(project_tasks - project_workflows - {"import-makefile-hint"})
    orphan_workflows = sorted(project_workflows - project_tasks)
    return (
        mkhint_exclude,
        missing_common_tasks,
        missing_common_workflows,
        missing_in_doql,
        orphan_workflows,
    )


def _build_comparison_issues(
    project: Project,
    doql: _DoqlAnalysis,
    stats: _PeerStats,
    orphan_workflows: list[str],
    missing_in_doql: list[str],
) -> list[str]:
    """Build the issues list for comparison result."""
    issues: list[str] = []
    if not project.has_taskfile:
        issues.append("No Taskfile.yml")
    elif len(project.taskfile_tasks) < max(3, stats.median_tasks // 3):
        issues.append(f"Few tasks ({len(project.taskfile_tasks)} vs median {stats.median_tasks})")

    if not project.has_doql:
        issues.append("No app.doql.css")
    elif not doql.has_app:
        issues.append("Missing app { } section")

    if doql.empty_workflows:
        issues.append(f"{len(doql.empty_workflows)} empty workflow(s)")
    if orphan_workflows:
        issues.append(f"{len(orphan_workflows)} orphan workflow(s)")
    if missing_in_doql:
        issues.append(f"{len(missing_in_doql)} task(s) not mirrored in doql")
    return issues


def _build_comparison_recommendations(
    project: Project,
    doql: _DoqlAnalysis,
    tf: _TaskfileAnalysis,
    missing_common_tasks: list[str],
    missing_common_workflows: list[str],
) -> list[str]:
    """Build the recommendations list for comparison result."""
    recommendations: list[str] = []
    if missing_common_tasks:
        rec = f"Add common tasks: {', '.join(missing_common_tasks[:5])}"
        recommendations.append(rec + ("…" if len(missing_common_tasks) > 5 else ""))
    if missing_common_workflows:
        rec = f"Add common workflows: {', '.join(missing_common_workflows[:5])}"
        recommendations.append(rec + ("…" if len(missing_common_workflows) > 5 else ""))
    if tf.has_docker and "health" not in project.taskfile_tasks:
        recommendations.append("Add 'health' task for Docker services")
    if len(project.taskfile_tasks) > 10 and not tf.has_pipeline:
        recommendations.append("Add 'pipeline:' section for CI/CD")
    if doql.entities and not doql.databases:
        recommendations.append("Add database { } section for entities")
    if not doql.has_deploy and (tf.has_docker or "deploy" in project.taskfile_tasks):
        recommendations.append("Add deploy { } section in doql")
    return recommendations


def _build_comparison_result(
    project: Project,
    stats: _PeerStats,
    doql: _DoqlAnalysis,
    tf: _TaskfileAnalysis,
) -> dict:
    """Build the comparison result dict for a single project."""
    project_tasks = set(project.taskfile_tasks)
    project_workflows = set(project.doql_workflows)

    _, missing_common_tasks, missing_common_workflows, missing_in_doql, orphan_workflows = (
        _compute_missing_items(project, stats, project_tasks, project_workflows)
    )

    issues = _build_comparison_issues(project, doql, stats, orphan_workflows, missing_in_doql)
    recommendations = _build_comparison_recommendations(
        project, doql, tf, missing_common_tasks, missing_common_workflows
    )

    return {
        "path": str(project.path),
        "name": project.name,
        "taskfile_tasks": len(project.taskfile_tasks),
        "taskfile_has_pipeline": tf.has_pipeline,
        "taskfile_has_docker": tf.has_docker,
        "taskfile_has_environments": tf.has_environments,
        "doql_workflows": len(project.doql_workflows),
        "doql_entities": len(doql.entities),
        "doql_databases": len(doql.databases),
        "doql_interfaces": len(doql.interfaces),
        "doql_has_app": doql.has_app,
        "doql_has_deploy": doql.has_deploy,
        "median_tasks": stats.median_tasks,
        "median_workflows": stats.median_workflows,
        "tasks_vs_median": len(project.taskfile_tasks) - stats.median_tasks,
        "workflows_vs_median": len(project.doql_workflows) - stats.median_workflows,
        "empty_workflows": doql.empty_workflows,
        "orphan_workflows": orphan_workflows,
        "tasks_missing_in_doql": missing_in_doql,
        "missing_common_tasks": missing_common_tasks,
        "missing_common_workflows": missing_common_workflows,
        "issues": issues,
        "recommendations": recommendations,
        "has_git": project.has_git,
    }


def compare_projects(projects: list[Project], common_threshold: float = 0.5) -> list[dict]:
    """Compare projects against each other (peer benchmarking).

    For each project, compute:
    - Tasks missing from this project that are "common" (present in >= threshold of peers)
    - Workflows missing from this project that are "common"
    - DOQL entity/database/interface counts vs median
    - Sync issues between Taskfile and doql
    - Improvement suggestions based on comparison

    Args:
        projects: List of Project objects to compare.
        common_threshold: Fraction of projects required to consider a task/workflow "common"
                          (default 0.5 = present in at least half of projects).

    Returns:
        List of dicts, one per project, with comparison metrics.
    """
    if not projects:
        return []

    stats = _compute_peer_stats(projects, common_threshold)
    results = []
    for project in projects:
        doql = _analyze_doql_structure(project)
        tf = _analyze_taskfile_structure(project)
        results.append(_build_comparison_result(project, stats, doql, tf))
    return results


def validate_project(project: Project) -> list[str]:
    """Run lightweight validation checks on a project. Returns list of issues."""
    issues = []

    if not project.has_taskfile:
        issues.append("Missing Taskfile.yml")
    elif not project.taskfile_tasks:
        issues.append("Taskfile.yml has no tasks")

    if project.has_doql:
        doql_path = project.path / "app.doql.css"
        try:
            content = doql_path.read_text()
            # Check for empty workflows (no step-1)
            workflow_blocks = re.findall(
                r'workflow\[name="([^"]+)"\]\s*\{([^}]*(?:\n[^}]*)*)\}',
                content,
            )
            for name, body in workflow_blocks:
                if "step-1:" not in body and "step-" not in body:
                    issues.append(f"Empty workflow '{name}' without steps")
            # Check for app section
            if "app {" not in content:
                issues.append("Missing app { } section in doql")
        except OSError:
            issues.append("Cannot read app.doql.css")

    return issues
