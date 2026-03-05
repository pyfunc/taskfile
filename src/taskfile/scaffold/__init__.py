"""Scaffold templates for `taskfile init`."""

from taskfile.scaffold.minimal import TEMPLATE as minimal
from taskfile.scaffold.web import TEMPLATE as web
from taskfile.scaffold.podman import TEMPLATE as podman
from taskfile.scaffold.full import TEMPLATE as full
from taskfile.scaffold.codereview import TEMPLATE as codereview
from taskfile.scaffold.multiplatform import TEMPLATE as multiplatform
from taskfile.scaffold.publish import TEMPLATE as publish

TEMPLATES = {
    "minimal": minimal,
    "web": web,
    "podman": podman,
    "full": full,
    "codereview": codereview,
    "multiplatform": multiplatform,
    "publish": publish,
}

def generate_taskfile(template: str = "full") -> str:
    """Generate a Taskfile.yml from a template."""
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template: {template}. Available: {list(TEMPLATES.keys())}")
    return TEMPLATES[template]
