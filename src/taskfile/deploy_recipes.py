"""Deploy recipes — auto-generate build/push/deploy/rollback/health tasks.

When a Taskfile contains a `deploy:` section, this module generates standard
tasks that would otherwise be 40+ lines of boilerplate YAML.

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
      rollback: auto
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

    tasks: dict[str, dict] = {}
    tasks.update(_build_tasks(images, registry, tag_var))
    tasks.update(_push_tasks(images, registry, tag_var))
    tasks["validate-deploy"] = _validate_task()
    tasks["deploy"] = _deploy_task(strategy, images, registry, tag_var, restart_delay)
    tasks.update(_health_tasks(images, health_check, health_retries, health_delay, registry, tag_var))
    tasks.update(_rollback_tasks(images, registry, tag_var, restart_delay))

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
