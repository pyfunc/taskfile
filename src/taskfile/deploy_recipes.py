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
    rollback_mode = deploy_section.get("rollback", "manual")  # auto | manual
    tag_var = "${TAG}"

    tasks: dict[str, dict] = {}

    # ── Build tasks (one per image) ──
    for svc_name, dockerfile in images.items():
        image_var = f"{registry}/{svc_name}:{tag_var}"
        tasks[f"build-{svc_name}"] = {
            "desc": f"Build {svc_name} Docker image",
            "stage": "build",
            "tags": ["ci", "build"],
            "cmds": [f"docker build -t {image_var} -f {dockerfile} ."],
        }

    # ── build-all ──
    if len(images) > 1:
        tasks["build-all"] = {
            "desc": "Build all images",
            "deps": [f"build-{s}" for s in images],
            "parallel": True,
            "tags": ["ci", "build"],
            "cmds": ["echo 'All images built'"],
        }

    # ── Push tasks ──
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

    # ── Validate deploy artifacts (pre-deploy gate) ──
    tasks["validate-deploy"] = {
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

    # ── Deploy task (strategy-specific) ──
    push_dep = "push-all" if len(images) > 1 else f"push-{list(images)[0]}" if images else None
    deploy_deps = ["validate-deploy"]
    if push_dep:
        deploy_deps.insert(0, push_dep)

    if strategy == "compose":
        tasks["deploy"] = _compose_deploy(deploy_deps)
    elif strategy == "quadlet":
        tasks["deploy"] = _quadlet_deploy(deploy_deps, images, registry, tag_var)
    elif strategy == "ssh-push":
        tasks["deploy"] = _ssh_push_deploy(deploy_deps, images, registry, tag_var)
    else:
        tasks["deploy"] = _compose_deploy(deploy_deps)

    # ── Health check ──
    tasks["health"] = {
        "desc": "Check application health",
        "tags": ["ops", "health"],
        "silent": True,
        "retries": health_retries,
        "retry_delay": health_delay,
        "cmds": [
            f"curl -sf https://${{DOMAIN}}{health_check} && echo 'OK' || exit 1",
        ],
    }

    # ── Rollback ──
    if images:
        rollback_cmds = []
        for svc_name in images:
            image_var = f"{registry}/{svc_name}:{tag_var}"
            rollback_cmds.append(f"@remote podman pull {image_var}")
        for svc_name in images:
            rollback_cmds.append(f"@remote systemctl --user restart ${{APP_NAME}}-{svc_name}")
        tasks["rollback"] = {
            "desc": "Rollback to specified version (--var TAG=<prev>)",
            "tags": ["deploy", "rollback"],
            "cmds": rollback_cmds,
        }

    return tasks


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


def _quadlet_deploy(deps: list[str], images: dict, registry: str, tag_var: str) -> dict:
    """Generate Quadlet-based deploy task."""
    cmds = [
        "taskfile quadlet generate",
        "taskfile quadlet upload",
        "@remote systemctl --user daemon-reload",
    ]
    for svc_name in images:
        image_var = f"{registry}/{svc_name}:{tag_var}"
        cmds.append(f"@remote podman pull {image_var}")
    for svc_name in images:
        cmds.append(f"@remote systemctl --user restart ${{APP_NAME}}-{svc_name}")
    cmds.append("@remote podman image prune -f")

    return {
        "desc": "Deploy via Podman Quadlet (generate → upload → pull → restart)",
        "deps": deps,
        "tags": ["ci", "deploy"],
        "retries": 2,
        "retry_delay": 15,
        "timeout": 600,
        "cmds": cmds,
    }


def _ssh_push_deploy(deps: list[str], images: dict, registry: str, tag_var: str) -> dict:
    """Generate simple SSH pull+restart deploy task."""
    cmds = []
    for svc_name in images:
        image_var = f"{registry}/{svc_name}:{tag_var}"
        cmds.append(f"@remote podman pull {image_var}")
    for svc_name in images:
        cmds.append(f"@remote systemctl --user restart ${{APP_NAME}}-{svc_name}")
    cmds.append("@remote podman image prune -f")

    return {
        "desc": "Deploy via SSH (pull + restart)",
        "deps": deps,
        "tags": ["ci", "deploy"],
        "retries": 1,
        "retry_delay": 10,
        "cmds": cmds,
    }
