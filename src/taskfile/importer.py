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


_FILENAME_TYPE_MAP: dict[str, str] = {
    "makefile": "makefile",
    "gnumakefile": "makefile",
    ".gitlab-ci.yml": "gitlab-ci",
    ".gitlab-ci.yaml": "gitlab-ci",
}


def _detect_type_from_yaml_content(path: Path) -> str:
    """Detect source type by inspecting YAML file content."""
    content = path.read_text(encoding="utf-8")
    if "jobs:" in content and ("on:" in content or "workflow_dispatch" in content):
        return "github-actions"
    if "stages:" in content or "script:" in content:
        return "gitlab-ci"
    raise ValueError(f"Cannot detect source type for: {path.name}. Use --type to specify.")


def _detect_type(path: Path) -> str:
    """Auto-detect source type from filename/path."""
    name = path.name.lower()

    # Exact filename match
    if name in _FILENAME_TYPE_MAP:
        return _FILENAME_TYPE_MAP[name]

    # Dockerfile variants
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "dockerfile"

    # Extension-based
    if name.endswith(".sh"):
        return "shell"

    # GitHub Actions path pattern
    if ".github" in str(path) and name.endswith((".yml", ".yaml")):
        return "github-actions"

    # Fallback: inspect YAML content
    if name.endswith((".yml", ".yaml")):
        return _detect_type_from_yaml_content(path)

    raise ValueError(f"Cannot detect source type for: {path.name}. Use --type to specify.")


# ─── GitHub Actions ──────────────────────────────────────────────────────


def _extract_gh_steps_as_commands(steps: list) -> list[str]:
    """Extract commands from GitHub Actions steps."""
    cmds = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if "run" in step:
            for line in step["run"].strip().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    cmds.append(line)
        elif "uses" in step:
            step_name = step.get("name", step["uses"])
            cmds.append(f"echo '[skip] GitHub Action: {step_name}'")
    return cmds


def _extract_gh_job_deps(job_data: dict) -> list[str]:
    """Extract dependency slugs from a GitHub Actions job."""
    needs = job_data.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    return [_slugify(n) for n in needs]


def _convert_gh_job_to_task(
    job_name: str, job_data: dict, variables: dict
) -> tuple[str, dict[str, Any]]:
    """Convert a single GitHub Actions job to a Taskfile task. Returns (task_name, task_dict)."""
    cmds = _extract_gh_steps_as_commands(job_data.get("steps", []))
    deps = _extract_gh_job_deps(job_data)

    task_name = _slugify(job_name)
    task: dict[str, Any] = {"desc": job_data.get("name", job_name)}
    if cmds:
        task["cmds"] = cmds
    if deps:
        task["deps"] = deps

    # Extract job env into shared variables
    job_env = job_data.get("env", {})
    if job_env:
        for k, v in job_env.items():
            variables[k] = str(v)

    return task_name, task


def parse_github_actions(content: str, filename: str = "workflow.yml") -> dict:
    """Parse GitHub Actions workflow YAML into a Taskfile dict."""
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

    # Extract global env vars
    global_env = data.get("env", {})
    if global_env:
        taskfile["variables"] = {k: str(v) for k, v in global_env.items()}

    # Convert jobs to tasks
    pipeline_stages = []
    for job_name, job_data in jobs.items():
        if not isinstance(job_data, dict):
            continue
        task_name, task = _convert_gh_job_to_task(job_name, job_data, taskfile["variables"])
        taskfile["tasks"][task_name] = task
        pipeline_stages.append(task_name)

    if pipeline_stages:
        taskfile["pipeline"] = {"stages": [{"name": s, "tasks": [s]} for s in pipeline_stages]}

    return taskfile


def _import_github_actions(content: str, filename: str) -> str:
    """Convert GitHub Actions workflow YAML to Taskfile.yml."""
    return _dump_taskfile(parse_github_actions(content, filename))


# ─── GitLab CI ──────────────────────────────────────────────────────────

_GL_RESERVED_KEYS = frozenset(
    {
        "stages",
        "variables",
        "image",
        "before_script",
        "after_script",
        "cache",
        "services",
        "include",
        "default",
        "workflow",
        "pages",
    }
)


def _extract_gl_job_commands(job_data: dict, global_before_script: list) -> list[str]:
    """Extract commands from a GitLab CI job, prepending global before_script."""
    scripts = job_data.get("script", [])
    if isinstance(scripts, str):
        scripts = [scripts]
    return list(global_before_script) + list(scripts)


def _extract_gl_job_deps(job_data: dict) -> list[str]:
    """Extract dependency slugs from a GitLab CI job."""
    deps = job_data.get("needs", job_data.get("dependencies", []))
    if isinstance(deps, str):
        deps = [deps]
    return (
        [_slugify(d) if isinstance(d, str) else _slugify(d.get("job", "")) for d in deps]
        if deps
        else []
    )


def _build_gl_task(
    taskfile: dict, pipeline_stages: dict, job_name: str, job_data: dict, before: list
) -> None:
    """Convert a single GitLab CI job into a Taskfile task entry."""
    cmds = _extract_gl_job_commands(job_data, before)
    task_name = _slugify(job_name)
    stage = job_data.get("stage", "")

    task: dict[str, Any] = {"desc": f"GitLab CI job: {job_name}"}
    if cmds:
        task["cmds"] = cmds
    if stage:
        task["stage"] = stage
        pipeline_stages.setdefault(stage, []).append(task_name)

    deps = _extract_gl_job_deps(job_data)
    if deps:
        task["deps"] = deps

    taskfile["tasks"][task_name] = task


def _build_gl_pipeline(taskfile: dict, pipeline_stages: dict, stages_order: list) -> None:
    """Build the pipeline section from collected stages."""
    if not pipeline_stages and not stages_order:
        return
    ordered_stages = [
        {"name": stage_name, "tasks": pipeline_stages.get(stage_name, [])}
        for stage_name in stages_order
        if pipeline_stages.get(stage_name)
    ]
    taskfile["pipeline"] = {"stages": ordered_stages}


def parse_gitlab_ci(content: str) -> dict:
    """Parse .gitlab-ci.yml into a Taskfile dict."""
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

    stages_order = data.get("stages", [])
    before = data.get("before_script", [])
    if isinstance(before, str):
        before = [before]

    pipeline_stages: dict[str, list[str]] = {}

    for job_name, job_data in data.items():
        if job_name in _GL_RESERVED_KEYS or job_name.startswith("."):
            continue
        if not isinstance(job_data, dict):
            continue
        _build_gl_task(taskfile, pipeline_stages, job_name, job_data, before)

    _build_gl_pipeline(taskfile, pipeline_stages, stages_order)

    return taskfile


def _import_via_parser(parser_fn, content: str) -> str:
    """Generic importer: parse content with given parser, then dump to YAML."""
    return _dump_taskfile(parser_fn(content))


def _import_gitlab_ci(content: str) -> str:
    """Convert .gitlab-ci.yml to Taskfile.yml."""
    return _import_via_parser(parse_gitlab_ci, content)


# ─── Makefile ────────────────────────────────────────────────────────────


def parse_makefile(content: str) -> dict:
    """Parse Makefile into a Taskfile dict."""
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
    # NOTE: ``[ \t]*`` — horizontal whitespace only. Using ``\s*`` here lets
    # the regex consume the newline + tab of the first recipe line and pull
    # the first command into the ``deps`` capture, dropping it from ``cmds``.
    # ``(?!=)`` — reject ``VAR := value`` / ``VAR ?= value`` variable
    # assignments which otherwise collide with the target pattern.
    target_re = re.compile(
        r"^([a-zA-Z_][a-zA-Z0-9_-]*)[ \t]*:(?!=)[ \t]*([^\n]*)\n((?:\t[^\n]+\n?)*)",
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

    return taskfile


def _import_makefile(content: str) -> str:
    """Convert Makefile to Taskfile.yml."""
    return _import_via_parser(parse_makefile, content)


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
        cmds = [
            line.strip()
            for line in fn_body.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
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
