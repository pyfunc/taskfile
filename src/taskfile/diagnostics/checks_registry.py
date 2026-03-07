"""Container registry reachability checks.

Verifies that IMAGE_* variables pointing to remote registries are reachable.
Suggests 'taskfile push' as SSH-based alternative when registry is unavailable.
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_WARNING,
)

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


def _extract_registry_host(image: str) -> str | None:
    """Extract registry hostname from a Docker image reference.

    Returns None for local images (no registry prefix).
    Examples:
        ghcr.io/user/app:latest → ghcr.io
        docker.io/library/nginx → docker.io
        registry.example.com:5000/myapp:v1 → registry.example.com:5000
        myapp:latest → None (local)
        localhost/myapp → None (local)
    """
    # Strip digest first
    img = image.split("@")[0]
    # Must have at least one slash to be a registry path
    if "/" not in img:
        return None
    first = img.split("/")[0]
    # localhost is local
    if first in ("localhost", "127.0.0.1") or first.startswith("localhost:"):
        return None
    # Registry hostnames contain a dot or a colon (port)
    if "." in first or ":" in first:
        return first
    return None


def _check_registry_reachable(host: str, timeout: float = 3.0) -> bool:
    """Check if a registry host is reachable (TCP connect on port 443)."""
    port = 443
    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            pass
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _is_image_var(key: str) -> bool:
    """Check if a variable name looks like an image reference."""
    upper = key.upper()
    return "IMAGE" in upper or upper.startswith("IMG")


def _collect_image_vars_from_config(config: "TaskfileConfig") -> dict[str, str]:
    """Collect IMAGE_* variables from global config variables."""
    return {
        key: val
        for key, val in (config.variables or {}).items()
        if isinstance(val, str) and _is_image_var(key)
    }


def _collect_image_vars_from_envs(config: "TaskfileConfig") -> dict[str, str]:
    """Collect IMAGE_* variables from environment-specific variables."""
    result: dict[str, str] = {}
    for env_name, env_obj in (config.environments or {}).items():
        for key, val in (env_obj.variables or {}).items():
            if isinstance(val, str) and _is_image_var(key):
                result[f"{key} (env:{env_name})"] = val
    return result


def _collect_image_vars_from_compose() -> dict[str, str]:
    """Collect image references from docker-compose.yml services."""
    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        return {}
    try:
        data = yaml.safe_load(compose_path.read_text()) or {}
        return {
            f"service:{svc_name}": svc["image"]
            for svc_name, svc in (data.get("services") or {}).items()
            if isinstance(svc, dict) and svc.get("image")
        }
    except Exception:
        return {}


def _group_by_registry(image_vars: dict[str, str]) -> dict[str, list[str]]:
    """Group image references by their registry hostname."""
    registries: dict[str, list[str]] = {}
    for var_key, image_ref in image_vars.items():
        host = _extract_registry_host(image_ref)
        if host:
            registries.setdefault(host, []).append(f"{var_key}={image_ref}")
    return registries


def _build_unreachable_registry_issue(registry: str, refs: list[str]) -> Issue:
    """Create an Issue for an unreachable container registry."""
    ref_list = ", ".join(refs[:3])
    if len(refs) > 3:
        ref_list += f" (+{len(refs) - 3} more)"
    return Issue(
        category=IssueCategory.DEPENDENCY_MISSING,
        message=f"Container registry '{registry}' is not reachable ({ref_list})",
        fix_strategy=FixStrategy.MANUAL,
        severity=SEVERITY_WARNING,
        fix_description=(
            f"Options:\n"
            f"  1. Transfer images via SSH: taskfile push IMAGE [IMAGE...]\n"
            f"  2. Use local images: change registry to 'localhost/' prefix\n"
            f"  3. Check network/VPN connection to {registry}"
        ),
        teach=(
            f"Your images reference registry '{registry}' which is not reachable. "
            "This may be due to network issues, VPN not connected, or the registry being down.\n\n"
            "**Alternative: SSH transfer (no registry needed)**\n"
            "Use `taskfile push` to transfer locally-built images directly to the remote server "
            "via `docker save | ssh podman load`:\n"
            "```\ntaskfile push myapp-web:latest myapp-landing:latest\n```\n\n"
            "**Alternative: localhost images**\n"
            "Change IMAGE_* variables to use `localhost/` prefix for local-only images."
        ),
        layer=3,
    )


def check_registry_access(config: "TaskfileConfig") -> list[Issue]:
    """Check if container image registries are reachable.

    Finds IMAGE_* variables pointing to remote registries and verifies
    network connectivity. Suggests 'taskfile push' as an alternative
    when registry is unreachable.
    """
    image_vars: dict[str, str] = {}
    image_vars.update(_collect_image_vars_from_config(config))
    image_vars.update(_collect_image_vars_from_envs(config))
    image_vars.update(_collect_image_vars_from_compose())

    registries = _group_by_registry(image_vars)
    return [
        _build_unreachable_registry_issue(registry, refs)
        for registry, refs in registries.items()
        if not _check_registry_reachable(registry)
    ]
