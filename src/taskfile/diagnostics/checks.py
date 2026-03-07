"""Pure diagnostic check functions — each returns list[Issue], no side effects.

Layer 1: check_preflight         — tools exist?
Layer 2: check_taskfile          — YAML valid?
Layer 3: check_env_files, check_unresolved_variables, check_ports,
         check_dependent_files, check_docker, check_ssh_keys,
         check_ssh_connectivity, check_git, check_task_commands
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


def _load_dotenv_vars(env_file_path: Path) -> dict[str, str]:
    """Parse a .env file and return key=value pairs (no shell export)."""
    result: dict[str, str] = {}
    if not env_file_path.exists():
        return result
    for line in env_file_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            result[key] = val
    return result


def _resolve_env_fields(env, taskfile_dir: Path | None = None) -> None:
    """Expand ${VAR:-default} in environment string fields.

    Mirrors the runner's dotenv loading: auto-loads .env and .env.local
    from taskfile_dir, then the environment's .env file, then os.environ.
    This ensures variables like PROD_HOST are available even when not
    exported in the shell.
    """
    from taskfile.compose import resolve_variables as _compose_resolve_variables

    # Build context: .env file vars → os.environ (shell overrides file)
    ctx: dict[str, str] = {}

    # Auto-load .env and .env.local from taskfile dir (matches runner behaviour)
    base_dir = taskfile_dir or Path.cwd()
    for dotenv_name in (".env", ".env.local"):
        dotenv_path = base_dir / dotenv_name
        if dotenv_path.is_file():
            ctx.update(_load_dotenv_vars(dotenv_path))

    # Load environment-specific .env file if set
    env_file = getattr(env, "env_file", None)
    if env_file:
        env_path = base_dir / env_file
        if env_path.is_file():
            ctx.update(_load_dotenv_vars(env_path))

    # Shell env overrides file values
    ctx.update(os.environ)

    for field_name in (
        "ssh_host", "ssh_user", "ssh_key",
        "compose_command", "container_runtime", "service_manager",
        "env_file", "compose_file", "quadlet_dir", "quadlet_remote_dir",
    ):
        value = getattr(env, field_name, None)
        if isinstance(value, str) and ("${" in value or "$" in value):
            setattr(env, field_name, _compose_resolve_variables(value, ctx))


# ─── Layer 1: Preflight ──────────────────────────────────────────


def check_preflight() -> list[Issue]:
    """Check if required/common tools are available on the system."""
    issues: list[Issue] = []
    tools = [
        ("python3", True),
        ("docker", False),
        ("podman", False),
        ("git", True),
        ("ssh", True),
        ("ssh-copy-id", False),
        ("rsync", False),
    ]
    for binary, required in tools:
        if shutil.which(binary):
            continue
        if required:
            severity = SEVERITY_ERROR if binary in ("python3", "git") else SEVERITY_WARNING
            teach_text = {
                "python3": "Python is the runtime for Taskfile itself. Install it via your package manager or from python.org.",
                "git": "Git tracks code changes and is used by Taskfile for versioning and deployment tracking. Install it to enable version control features.",
                "ssh": "SSH is required for remote deployments (@remote commands). Install openssh-client to enable deploying to remote servers.",
            }.get(binary, f"{binary} is required for this Taskfile. Install it with your package manager.")
            issues.append(Issue(
                category=IssueCategory.DEPENDENCY_MISSING,
                message=f"{binary}: not found in PATH",
                fix_strategy=FixStrategy.MANUAL,
                severity=severity,
                fix_description=f"Install {binary} (e.g. apt install {binary})",
                teach=teach_text,
                layer=1,
            ))
        else:
            teach_optional = {
                "docker": "Docker is a container runtime. If your Taskfile uses 'docker compose', install Docker or use Podman as alternative.",
                "podman": "Podman is a Docker alternative. If your Taskfile uses containers but you prefer rootless operation, install Podman.",
                "ssh-copy-id": "ssh-copy-id copies SSH keys to remote servers. Required for initial SSH setup before remote deployment.",
                "rsync": "rsync efficiently syncs files to remote servers. Useful for deployment tasks with file transfers.",
            }.get(binary, f"{binary} is optional but recommended for some Taskfile features.")
            install_hint = {
                "docker": "apt install docker.io docker-compose-v2  # https://docs.docker.com/engine/install/",
                "podman": "apt install podman  # https://podman.io/docs/installation",
                "ssh-copy-id": "apt install openssh-client",
                "rsync": "apt install rsync",
            }.get(binary, f"apt install {binary}")
            issues.append(Issue(
                category=IssueCategory.DEPENDENCY_MISSING,
                message=f"{binary}: not found (optional)",
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_INFO,
                fix_description=f"Install: {install_hint}",
                teach=teach_optional,
                layer=1,
            ))
    return issues


# ─── Layer 2: Validation ─────────────────────────────────────────


def check_taskfile() -> list[Issue]:
    """Check if Taskfile.yml exists and is valid YAML."""
    from taskfile.parser import find_taskfile, load_taskfile, TaskfileNotFoundError

    issues: list[Issue] = []
    try:
        path = find_taskfile()
    except TaskfileNotFoundError:
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message="Taskfile.yml not found",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_ERROR,
            fix_command="taskfile init --template minimal",
            fix_description="Create a Taskfile.yml from template",
            layer=2,
        ))
        return issues
    try:
        load_taskfile(path)
    except Exception as e:
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message=f"Taskfile.yml parse error: {e}",
            fix_strategy=FixStrategy.MANUAL,
            severity=SEVERITY_ERROR,
            fix_description="Fix YAML syntax in Taskfile.yml",
            layer=2,
        ))
    return issues


# ─── Layer 3: Environment & Infrastructure ────────────────────────


def check_env_files() -> list[Issue]:
    """Check local .env files for common problems."""
    issues: list[Issue] = []
    for env_file in [".env", ".env.local", ".env.prod"]:
        env_path = Path(env_file).resolve()
        if not env_path.exists():
            continue
        content = env_path.read_text()

        # Check for empty API keys
        if "OPENROUTER_API_KEY=" in content and "OPENROUTER_API_KEY=\n" in content:
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"{env_path}: OPENROUTER_API_KEY is empty",
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_WARNING,
                fix_description=f"Get key from https://openrouter.ai/settings/keys and set in {env_path}",
                layer=3,
            ))

        # Check for incorrect PORT variable names
        for line in content.splitlines():
            if line.startswith("PORT=") and not line.startswith("PORT_"):
                issues.append(Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"{env_path}: Use PORT_WEB or PORT_LANDING instead of PORT",
                    fix_strategy=FixStrategy.AUTO,
                    severity=SEVERITY_WARNING,
                    fix_description=f"Rename PORT= to PORT_WEB= in {env_path}",
                    layer=3,
                ))
                break
    return issues


def _collect_required_vars(config: "TaskfileConfig") -> set[str]:
    """Collect all ${VAR} references from config variables and SSH fields."""
    required_vars: set[str] = set()
    # From global variables
    for var_value in (config.variables or {}).values():
        if isinstance(var_value, str):
            refs = re.findall(r'\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-[^}]*)?\}', var_value)
            required_vars.update(refs)
    # From SSH config in environments
    for env_name, env_obj in (config.environments or {}).items():
        for field_name in ("ssh_host", "ssh_user", "ssh_key"):
            value = getattr(env_obj, field_name, None) or ""
            if isinstance(value, str) and value.startswith("${"):
                m = re.match(r'\$\{(?P<var>[A-Za-z_][A-Za-z0-9_]*)', value)
                if m:
                    required_vars.add(m.group("var"))
    return required_vars


def _check_env_file_vars(env_file: str, required_vars: set[str]) -> list[Issue]:
    """Check a single .env file for missing or empty required variables."""
    issues: list[Issue] = []
    env_path = Path(env_file).resolve()
    if not env_path.exists():
        return issues
    env_content = env_path.read_text()
    env_vars: set[str] = set()
    for line in env_content.splitlines():
        if "=" in line and not line.startswith("#"):
            env_vars.add(line.split("=", 1)[0].strip())
    for var in required_vars:
        if var not in env_vars:
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"{env_path}: Missing required variable {var}",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_WARNING,
                fix_description=f"Set {var} in {env_path}",
                teach=(
                    f"Variable {var} is referenced in Taskfile but not defined in {env_path}. "
                    "Add it to the env file with a real value."
                ),
                layer=3,
            ))
        elif f"{var}=\n" in env_content or f"{var}=\r\n" in env_content:
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"{env_path}: {var} is empty",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_WARNING,
                fix_description=f"Set value for {var} in {env_path}",
                teach=(
                    f"Variable {var} exists in {env_path} but has no value. "
                    "Set it to a real value before running the task."
                ),
                layer=3,
            ))
    return issues


def check_unresolved_variables(config: "TaskfileConfig") -> list[Issue]:
    """Find ${VAR} references without values — most common problem from TEST_REPORT."""
    required_vars = _collect_required_vars(config)
    if not required_vars:
        return []
    issues: list[Issue] = []
    for env_file in [".env", ".env.local", ".env.prod", ".env.staging"]:
        issues.extend(_check_env_file_vars(env_file, required_vars))
    return issues


def check_ports() -> list[Issue]:
    """Check docker-compose port conflicts and suggest .env fixes."""
    from taskfile.diagnostics.checks_ports import check_ports as _check_ports
    return _check_ports()


def _check_script_files(config: "TaskfileConfig", taskfile_dir: Path) -> list[Issue]:
    """Check that all script: references point to existing files."""
    issues: list[Issue] = []
    for task_name, task in config.tasks.items():
        if not task.script:
            continue
        script_path = (taskfile_dir / task.script).resolve()
        if not script_path.exists():
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"Task '{task_name}' script not found: {script_path}",
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_ERROR,
                fix_description=f"Create the script file: {script_path}",
                teach=(
                    "The 'script:' directive runs an external script file. "
                    "If the file doesn't exist, create it or use 'cmds:' "
                    "with inline commands instead of 'script:'."
                ),
                layer=3,
            ))
    return issues


def _check_env_files(config: "TaskfileConfig", taskfile_dir: Path) -> list[Issue]:
    """Check that environment files referenced in env.env_file exist."""
    issues: list[Issue] = []
    for env_name, env in config.environments.items():
        if env.env_file:
            env_file_path = (taskfile_dir / env.env_file).resolve()
            if not env_file_path.exists():
                example_path = (taskfile_dir / f"{env.env_file}.example").resolve()
                if example_path.exists():
                    issues.append(Issue(
                        category=IssueCategory.CONFIG_ERROR,
                        message=f"Environment '{env_name}' env_file not found: {env_file_path}",
                        fix_strategy=FixStrategy.AUTO,
                        severity=SEVERITY_WARNING,
                        fix_command=f"cp {example_path} {env_file_path}",
                        fix_description=f"Copy {example_path} → {env_file_path}",
                        context={"env_file": str(env_file_path), "example": str(example_path)},
                        teach=(
                            "Environment files (.env) contain variables specific to each environment "
                            "(passwords, addresses, keys). Create one from .env.example as a template."
                        ),
                        layer=3,
                    ))
                else:
                    issues.append(Issue(
                        category=IssueCategory.CONFIG_ERROR,
                        message=f"Environment '{env_name}' env_file not found: {env_file_path}",
                        fix_strategy=FixStrategy.MANUAL,
                        severity=SEVERITY_WARNING,
                        fix_description=f"Create {env_file_path} with required variables",
                        teach=(
                            "Environment files (.env) contain variables specific to each environment "
                            "(passwords, addresses, keys). Each environment in Taskfile can have its own "
                            ".env file."
                        ),
                        layer=3,
                    ))
    return issues


def _check_circular_deps(config: "TaskfileConfig") -> list[Issue]:
    """Check for circular dependencies in task definitions."""
    issues: list[Issue] = []
    from taskfile.parser import validate_taskfile
    for warning in validate_taskfile(config):
        if "Circular dependency" in warning:
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=warning,
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_ERROR,
                fix_description="Break the circular dependency in Taskfile.yml",
                layer=2,
            ))
    return issues


def check_dependent_files(config: "TaskfileConfig") -> list[Issue]:
    """Check that all files referenced in Taskfile (scripts, env_files) exist."""
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    return (
        _check_script_files(config, taskfile_dir) +
        _check_env_files(config, taskfile_dir) +
        _check_circular_deps(config)
    )


# ─── Registry access (delegated to checks_registry.py) ────────────

from taskfile.diagnostics.checks_registry import (  # noqa: E402, F401
    _extract_registry_host,
    _check_registry_reachable,
    _is_image_var,
    _collect_image_vars_from_config,
    _collect_image_vars_from_envs,
    _collect_image_vars_from_compose,
    _group_by_registry,
    _build_unreachable_registry_issue,
    check_registry_access,
)


def check_docker() -> list[Issue]:
    """Check if Docker is available."""
    issues: list[Issue] = []
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append(Issue(
            category=IssueCategory.DEPENDENCY_MISSING,
            message="Docker not installed or not running",
            fix_strategy=FixStrategy.MANUAL,
            severity=SEVERITY_WARNING,
            fix_description="Install Docker: https://docs.docker.com/get-docker/",
            teach=(
                "Docker is a container runtime used by most Taskfile projects. "
                "If your Taskfile uses 'docker compose' commands, Docker must be installed. "
                "Alternatively, use Podman as a drop-in replacement."
            ),
            layer=1,
        ))
    return issues


def check_ssh_keys() -> list[Issue]:
    """Check SSH keys exist."""
    from taskfile.diagnostics.checks_ssh import check_ssh_keys as _check_ssh_keys
    return _check_ssh_keys()


def check_ssh_connectivity(config: "TaskfileConfig") -> list[Issue]:
    """Check SSH connectivity — distinguish: missing key vs refused vs auth fail."""
    from taskfile.diagnostics.checks_ssh import check_ssh_connectivity as _check
    return _check(config)


def check_remote_health(config: "TaskfileConfig") -> list[Issue]:
    """Check remote host health — podman, disk space, container status."""
    from taskfile.diagnostics.checks_ssh import check_remote_health as _check
    return _check(config)


def check_git() -> list[Issue]:
    """Check if in git repo."""
    issues: list[Issue] = []
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message="Not a git repository",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_INFO,
            fix_command="git init",
            teach=(
                "Git tracks changes to your code. While not required for Taskfile, "
                "it's recommended for version control. Run 'git init' to start tracking "
                "changes, then 'git add' and 'git commit' to save your work."
            ),
            layer=3,
        ))
    return issues


def check_task_commands(config: "TaskfileConfig") -> list[Issue]:
    """Check if commands in tasks reference existing binaries."""
    from taskfile.compose import resolve_variables as _compose_resolve_variables

    # Build variable context for resolving ${COMPOSE} etc.
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    var_ctx: dict[str, str] = {}
    for dotenv_name in (".env", ".env.local"):
        dotenv_path = taskfile_dir / dotenv_name
        if dotenv_path.is_file():
            var_ctx.update(_load_dotenv_vars(dotenv_path))
    var_ctx.update(config.variables)
    var_ctx.update(os.environ)

    issues: list[Issue] = []
    for task_name, task in config.tasks.items():
        for cmd in task.commands:
            resolved_cmd = _compose_resolve_variables(cmd, var_ctx)
            binary = _extract_binary(resolved_cmd)
            if binary and not shutil.which(binary) and not binary.startswith("@"):
                issues.append(Issue(
                    category=IssueCategory.DEPENDENCY_MISSING,
                    message=f"Task '{task_name}': command '{binary}' not found",
                    fix_strategy=FixStrategy.LLM,
                    severity=SEVERITY_WARNING,
                    context={"binary": binary, "task": task_name, "cmd": cmd},
                    teach=(
                        f"The command '{binary}' is used in your Taskfile but not "
                        "installed on your system. Each tool in 'cmds:' must be available. "
                        "Install missing tools with your package manager (apt, brew, etc.)."
                    ),
                    layer=3,
                ))
    return issues


def check_examples(examples_dir: Path) -> list[dict]:
    """Validate all example directories. Returns list of result dicts."""
    from taskfile.parser import load_taskfile

    results: list[dict] = []
    if not examples_dir.is_dir():
        return results

    for child in sorted(examples_dir.iterdir()):
        if not child.is_dir():
            continue
        taskfile_path = child / "Taskfile.yml"
        if not taskfile_path.exists():
            taskfile_path = child / "Taskfile.yaml"
        if not taskfile_path.exists():
            continue

        entry: dict = {
            "name": child.name, "valid": True, "tasks": 0,
            "envs": 0, "missing_env_files": [], "errors": [],
        }
        try:
            cfg = load_taskfile(taskfile_path)
            entry["tasks"] = len(cfg.tasks)
            entry["envs"] = len(cfg.environments)
            for env_name, env in cfg.environments.items():
                if env.env_file:
                    if not (child / env.env_file).exists():
                        entry["missing_env_files"].append(env.env_file)
        except Exception as e:
            entry["valid"] = False
            entry["errors"].append(str(e))
        results.append(entry)
    return results


# ─── Placeholder/env validation (delegated to checks_placeholders.py) ────────

from taskfile.diagnostics.checks_placeholders import (  # noqa: E402, F401
    PLACEHOLDER_PATTERNS,
    _load_env_file_vars,
    _extract_fields_to_check,
    _is_placeholder,
    _should_skip_placeholder,
    _check_env_placeholders,
    check_placeholder_values,
    _check_env_file_for_target,
)


def _check_tasks_and_deps(
    config: "TaskfileConfig",
    task_names: list[str] | None,
    taskfile_dir: Path,
) -> list[Issue]:
    """Check that requested tasks and their dependencies exist and scripts are present."""
    issues: list[Issue] = []
    for tname in (task_names or []):
        task = config.tasks.get(tname)
        if not task:
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"Unknown task: {tname}",
                severity=SEVERITY_ERROR,
                layer=2,
            ))
            continue
        if task.script:
            sp = taskfile_dir / task.script
            if not sp.exists():
                issues.append(Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"Task '{tname}' script not found: {task.script}",
                    severity=SEVERITY_ERROR,
                    fix_description=f"Create the script: mkdir -p {Path(task.script).parent} && touch {task.script}",
                    teach=(
                        "The 'script:' directive runs an external script file. "
                        "If the file doesn't exist, create it or use 'cmds:' "
                        "with inline commands instead of 'script:'."
                    ),
                    layer=2,
                ))
        for dep in task.deps:
            if dep not in config.tasks:
                issues.append(Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"Task '{tname}' depends on unknown task '{dep}'",
                    severity=SEVERITY_ERROR,
                    layer=2,
                ))
    return issues


# ─── Infrastructure Checks (delegated to checks_infra.py) ─────────

from taskfile.diagnostics.checks_infra import (  # noqa: E402, F401
    check_ufw_forward_policy as _check_ufw_forward_policy,
    check_container_dns as _check_container_dns,
)


# ─── Deploy Artifact Validation (delegated to checks_deploy.py) ───

from taskfile.diagnostics.checks_deploy import (  # noqa: E402, F401
    check_deploy_artifacts,
    _scan_file_for_unresolved,
)


def _check_ssh_key_for_env(
    config: "TaskfileConfig",
    env_name: str | None,
) -> list[Issue]:
    """Check that SSH key exists for remote environment."""
    issues: list[Issue] = []
    target_env = env_name or config.default_env or "local"
    env_obj = config.environments.get(target_env)
    if env_obj and env_obj.ssh_host:
        ssh_key = env_obj.ssh_key
        if ssh_key:
            key_path = Path(os.path.expanduser(ssh_key))
            if not key_path.exists():
                issues.append(Issue(
                    category=IssueCategory.CONFIG_ERROR,
                    message=f"SSH key not found for '{target_env}': {ssh_key}",
                    severity=SEVERITY_WARNING,
                    fix_strategy=FixStrategy.CONFIRM,
                    fix_command=f"ssh-keygen -t ed25519 -f {ssh_key} -N ''",
                    layer=3,
                ))
    return issues


def validate_before_run(
    config: "TaskfileConfig",
    env_name: str | None = None,
    task_names: list[str] | None = None,
) -> list[Issue]:
    """Quick pre-run validation — returns issues that would cause task failure."""
    taskfile_dir = Path(config.source_path).parent if config.source_path else Path.cwd()
    issues: list[Issue] = []
    issues.extend(_check_env_file_for_target(config, env_name, taskfile_dir))
    issues.extend(_check_tasks_and_deps(config, task_names, taskfile_dir))
    issues.extend(check_placeholder_values(config))
    issues.extend(_check_ssh_key_for_env(config, env_name))
    return issues


# ─── Private helpers ──────────────────────────────────────────────


# Port helpers — delegated to checks_ports.py (backward-compat re-exports)
from taskfile.diagnostics.checks_ports import (  # noqa: E402, F401
    _resolve_port_conflict,
    _parse_compose_host_port,
    _is_port_free,
    _find_free_port_near,
    _who_uses_port,
    _is_docker_process,
)


# SSH helpers — delegated to checks_ssh.py (backward-compat re-export)
# NOTE: _test_ssh removed — SSH transport now handled by fixop.ssh


def _extract_binary(cmd: str) -> str | None:
    """Extract the binary name from a shell command string."""
    cmd = cmd.strip()
    if not cmd:
        return None
    # Skip special prefixes
    if cmd.startswith("@"):
        return None
    # Skip shell builtins and conditionals
    if cmd.startswith(("if ", "for ", "while ", "case ", "echo ", "export ", "cd ")):
        return None
    # Handle pipe chains — check first command
    first = cmd.split("|")[0].strip()
    # Handle env var assignments
    parts = first.split()
    for part in parts:
        if "=" in part:
            continue
        return part
    return None
