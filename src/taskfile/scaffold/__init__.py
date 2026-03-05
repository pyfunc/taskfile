"""Scaffold templates for `taskfile init`.

Templates are stored as plain YAML files in templates/ directory,
editable without knowing Python. The old Python modules are kept
as fallbacks for backward compatibility.
"""

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_TEMPLATE_NAMES = [
    "minimal", "web", "podman", "full", "codereview", "multiplatform", "publish",
]


def _load_template(name: str) -> str:
    """Load template from YAML file, fall back to Python module."""
    yml_path = _TEMPLATES_DIR / f"{name}.yml"
    if yml_path.is_file():
        return yml_path.read_text(encoding="utf-8")
    # Fallback to Python module (backward compat)
    import importlib
    mod = importlib.import_module(f"taskfile.scaffold.{name}")
    return mod.TEMPLATE


def generate_taskfile(template: str = "full") -> str:
    """Generate a Taskfile.yml from a template."""
    if template not in _TEMPLATE_NAMES:
        raise ValueError(f"Unknown template: {template}. Available: {_TEMPLATE_NAMES}")
    return _load_template(template)
