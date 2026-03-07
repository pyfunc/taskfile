"""Deploy recipes — auto-generate build/push/deploy/ops/rollback/health tasks.

When a Taskfile contains a `deploy:` section, this module generates standard
tasks that would otherwise be 200+ lines of boilerplate YAML.

Generated task categories:
    Build:   build-<svc>, build-all
    Push:    push-<svc>, push-all
    Deploy:  validate-deploy, deploy, post-deploy
    Ops:     status, logs, stop, restart, backup
    Health:  health
    Rescue:  rollback

Supported strategies:
    compose  — docker compose up/down (local/staging)
    quadlet  — Podman Quadlet generate + upload + restart (production)
    ssh-push — simple pull + restart via SSH

Example YAML:
    deploy:
      strategy: quadlet
      images:
        api: services/api/Dockerfile
        web: services/web/Dockerfile
      registry: ghcr.io/myorg
      health_check: /health
      health_retries: 5
      restart_delay: 3
      log_lines: 50
      backup_paths:
        - /data/volumes
"""

from __future__ import annotations

from typing import Any


def expand_deploy_recipe(deploy_section: dict[str, Any], variables: dict[str, str]) -> dict[str, dict]:
    """Convert a deploy: section into a dict of task definitions.

    Returns raw task dicts ready to merge into the tasks: section.
    Generated task names use a `deploy-` prefix to avoid collisions.
    """
    if not isinstance(deploy_section, dict):
        return {}

    strategy = deploy_section.get("strategy", "compose")
    images = deploy_section.get("images", {})
    registry = deploy_section.get("registry", "${REGISTRY}")
    health_check = deploy_section.get("health_check", "/health")
    health_retries = deploy_section.get("health_retries", 5)
    health_delay = deploy_section.get("health_delay", 5)
    restart_delay = deploy_section.get("restart_delay", 3)  # seconds between stop→start
    tag_var = "${TAG}"

    log_lines = deploy_section.get("log_lines", 50)
    backup_paths = deploy_section.get("backup_paths", [])
    containers = deploy_section.get("containers", list(images.keys()))

    tasks: dict[str, dict] = {}
    tasks.update(_build_tasks(images, registry, tag_var))
    tasks.update(_push_tasks(images, registry, tag_var))
    tasks["validate-deploy"] = _validate_task()
    tasks["deploy"] = _deploy_task(strategy, images, registry, tag_var, restart_delay)
    tasks.update(_health_tasks(images, health_check, health_retries, health_delay, registry, tag_var))
    tasks.update(_rollback_tasks(images, registry, tag_var, restart_delay))
    tasks.update(_ops_tasks(strategy, containers, restart_delay, log_lines, backup_paths))

    # Optional fixop integration (presence of key signals intent, even if empty)
    if "fixop" in deploy_section:
        fixop_cfg = deploy_section.get("fixop") or {}
        tasks.update(_fixop_tasks(fixop_cfg, containers))

    return tasks


def _build_tasks(images: dict, registry: str, tag_var: str) -> dict[str, dict]:
    """Generate build-<svc> and build-all tasks."""
    tasks: dict[str, dict] = {}
    for svc_name, dockerfile in images.items():
        image_var = f"{registry}/{svc_name}:{tag_var}"
        tasks[f"build-{svc_name}"] = {
            "desc": f"Build {svc_name} Docker image",
            "stage": "build",
            "tags": ["ci", "build"],
            "cmds": [f"docker build -t {image_var} -f {dockerfile} ."],
        }
    if len(images) > 1:
        tasks["build-all"] = {
            "desc": "Build all images",
            "deps": [f"build-{s}" for s in images],
            "parallel": True,
            "tags": ["ci", "build"],
            "cmds": ["echo 'All images built'"],
        }
    return tasks


def _push_tasks(images: dict, registry: str, tag_var: str) -> dict[str, dict]:
    """Generate push-<svc> and push-all tasks."""
    tasks: dict[str, dict] = {}
    for svc_name in images:
        image_var = f"{registry}/{svc_name}:{tag_var}"
        tasks[f"push-{svc_name}"] = {
            "desc": f"Push {svc_name} to registry",
            "deps": [f"build-{svc_name}"],
            "stage": "push",
            "tags": ["ci", "push"],
            "cmds": [f"docker push {image_var}"],
        }
    if len(images) > 1:
        tasks["push-all"] = {
            "desc": "Push all images to registry",
            "deps": [f"push-{s}" for s in images],
            "parallel": True,
            "stage": "push",
            "tags": ["ci", "push"],
            "cmds": [f"echo 'All images pushed to {registry}'"],
        }
    return tasks


def _validate_task() -> dict:
    """Generate the validate-deploy gate task."""
    return {
        "desc": "Validate deploy artifacts — check for unresolved variables and placeholders",
        "tags": ["ci", "validate"],
        "silent": True,
        "cmds": [
            '@python from taskfile.diagnostics.checks import check_deploy_artifacts; '
            'from taskfile.parser import find_taskfile, load_taskfile; '
            'cfg = load_taskfile(find_taskfile()); '
            'issues = check_deploy_artifacts(cfg); '
            '[print(f"ERROR: {i.message}") for i in issues if i.severity == "error"]; '
            '[print(f"WARN: {i.message}") for i in issues]; '
            'exit(1) if any(i.severity == "error" for i in issues) else None',
        ],
    }


def _deploy_task(
    strategy: str, images: dict, registry: str, tag_var: str, restart_delay: int,
) -> dict:
    """Generate the deploy task based on strategy. Dispatches to strategy-specific builders."""
    push_dep = "push-all" if len(images) > 1 else f"push-{list(images)[0]}" if images else None
    deploy_deps = ["validate-deploy"]
    if push_dep:
        deploy_deps.insert(0, push_dep)

    _STRATEGY_DISPATCH = {
        "compose": lambda: _compose_deploy(deploy_deps),
        "quadlet": lambda: _quadlet_deploy(deploy_deps, images, registry, tag_var, restart_delay),
        "ssh-push": lambda: _ssh_push_deploy(deploy_deps, images, registry, tag_var, restart_delay),
    }
    builder = _STRATEGY_DISPATCH.get(strategy, _STRATEGY_DISPATCH["compose"])
    return builder()


def _health_tasks(
    images: dict, health_check: str, health_retries: int, health_delay: int,
    registry: str, tag_var: str,
) -> dict[str, dict]:
    """Generate health and post-deploy health gate tasks."""
    return {
        "health": {
            "desc": "Check application health",
            "tags": ["ops", "health"],
            "silent": True,
            "retries": health_retries,
            "retry_delay": health_delay,
            "cmds": [
                f"curl -sf https://${{DOMAIN}}{health_check} && echo 'OK' || exit 1",
            ],
        },
        "post-deploy": {
            "desc": "Post-deploy health gate — verify all services are healthy after deploy",
            "tags": ["deploy", "health"],
            "silent": True,
            "retries": health_retries,
            "retry_delay": health_delay,
            "cmds": _post_deploy_health_cmds(images, health_check, registry, tag_var),
        },
    }


def _rollback_tasks(images: dict, registry: str, tag_var: str, restart_delay: int) -> dict[str, dict]:
    """Generate rollback task if images are defined."""
    if not images:
        return {}
    rollback_cmds = []
    for svc_name in images:
        image_var = f"{registry}/{svc_name}:{tag_var}"
        rollback_cmds.append(f"@remote podman pull {image_var}")
    for svc_name in images:
        rollback_cmds.extend(_graceful_restart_cmds(svc_name, restart_delay))
    return {
        "rollback": {
            "desc": "Rollback to specified version (--var TAG=<prev>)",
            "tags": ["deploy", "rollback"],
            "cmds": rollback_cmds,
        },
    }


def _graceful_restart_cmds(svc_name: str, restart_delay: int = 3) -> list[str]:
    """Generate graceful restart commands for a single service.

    Pattern: stop → sleep(delay) → start
    This avoids the hard restart that causes dropped connections.
    The delay allows in-flight requests to complete.
    """
    return [
        f"@remote systemctl --user stop ${{APP_NAME}}-{svc_name}",
        f"sleep {restart_delay}",
        f"@remote systemctl --user start ${{APP_NAME}}-{svc_name}",
    ]


def _post_deploy_health_cmds(
    images: dict, health_check: str, registry: str, tag_var: str,
) -> list[str]:
    """Generate post-deploy health verification commands."""
    cmds: list[str] = []
    # Check each service container is running
    for svc_name in images:
        cmds.append(
            f"@remote systemctl --user is-active --quiet ${{APP_NAME}}-{svc_name} "
            f"&& echo '{svc_name}: running' || (echo '{svc_name}: NOT RUNNING' && exit 1)"
        )
    # Check HTTP health endpoint
    cmds.append(
        f"curl -sf https://${{DOMAIN}}{health_check} && echo 'Health: OK' || exit 1"
    )
    return cmds


def _compose_deploy(deps: list[str]) -> dict:
    """Generate compose-based deploy task."""
    return {
        "desc": "Deploy via docker compose",
        "deps": deps,
        "tags": ["ci", "deploy"],
        "retries": 2,
        "retry_delay": 10,
        "cmds": [
            "@remote docker compose pull",
            "@remote docker compose up -d --remove-orphans",
        ],
    }


def _quadlet_deploy(
    deps: list[str], images: dict, registry: str, tag_var: str,
    restart_delay: int = 3,
) -> dict:
    """Generate Quadlet-based deploy task with graceful restart."""
    cmds = [
        "taskfile quadlet generate",
        "taskfile quadlet upload",
        "@remote systemctl --user daemon-reload",
    ]
    for svc_name in images:
        image_var = f"{registry}/{svc_name}:{tag_var}"
        cmds.append(f"@remote podman pull {image_var}")
    # Graceful restart: stop → delay → start (one service at a time)
    for svc_name in images:
        cmds.extend(_graceful_restart_cmds(svc_name, restart_delay))
    cmds.append("@remote podman image prune -f")

    return {
        "desc": "Deploy via Podman Quadlet (generate → upload → pull → graceful restart)",
        "deps": deps,
        "tags": ["ci", "deploy"],
        "retries": 2,
        "retry_delay": 15,
        "timeout": 600,
        "cmds": cmds,
    }


def _ssh_push_deploy(
    deps: list[str], images: dict, registry: str, tag_var: str,
    restart_delay: int = 3,
) -> dict:
    """Generate simple SSH pull+graceful restart deploy task."""
    cmds = []
    for svc_name in images:
        image_var = f"{registry}/{svc_name}:{tag_var}"
        cmds.append(f"@remote podman pull {image_var}")
    # Graceful restart: stop → delay → start (one service at a time)
    for svc_name in images:
        cmds.extend(_graceful_restart_cmds(svc_name, restart_delay))
    cmds.append("@remote podman image prune -f")

    return {
        "desc": "Deploy via SSH (pull + graceful restart)",
        "deps": deps,
        "tags": ["ci", "deploy"],
        "retries": 1,
        "retry_delay": 10,
        "cmds": cmds,
    }


# ─── Ops tasks (status, logs, stop, restart, backup) ─────────────────────────


def _ops_tasks(
    strategy: str,
    containers: list[str],
    restart_delay: int,
    log_lines: int,
    backup_paths: list[str],
) -> dict[str, dict]:
    """Generate operational tasks: status, logs, stop, restart, backup.

    These are the day-to-day tasks that operators use after deploy.
    Strategy-aware: compose uses docker compose, quadlet/ssh-push use systemctl+podman.
    """
    tasks: dict[str, dict] = {}

    if strategy == "compose":
        tasks.update(_compose_ops_tasks(containers, log_lines))
    else:
        tasks.update(_systemd_ops_tasks(containers, restart_delay, log_lines))

    if backup_paths:
        tasks["backup"] = _backup_task(backup_paths)

    return tasks


def _compose_ops_tasks(containers: list[str], log_lines: int) -> dict[str, dict]:
    """Generate ops tasks for compose strategy."""
    return {
        "status": {
            "desc": "Show status of all services",
            "tags": ["ops"],
            "cmds": ["docker compose ps"],
        },
        "logs": {
            "desc": f"Tail logs (last {log_lines} lines)",
            "tags": ["ops"],
            "cmds": [f"docker compose logs --tail={log_lines} -f"],
        },
        "stop": {
            "desc": "Stop all services",
            "tags": ["ops"],
            "cmds": ["docker compose stop"],
        },
        "restart": {
            "desc": "Restart all services",
            "tags": ["ops"],
            "cmds": ["docker compose restart"],
        },
    }


def _systemd_ops_tasks(
    containers: list[str], restart_delay: int, log_lines: int,
) -> dict[str, dict]:
    """Generate ops tasks for quadlet/ssh-push strategies (systemd + podman)."""
    # status: check each unit + show running containers
    status_cmds: list[str] = []
    for c in containers:
        status_cmds.append(
            f"@remote systemctl --user is-active --quiet ${{APP_NAME}}-{c} "
            f"&& echo '{c}: ✓ running' || echo '{c}: ✗ stopped'"
        )
    status_cmds.append("@remote podman ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")

    # logs: journal + podman logs
    logs_cmds: list[str] = []
    for c in containers:
        logs_cmds.append(f"@remote podman logs --tail={log_lines} ${{APP_NAME}}-{c}")

    # stop: graceful stop each service
    stop_cmds = [f"@remote systemctl --user stop ${{APP_NAME}}-{c}" for c in containers]

    # restart: graceful restart (stop → delay → start) per service
    restart_cmds: list[str] = []
    for c in containers:
        restart_cmds.extend(_graceful_restart_cmds(c, restart_delay))

    return {
        "status": {
            "desc": "Show status of all services on remote",
            "tags": ["ops"],
            "cmds": status_cmds,
        },
        "logs": {
            "desc": f"Tail remote container logs (last {log_lines} lines)",
            "tags": ["ops"],
            "cmds": logs_cmds,
        },
        "stop": {
            "desc": "Gracefully stop all services on remote",
            "tags": ["ops"],
            "cmds": stop_cmds,
        },
        "restart": {
            "desc": "Gracefully restart all services on remote",
            "tags": ["ops"],
            "cmds": restart_cmds,
        },
    }


def _backup_task(backup_paths: list[str]) -> dict:
    """Generate backup task for specified paths."""
    timestamp = "$(date +%Y%m%d_%H%M%S)"
    cmds = [f"@remote mkdir -p /tmp/backup-{timestamp}"]
    for p in backup_paths:
        cmds.append(f"@remote cp -a {p} /tmp/backup-{timestamp}/")
    cmds.append(f"@remote tar czf /tmp/backup-{timestamp}.tar.gz -C /tmp backup-{timestamp}")
    cmds.append(f"@remote rm -rf /tmp/backup-{timestamp}")
    cmds.append(f"echo 'Backup saved to /tmp/backup-{timestamp}.tar.gz'")
    return {
        "desc": "Backup data volumes before deploy",
        "tags": ["ops", "backup"],
        "cmds": cmds,
    }


# ─── Fixop integration ───────────────────────────────────────────────────────


def _fixop_tasks(fixop_cfg: dict, containers: list[str]) -> dict[str, dict]:
    """Generate fixop integration tasks: doctor, drift-check, fix.

    Config example:
        fixop:
          domains: ["example.com"]
          readme: README.md
          source_dir: sandbox/
          auto_fix: true
    """
    tasks: dict[str, dict] = {}

    domains = fixop_cfg.get("domains", [])
    readme = fixop_cfg.get("readme", "README.md")
    source_dir = fixop_cfg.get("source_dir", "sandbox/")
    auto_fix = fixop_cfg.get("auto_fix", False)

    # doctor: run fixop checks against the environment
    doctor_cmds = ["fixop check"]
    if domains:
        for d in domains:
            doctor_cmds.append(f"fixop check --domain {d}")
    if containers:
        doctor_cmds.append(
            f"fixop check --containers {' '.join(containers)}"
        )

    tasks["doctor"] = {
        "desc": "Run infrastructure health checks (fixop)",
        "tags": ["ops", "fixop"],
        "cmds": doctor_cmds,
    }

    # drift-check: compare README blocks against disk files
    tasks["drift-check"] = {
        "desc": "Check for file drift between README and disk",
        "tags": ["ci", "fixop"],
        "silent": True,
        "cmds": [
            f"@python from fixop.drift import check_file_drift, check_untracked_files; "
            f"issues = check_file_drift('{readme}', '{source_dir}'); "
            f"issues += check_untracked_files('{readme}', '{source_dir}'); "
            f"[print(f'{{i.severity.value}}: {{i.message}}') for i in issues]; "
            f"exit(1) if any(i.severity.value == 'error' for i in issues) else None",
        ],
    }

    # fix: auto-fix issues if enabled
    if auto_fix:
        tasks["fix"] = {
            "desc": "Auto-fix infrastructure issues (fixop)",
            "tags": ["ops", "fixop"],
            "cmds": ["fixop fix --auto"],
        }

    return tasks
