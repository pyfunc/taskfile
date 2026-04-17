"""Tests for project-aware ``minimal`` scaffold customisation.

The previous ``minimal.yml`` template generated a Taskfile that referenced an
unbound ``${COMPOSE}`` variable and a placeholder SSH host, so every freshly
initialised project crashed on the first ``taskfile run`` invocation.

These tests pin the new behaviour: detect the project type and emit working
tasks instead.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from taskfile.scaffold import generate_taskfile
from taskfile.scaffold.customize import customise_minimal


# ── helpers ───────────────────────────────────────────────────


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body).lstrip())
    return p


def _customise(root: Path) -> dict:
    raw = generate_taskfile("minimal")
    out = customise_minimal(raw, root)
    return yaml.safe_load(out)


# ── baseline template hygiene ────────────────────────────────


def test_minimal_template_no_unbound_compose_placeholder() -> None:
    """Regression: the previous template referenced ``${COMPOSE}`` which was
    never defined, so the very first ``taskfile run build`` would fail with
    an unbound variable error.
    """
    raw = generate_taskfile("minimal")
    assert "${COMPOSE}" not in raw, (
        "minimal template must not reference the unbound ${COMPOSE} variable"
    )
    assert "your-server.example.com" not in raw, (
        "minimal template must not ship with a placeholder SSH host"
    )


def test_minimal_template_is_valid_yaml_with_tasks() -> None:
    raw = generate_taskfile("minimal")
    data = yaml.safe_load(raw)
    assert isinstance(data, dict)
    assert data.get("tasks"), "minimal template must define at least one task"


# ── project detection ────────────────────────────────────────


def test_customise_detects_python_pyproject_with_pytest_and_ruff(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", """\
        [project]
        name = "demo-pkg"
        version = "0.1.0"
        dependencies = []
        [project.optional-dependencies]
        dev = ["pytest", "ruff"]
    """)
    (tmp_path / "tests").mkdir()

    data = _customise(tmp_path)

    assert data["name"] == "demo-pkg"
    assert data["variables"]["APP_NAME"] == "demo-pkg"
    tasks = data["tasks"]
    assert "install" in tasks
    assert "pip install -e .[dev]" in tasks["install"]["cmds"]
    assert "test" in tasks
    assert "pytest -q" in tasks["test"]["cmds"]
    assert "lint" in tasks and "ruff check" in tasks["lint"]["cmds"][0]
    assert "build" in tasks and "python -m build" in tasks["build"]["cmds"]


def test_customise_uses_requirements_when_no_pyproject(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "requests\n")
    data = _customise(tmp_path)
    tasks = data["tasks"]
    assert "install" in tasks
    assert "pip install -r requirements.txt" in tasks["install"]["cmds"]
    # No pyproject → no build/clean tasks
    assert "build" not in tasks


def test_customise_detects_node_scripts(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", """\
        {
          "name": "demo-web",
          "scripts": {
            "build": "vite build",
            "dev": "vite",
            "test": "vitest"
          }
        }
    """)
    data = _customise(tmp_path)
    tasks = data["tasks"]
    assert data["name"] == "demo-web"
    assert "install" in tasks and "npm install" in tasks["install"]["cmds"]
    assert "build" in tasks and tasks["build"]["cmds"] == ["npm run build"]
    assert "dev" in tasks
    assert "test" in tasks


def test_customise_detects_docker_compose(tmp_path: Path) -> None:
    _write(tmp_path, "docker-compose.yml", "services:\n  web:\n    image: nginx\n")
    data = _customise(tmp_path)
    tasks = data["tasks"]
    assert "up" in tasks and "docker compose up -d" in tasks["up"]["cmds"]
    assert "down" in tasks
    assert "logs" in tasks
    assert "ps" in tasks


def test_customise_detects_dockerfile_only(tmp_path: Path) -> None:
    _write(tmp_path, "Dockerfile", "FROM alpine\n")
    data = _customise(tmp_path)
    tasks = data["tasks"]
    assert "docker-build" in tasks
    cmd = tasks["docker-build"]["cmds"][0]
    assert cmd.startswith("docker build -t ")
    assert tmp_path.name in cmd


def test_customise_hints_at_existing_makefile(tmp_path: Path) -> None:
    _write(tmp_path, "Makefile", "build:\n\techo hi\n")
    _write(tmp_path, "pyproject.toml", '[project]\nname="x"\nversion="0.1.0"\n')
    data = _customise(tmp_path)
    tasks = data["tasks"]
    assert "import-makefile-hint" in tasks
    desc = tasks["import-makefile-hint"]["desc"].lower()
    assert "makefile" in desc and "import" in desc


def test_customise_combines_python_and_compose(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname="api"\nversion="0.1.0"\n')
    _write(tmp_path, "docker-compose.yml", "services:\n  api: {image: x}\n")
    data = _customise(tmp_path)
    tasks = data["tasks"]
    # Both worlds present
    assert "install" in tasks
    assert "up" in tasks
    # Python build task wins over compose for the "build" name
    assert "python -m build" in tasks["build"]["cmds"][0]


def test_customise_falls_back_to_template_when_nothing_detected(tmp_path: Path) -> None:
    """Empty directory → keep the template stubs so the file remains valid."""
    data = _customise(tmp_path)
    assert "tasks" in data and data["tasks"], "fallback must keep stub tasks"


def test_customise_output_parses_as_taskfile_config(tmp_path: Path) -> None:
    """End-to-end: customised output must round-trip through the loader."""
    from taskfile.models import TaskfileConfig

    _write(tmp_path, "pyproject.toml", '[project]\nname="x"\nversion="0.1.0"\ndependencies=[]\n')
    raw = generate_taskfile("minimal")
    out = customise_minimal(raw, tmp_path)
    data = yaml.safe_load(out)
    config = TaskfileConfig.from_dict(data)
    assert config.name == "x"
    assert len(config.tasks) > 0
