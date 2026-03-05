"""Import external CI/CD configs, Makefiles, and shell scripts INTO Taskfile.yml format.

Supported sources:
  - GitHub Actions YAML (.github/workflows/*.yml)
  - GitLab CI YAML (.gitlab-ci.yml)
  - Makefile
  - Shell scripts (*.sh)
  - Dockerfile (extract build stages as tasks)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def import_file(source_path: str | Path, source_type: str | None = None) -> str:
    """Import a file and return Taskfile.yml content as string.

    Args:
        source_path: Path to the source file.
        source_type: One of: github-actions, gitlab-ci, makefile, shell, dockerfile.
                     Auto-detected if None.

    Returns:
        Generated Taskfile.yml content as YAML string.
    """
    path = Path(source_path)
    if not path.is_file():
        raise FileNotFoundError(f"Source file not found: {path}")

    if source_type is None:
        source_type = _detect_type(path)

    content = path.read_text(encoding="utf-8")

    if source_type == "github-actions":
        return _import_github_actions(content, path.name)
    elif source_type == "gitlab-ci":
        return _import_gitlab_ci(content)
    elif source_type == "makefile":
        return _import_makefile(content)
    elif source_type == "shell":
        return _import_shell_script(content, path.name)
    elif source_type == "dockerfile":
        return _import_dockerfile(content)
    else:
        raise ValueError(f"Unknown source type: {source_type}")


def _detect_type(path: Path) -> str:
    """Auto-detect source type from filename/path."""
    name = path.name.lower()
    if name == "makefile" or name == "gnumakefile":
        return "makefile"
    if name == ".gitlab-ci.yml" or name == ".gitlab-ci.yaml":
        return "gitlab-ci"
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "dockerfile"
    if name.endswith(".sh"):
        return "shell"
    # Check for GitHub Actions path pattern
    if ".github" in str(path) and name.endswith((".yml", ".yaml")):
        return "github-actions"
    if name.endswith((".yml", ".yaml")):
        # Try to detect from content
        content = path.read_text(encoding="utf-8")
        if "jobs:" in content and ("on:" in content or "workflow_dispatch" in content):
            return "github-actions"
        if "stages:" in content or "script:" in content:
            return "gitlab-ci"
    raise ValueError(f"Cannot detect source type for: {path.name}. Use --type to specify.")


# ─── GitHub Actions ──────────────────────────────────────────────────────

def _import_github_actions(content: str, filename: str) -> str:
    """Convert GitHub Actions workflow YAML to Taskfile.yml."""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("Invalid GitHub Actions YAML")

    workflow_name = data.get("name", filename.replace(".yml", ""))
    jobs = data.get("jobs", {})

    taskfile: dict[str, Any] = {
        "version": "1",
        "name": _slugify(workflow_name),
        "description": f"Imported from GitHub Actions: {filename}",
        "variables": {},
        "tasks": {},
    }

    # Extract env vars
    global_env = data.get("env", {})
    if global_env:
        taskfile["variables"] = {k: str(v) for k, v in global_env.items()}

    # Convert jobs to tasks
    pipeline_stages = []
    for job_name, job_data in jobs.items():
        if not isinstance(job_data, dict):
            continue

        steps = job_data.get("steps", [])
        cmds = []
        for step in steps:
            if isinstance(step, dict):
                if "run" in step:
                    run_cmd = step["run"].strip()
                    # Multi-line: take each line
                    for line in run_cmd.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            cmds.append(line)
                elif "uses" in step:
                    action = step["uses"]
                    step_name = step.get("name", action)
                    cmds.append(f"echo '[skip] GitHub Action: {step_name}'")

        deps = []
        needs = job_data.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        deps = [_slugify(n) for n in needs]

        task_name = _slugify(job_name)
        task: dict[str, Any] = {"desc": job_data.get("name", job_name)}
        if cmds:
            task["cmds"] = cmds
        if deps:
            task["deps"] = deps

        # Extract job env
        job_env = job_data.get("env", {})
        if job_env:
            for k, v in job_env.items():
                taskfile["variables"][k] = str(v)

        taskfile["tasks"][task_name] = task
        pipeline_stages.append(task_name)

    if pipeline_stages:
        taskfile["pipeline"] = {
            "stages": [{"name": s, "tasks": [s]} for s in pipeline_stages]
        }

    return _dump_taskfile(taskfile)


# ─── GitLab CI ──────────────────────────────────────────────────────────

def _import_gitlab_ci(content: str) -> str:
    """Convert .gitlab-ci.yml to Taskfile.yml."""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("Invalid GitLab CI YAML")

    taskfile: dict[str, Any] = {
        "version": "1",
        "name": "imported-gitlab-ci",
        "description": "Imported from .gitlab-ci.yml",
        "variables": {},
        "tasks": {},
    }

    # Extract global variables
    global_vars = data.get("variables", {})
    if global_vars:
        taskfile["variables"] = {k: str(v) for k, v in global_vars.items()}

    # Extract stages order
    stages_order = data.get("stages", [])

    # Reserved keys that are not jobs
    reserved = {"stages", "variables", "image", "before_script", "after_script",
                "cache", "services", "include", "default", "workflow", "pages"}

    pipeline_stages: dict[str, list[str]] = {}

    for job_name, job_data in data.items():
        if job_name in reserved or job_name.startswith("."):
            continue
        if not isinstance(job_data, dict):
            continue

        scripts = job_data.get("script", [])
        if isinstance(scripts, str):
            scripts = [scripts]

        before = data.get("before_script", [])
        if isinstance(before, str):
            before = [before]

        cmds = list(before) + list(scripts)

        task_name = _slugify(job_name)
        stage = job_data.get("stage", "")

        task: dict[str, Any] = {"desc": f"GitLab CI job: {job_name}"}
        if cmds:
            task["cmds"] = cmds
        if stage:
            task["stage"] = stage
            pipeline_stages.setdefault(stage, []).append(task_name)

        # Dependencies
        deps = job_data.get("needs", job_data.get("dependencies", []))
        if isinstance(deps, str):
            deps = [deps]
        if deps:
            task["deps"] = [_slugify(d) if isinstance(d, str) else _slugify(d.get("job", "")) for d in deps]

        taskfile["tasks"][task_name] = task

    # Build pipeline from stages
    if pipeline_stages or stages_order:
        ordered_stages = []
        for stage_name in stages_order:
            tasks = pipeline_stages.get(stage_name, [])
            if tasks:
                ordered_stages.append({"name": stage_name, "tasks": tasks})
        taskfile["pipeline"] = {"stages": ordered_stages}

    return _dump_taskfile(taskfile)


# ─── Makefile ────────────────────────────────────────────────────────────

def _import_makefile(content: str) -> str:
    """Convert Makefile to Taskfile.yml."""
    taskfile: dict[str, Any] = {
        "version": "1",
        "name": "imported-makefile",
        "description": "Imported from Makefile",
        "variables": {},
        "tasks": {},
    }

    # Extract variables (VAR = value or VAR := value)
    for match in re.finditer(r"^([A-Z_][A-Z0-9_]*)\s*[:?]?=\s*(.+)$", content, re.MULTILINE):
        taskfile["variables"][match.group(1)] = match.group(2).strip()

    # Extract targets
    # Match: target: [deps]
    #            command lines (tab-indented)
    target_re = re.compile(
        r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*([^\n]*)\n((?:\t[^\n]+\n?)*)",
        re.MULTILINE,
    )

    for match in target_re.finditer(content):
        name = match.group(1)
        deps_str = match.group(2).strip()
        body = match.group(3)

        # Skip .PHONY and other dot-targets
        if name.startswith("."):
            continue

        cmds = []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("@"):
                line = line[1:]
            if line:
                cmds.append(line)

        task: dict[str, Any] = {"desc": f"Make target: {name}"}
        if cmds:
            task["cmds"] = cmds

        deps = [d.strip() for d in deps_str.split() if d.strip() and not d.startswith(".")]
        if deps:
            task["deps"] = deps

        taskfile["tasks"][_slugify(name)] = task

    return _dump_taskfile(taskfile)


# ─── Shell Script ────────────────────────────────────────────────────────

def _import_shell_script(content: str, filename: str) -> str:
    """Convert a shell script to a Taskfile with functions as tasks."""
    taskfile: dict[str, Any] = {
        "version": "1",
        "name": f"imported-{Path(filename).stem}",
        "description": f"Imported from {filename}",
        "tasks": {},
    }

    # Extract shell functions
    func_re = re.compile(
        r"^(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*\{([^}]*)\}",
        re.MULTILINE | re.DOTALL,
    )

    for match in func_re.finditer(content):
        fn_name = match.group(1)
        fn_body = match.group(2).strip()
        cmds = [line.strip() for line in fn_body.splitlines() if line.strip() and not line.strip().startswith("#")]
        if cmds:
            taskfile["tasks"][_slugify(fn_name)] = {
                "desc": f"Shell function: {fn_name}",
                "cmds": cmds,
            }

    # If no functions found, treat the whole script as a single task
    if not taskfile["tasks"]:
        cmds = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("set "):
                cmds.append(line)
        if cmds:
            taskfile["tasks"]["main"] = {
                "desc": f"Imported from {filename}",
                "cmds": cmds,
            }

    return _dump_taskfile(taskfile)


# ─── Dockerfile ──────────────────────────────────────────────────────────

def _import_dockerfile(content: str) -> str:
    """Convert Dockerfile build stages to Taskfile tasks."""
    taskfile: dict[str, Any] = {
        "version": "1",
        "name": "imported-dockerfile",
        "description": "Imported from Dockerfile (build stages as tasks)",
        "tasks": {},
    }

    # Extract FROM stages
    stage_re = re.compile(r"^FROM\s+\S+(?:\s+AS\s+(\S+))?", re.MULTILINE | re.IGNORECASE)
    stages = []
    for match in stage_re.finditer(content):
        stage_name = match.group(1)
        if stage_name:
            stages.append(stage_name)

    if stages:
        for stage in stages:
            taskfile["tasks"][_slugify(stage)] = {
                "desc": f"Docker build stage: {stage}",
                "cmds": [f"docker build --target {stage} -t ${{IMAGE}}:{stage} ."],
            }
    else:
        taskfile["tasks"]["build"] = {
            "desc": "Docker build",
            "cmds": ["docker build -t ${IMAGE}:${TAG} ."],
        }
        taskfile["variables"] = {"IMAGE": "myapp", "TAG": "latest"}

    return _dump_taskfile(taskfile)


# ─── Helpers ─────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert a name to a valid task name slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "task"


def _dump_taskfile(data: dict) -> str:
    """Dump taskfile dict to YAML string with nice formatting."""
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
