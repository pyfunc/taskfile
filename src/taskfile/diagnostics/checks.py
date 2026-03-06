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
    issues: list[Issue] = []
    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        return issues

    try:
        compose = yaml.safe_load(compose_path.read_text()) or {}
    except Exception:
        return issues

    services = (compose or {}).get("services") or {}
    if not isinstance(services, dict):
        return issues

    from taskfile.compose import load_env_file, resolve_variables

    env_path = Path(".env")
    env_vars = load_env_file(env_path) if env_path.exists() else {}
    ctx = {**os.environ, **env_vars}

    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for port_entry in (svc.get("ports") or []):
            if not isinstance(port_entry, str):
                continue
            conflict = _resolve_port_conflict(svc_name, port_entry, ctx)
            if conflict:
                key, resolved_port, suggested = conflict
                pid, process = _who_uses_port(resolved_port)
                issues.append(Issue(
                    category=IssueCategory.RUNTIME_ERROR,
                    message=f"Port {resolved_port} for service '{svc_name}' is in use"
                            + (f" by '{process}' (pid {pid})" if process else ""),
                    fix_strategy=FixStrategy.CONFIRM,
                    severity=SEVERITY_WARNING,
                    fix_command=f"docker stop {process}" if process and _is_docker_process(process) else None,
                    fix_description=f"Set {key}={suggested} in .env or stop the conflicting process",
                    teach=(
                        f"Each service needs a unique port to listen on. Port {resolved_port} is already "
                        "in use by another process. Either stop the existing process or configure a "
                        "different port in your .env file. Use 'lsof -i :<port>' to find what's using it."
                    ),
                    context={"port_fixes": {key: suggested}},
                    layer=3,
                ))
    return issues


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
    issues: list[Issue] = []
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message="~/.ssh directory not found",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_ERROR,
            fix_command="mkdir -p ~/.ssh && chmod 700 ~/.ssh",
            teach=(
                "SSH directory (~/.ssh) stores your SSH keys and config. "
                "It must exist before generating keys. The chmod 700 ensures "
                "only you can access it — SSH refuses to use insecure directories."
            ),
            layer=3,
        ))
        return issues

    keys = list(ssh_dir.glob("id_*"))
    if not keys:
        issues.append(Issue(
            category=IssueCategory.CONFIG_ERROR,
            message="No SSH keys found (~/.ssh/id_*)",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_WARNING,
            fix_command="ssh-keygen -t ed25519 -N ''",
            fix_description="Generate an SSH key pair",
            teach=(
                "SSH keys authenticate you to remote servers without passwords. "
                "Generate a key pair, then copy the public key to the server "
                "with 'ssh-copy-id'. Ed25519 is the modern, secure key format."
            ),
            layer=3,
        ))
    return issues


def check_ssh_connectivity(config: "TaskfileConfig") -> list[Issue]:
    """Check SSH connectivity — distinguish: missing key vs refused vs auth fail."""
    issues: list[Issue] = []
    for env_name, env in config.environments.items():
        if not env.is_remote:
            continue
        ssh_key = env.ssh_key or "~/.ssh/id_ed25519"
        key_path = Path(os.path.expanduser(ssh_key))
        if not key_path.exists():
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"SSH key {ssh_key} not found for env '{env_name}'",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_WARNING,
                fix_command=f"ssh-keygen -t ed25519 -f {ssh_key} -N ''",
                context={"env": env_name, "host": env.ssh_host},
                teach=(
                    "SSH keys authenticate you to remote servers. "
                    "Generate a key pair, then use 'ssh-copy-id' to authorize it "
                    "on the remote server before attempting remote deployment."
                ),
                layer=3,
            ))
            continue

        rc = _test_ssh(env)
        if rc == 255:  # connection refused
            issues.append(Issue(
                category=IssueCategory.EXTERNAL_ERROR,
                message=f"SSH to {env.ssh_host}: connection refused",
                fix_strategy=FixStrategy.LLM,
                severity=SEVERITY_ERROR,
                context={"host": env.ssh_host, "env": env_name, "error": "connection_refused"},
                teach=(
                    "Connection refused means the server is reachable but SSH daemon "
                    "is not running or the port is blocked. Check: 1) Is the server "
                    "up? 2) Is SSH service running? 3) Is firewall blocking port 22? "
                    "4) Is the correct hostname/IP configured in Taskfile?"
                ),
                layer=3,
            ))
        elif rc == 5:  # auth failed
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"SSH auth failed for {env.ssh_host}",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_ERROR,
                fix_command=f"ssh-copy-id -i {ssh_key} {env.ssh_user}@{env.ssh_host}",
                context={"host": env.ssh_host, "env": env_name},
                teach=(
                    "SSH authentication failed — the key is not authorized on the server. "
                    "Copy your public key to the server with 'ssh-copy-id'. "
                    "Ensure the remote server has your key in ~/.ssh/authorized_keys."
                ),
                layer=3,
            ))
        elif rc != 0 and rc is not None:
            issues.append(Issue(
                category=IssueCategory.EXTERNAL_ERROR,
                message=f"SSH to {env.ssh_host}: failed (exit {rc})",
                fix_strategy=FixStrategy.LLM,
                severity=SEVERITY_WARNING,
                context={"host": env.ssh_host, "env": env_name, "exit_code": rc},
                layer=3,
            ))
    return issues


def check_remote_health(config: "TaskfileConfig") -> list[Issue]:
    """Check remote host health — podman, disk space, container status."""
    issues: list[Issue] = []
    for env_name, env in config.environments.items():
        if not env.is_remote:
            continue

        from taskfile.deploy_utils import (
            check_remote_podman,
            check_remote_disk,
            test_ssh_connection,
        )

        # Quick SSH check first
        ssh_result = test_ssh_connection(env.ssh_host, env.ssh_user, env.ssh_port)
        if not ssh_result.success:
            continue  # SSH checks are handled by check_ssh_connectivity

        # Podman
        podman_ok, podman_ver = check_remote_podman(env.ssh_host, env.ssh_user, env.ssh_port)
        if not podman_ok:
            issues.append(Issue(
                category=IssueCategory.DEPENDENCY_MISSING,
                message=f"Podman not installed on {env.ssh_host} (env: {env_name})",
                fix_strategy=FixStrategy.CONFIRM,
                severity=SEVERITY_WARNING,
                fix_command=f"ssh {env.ssh_user}@{env.ssh_host} 'apt install -y podman'",
                fix_description="Install podman on the remote server",
                teach=(
                    "Podman is a container runtime used on the remote server to run containers. "
                    "It's a Docker alternative preferred for rootless operation. "
                    "Install it via your distribution's package manager."
                ),
                context={"host": env.ssh_host, "env": env_name},
                layer=3,
            ))

        # Disk space
        disk = check_remote_disk(env.ssh_host, env.ssh_user, env.ssh_port)
        if disk and disk != "unknown":
            # Parse disk value — warn if < 1G
            try:
                val = disk.rstrip("GMKTBgmktb")
                unit = disk[len(val):].upper()
                num = float(val)
                if unit.startswith("M") and num < 500:
                    issues.append(Issue(
                        category=IssueCategory.EXTERNAL_ERROR,
                        message=f"Low disk on {env.ssh_host}: {disk} free",
                        fix_strategy=FixStrategy.MANUAL,
                        severity=SEVERITY_WARNING,
                        fix_description="Free disk space or expand volume",
                        teach=(
                            "Low disk space on the remote server may cause deployment failures "
                            "when pulling new images or writing files. Clean up unused images "
                            "with 'podman system prune' or expand the disk."
                        ),
                        context={"host": env.ssh_host, "disk": disk},
                        layer=3,
                    ))
                elif unit.startswith("K"):
                    issues.append(Issue(
                        category=IssueCategory.EXTERNAL_ERROR,
                        message=f"Critical disk on {env.ssh_host}: {disk} free",
                        fix_strategy=FixStrategy.MANUAL,
                        severity=SEVERITY_ERROR,
                        fix_description="Immediately free disk space",
                        teach=(
                            "Critical disk space on the remote server will prevent any new "
                            "deployments and may crash existing services. Urgent cleanup needed "
                            "with 'podman system prune' and removing logs."
                        ),
                        context={"host": env.ssh_host, "disk": disk},
                        layer=3,
                    ))
            except (ValueError, IndexError):
                pass

    return issues


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
    issues: list[Issue] = []
    for task_name, task in config.tasks.items():
        for cmd in task.commands:
            binary = _extract_binary(cmd)
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


# ─── Pre-run validation (called by runner) ────────────────────────


PLACEHOLDER_PATTERNS = [
    re.compile(r'your-.*\.example\.com', re.I),
    re.compile(r'\.example\.com$', re.I),
    re.compile(r'xxx+', re.I),
    re.compile(r'changeme', re.I),
    re.compile(r'replace[_-]me', re.I),
    re.compile(r'\bTODO\b'),
    re.compile(r'^0\.0\.0\.0$'),
    re.compile(r'^placeholder', re.I),
]


def _load_env_file_vars(env_file_path: Path) -> set[str]:
    """Load variable names defined in an env file."""
    if not env_file_path.exists():
        return set()
    names: set[str] = set()
    for line in env_file_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            names.add(line.split("=", 1)[0].strip())
    return names


def check_placeholder_values(config: "TaskfileConfig") -> list[Issue]:
    """Detect variables with placeholder values (example.com, changeme, etc.)."""
    taskfile_dir = Path(config.source_path).parent.resolve() if config.source_path else Path.cwd().resolve()
    issues: list[Issue] = []
    for env_name, env_obj in (config.environments or {}).items():
        resolved = env_obj.resolve_variables(config.variables or {})

        # Load env_file variables (if file exists) to check if fallbacks are overridden
        env_file_vars: set[str] = set()
        if env_obj.env_file:
            env_file_abs = (taskfile_dir / env_obj.env_file).resolve()
            env_file_vars = _load_env_file_vars(env_file_abs)

        # Also check ssh_host directly (may contain ${VAR:-default})
        fields_to_check = dict(resolved)
        fallback_var_map: dict[str, str] = {}  # key -> VAR name from ${VAR:-default}
        for attr in ("ssh_host", "ssh_user"):
            raw = getattr(env_obj, attr, None)
            if raw and isinstance(raw, str):
                # Extract default value from ${VAR:-default}
                m = re.match(r'\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]+)\}', raw)
                if m:
                    fallback_key = f"_{attr}_default"
                    fields_to_check[fallback_key] = m.group(2)
                    fallback_var_map[fallback_key] = m.group(1)
                else:
                    fields_to_check[attr] = raw

        for key, val in fields_to_check.items():
            if not isinstance(val, str):
                continue

            if not any(p.search(val) for p in PLACEHOLDER_PATTERNS):
                continue

            # Skip fallback placeholders when env_file defines the variable
            # e.g. ${STAGING_HOST:-staging.example.com} — if .env.staging has STAGING_HOST, skip
            if key in fallback_var_map:
                var_name = fallback_var_map[key]
                if var_name in env_file_vars:
                    continue

            # Skip resolved variables when env_file overrides them at runtime
            # e.g. DOMAIN_WEB=app-staging.example.com in Taskfile but .env.staging has DOMAIN_WEB=real.com
            if key in env_file_vars and not key.startswith("_"):
                continue

            real_key = key.lstrip("_").replace("_default", "").upper()
            env_file_hint = ""
            if env_obj.env_file:
                env_file_abs = (taskfile_dir / env_obj.env_file).resolve()
                env_file_hint = f" or edit {env_file_abs}"
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"'{real_key}' in env '{env_name}' looks like a placeholder: \"{val}\"",
                fix_strategy=FixStrategy.MANUAL,
                severity=SEVERITY_WARNING,
                fix_description=f"Set real value: export {real_key}=...{env_file_hint}",
                teach=(
                    f"Variables with values like 'example.com' or 'your-*' are placeholders "
                    f"— replace them with real data before deploying."
                ),
                layer=2,
            ))
    return issues


def _check_env_file_for_target(
    config: "TaskfileConfig",
    env_name: str | None,
    taskfile_dir: Path,
) -> list[Issue]:
    """Check that the target environment's env_file exists."""
    issues: list[Issue] = []
    target_env = env_name or config.default_env or "local"
    env_obj = config.environments.get(target_env)
    if env_obj and env_obj.env_file:
        env_path = (taskfile_dir / env_obj.env_file).resolve()
        if not env_path.exists():
            example = (taskfile_dir / f"{env_obj.env_file}.example").resolve()
            hint = f" (copy from {example})" if example.exists() else ""
            issues.append(Issue(
                category=IssueCategory.CONFIG_ERROR,
                message=f"Missing env file for '{target_env}': {env_path}{hint}",
                fix_strategy=FixStrategy.AUTO if example.exists() else FixStrategy.MANUAL,
                severity=SEVERITY_ERROR,
                context={"env_file": str(env_path), "example": str(example) if example.exists() else None},
                teach=(
                    "Environment files (.env) contain variables specific to each environment "
                    "(passwords, addresses, keys). Each environment in Taskfile can have its own "
                    ".env file. Create one from .env.example as a template."
                ),
                layer=2,
            ))
    return issues


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


def _resolve_port_conflict(
    svc_name: str, port_entry: str, ctx: dict
) -> tuple[str, int, int] | None:
    """Check a single port entry for conflicts. Returns (key, port, suggested) or None."""
    host_port, var_name = _parse_compose_host_port(port_entry)
    if host_port is None:
        return None

    from taskfile.compose import resolve_variables
    expanded = resolve_variables(str(host_port), ctx)
    try:
        resolved = int(expanded)
    except ValueError:
        return None

    if _is_port_free(resolved):
        return None

    suggested = _find_free_port_near(resolved)
    if suggested is None:
        return None

    key = var_name or f"PORT_{svc_name.upper()}"
    return key, resolved, suggested


def _parse_compose_host_port(port_entry: str) -> tuple[str | None, str | None]:
    entry = port_entry.strip()
    if not entry:
        return None, None
    entry = entry.split("/", 1)[0]
    parts = entry.split(":")
    if len(parts) < 2:
        return None, None
    host_port_expr = parts[-2]
    var_name = None
    m = re.match(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)", host_port_expr)
    if m:
        var_name = m.group("name")
    return host_port_expr, var_name


def _is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False


def _find_free_port_near(start: int, span: int = 50) -> int | None:
    for p in range(start, start + span + 1):
        if _is_port_free(p):
            return p
    for p in range(max(1024, start - span), start):
        if _is_port_free(p):
            return p
    return None


def _who_uses_port(port: int) -> tuple[int | None, str | None]:
    """Find pid and process name using a port. Returns (pid, name) or (None, None)."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pid = int(result.stdout.strip().split("\n")[0])
            ps = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                capture_output=True, text=True, timeout=5,
            )
            name = ps.stdout.strip() if ps.returncode == 0 else None
            return pid, name
    except Exception:
        pass
    return None, None


def _is_docker_process(process_name: str | None) -> bool:
    if not process_name:
        return False
    return any(x in (process_name or "").lower() for x in ("docker", "containerd", "podman"))


def _test_ssh(env) -> int | None:
    """Quick SSH connection test. Returns exit code or None on exception."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=no",
             f"-p", str(env.ssh_port),
             f"{env.ssh_user}@{env.ssh_host}", "true"],
            capture_output=True, timeout=10,
        )
        return result.returncode
    except Exception:
        return None


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
