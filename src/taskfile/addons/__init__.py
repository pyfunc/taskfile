"""Addons system — pluggable task generators for common infrastructure.

Each addon module exports a `generate_tasks(config: dict) -> dict[str, dict]`
function that returns raw task definitions ready to merge into TaskfileConfig.

Usage in Taskfile.yml:
    addons:
      - postgres:
          db_name: myapp
          backup_dir: /tmp/backups
      - monitoring:
          grafana_url: http://grafana:3000
      - redis:
          url: redis://localhost:6379
"""

from __future__ import annotations

from typing import Any

# Registry of built-in addons
_ADDON_REGISTRY: dict[str, Any] = {}


def _load_registry() -> None:
    """Lazily populate the addon registry."""
    if _ADDON_REGISTRY:
        return
    from taskfile.addons import postgres, monitoring, redis_addon, fixop_addon
    _ADDON_REGISTRY["postgres"] = postgres.generate_tasks
    _ADDON_REGISTRY["monitoring"] = monitoring.generate_tasks
    _ADDON_REGISTRY["redis"] = redis_addon.generate_tasks
    _ADDON_REGISTRY["fixop"] = fixop_addon.generate_tasks


def expand_addons(addons_section: list) -> dict[str, dict]:
    """Expand addons: list into a dict of raw task definitions.

    Each entry can be:
      - str:  addon name with defaults  (e.g. "postgres")
      - dict: addon name → config       (e.g. {"postgres": {"db_name": "x"}})

    Returns merged task dicts. Later addons override earlier ones on collision.
    """
    _load_registry()

    tasks: dict[str, dict] = {}
    for entry in addons_section:
        if isinstance(entry, str):
            addon_name = entry
            addon_config: dict = {}
        elif isinstance(entry, dict):
            # YAML: - postgres: {db_name: x}  →  {"postgres": {"db_name": "x"}}
            addon_name = next(iter(entry))
            addon_config = entry[addon_name] or {}
        else:
            continue

        generator = _ADDON_REGISTRY.get(addon_name)
        if generator is None:
            available = ", ".join(sorted(_ADDON_REGISTRY.keys()))
            raise ValueError(
                f"Unknown addon '{addon_name}'. Available: {available}"
            )

        generated = generator(addon_config)
        tasks.update(generated)

    return tasks
