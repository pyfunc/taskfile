"""Tests for ``taskfile init --from-doql app.doql.css`` converter.

The ``doql adopt`` command captures a project's workflows into a CSS-like
spec. The reverse path \u2014 generating a ``Taskfile.yml`` from that spec \u2014
lets users switch between the two formats without manual translation.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from taskfile.models import TaskfileConfig
from taskfile.scaffold.from_doql import generate_from_doql


# ── helpers ───────────────────────────────────────────────────


def _write_spec(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "app.doql.css"
    path.write_text(body)
    return path


# ── parsing ───────────────────────────────────────────────────


def test_generate_from_minimal_spec(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path, ('app {\n  name: "demo-app";\n  version: "1.2.3";\n}\n'))
    content = generate_from_doql(spec)
    data = yaml.safe_load(content)
    assert data["name"] == "demo-app"
    assert "1.2.3" in data["description"]
    assert data["variables"]["APP_NAME"] == "demo-app"
    # No workflows \u2192 stub noop task so the Taskfile still parses
    assert data["tasks"]["noop"]["desc"].lower().startswith("no workflows")


def test_workflow_blocks_become_tasks(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        (
            'app { name: "api"; version: "0.1.0"; }\n'
            'workflow[name="build"] {\n'
            "  trigger: manual;\n"
            "  step-1: run cmd=pip install -e .;\n"
            "  step-2: run cmd=python -m build;\n"
            "}\n"
            'workflow[name="test"] {\n'
            "  trigger: manual;\n"
            "  step-1: run cmd=pytest -q;\n"
            "}\n"
        ),
    )
    data = yaml.safe_load(generate_from_doql(spec))
    tasks = data["tasks"]

    assert set(tasks) == {"build", "test"}
    assert tasks["build"]["cmds"] == ["pip install -e .", "python -m build"]
    assert tasks["test"]["cmds"] == ["pytest -q"]


def test_workflow_steps_are_ordered_by_step_number(tmp_path: Path) -> None:
    """``step-2`` before ``step-1`` in the spec must not corrupt the order
    of emitted commands.
    """
    spec = _write_spec(
        tmp_path,
        (
            'workflow[name="release"] {\n'
            "  step-2: run cmd=git push --tags;\n"
            "  step-1: run cmd=git tag v1.0;\n"
            "  step-3: run cmd=twine upload dist/*;\n"
            "}\n"
        ),
    )
    data = yaml.safe_load(generate_from_doql(spec))
    assert data["tasks"]["release"]["cmds"] == [
        "git tag v1.0",
        "git push --tags",
        "twine upload dist/*",
    ]


def test_environment_blocks_become_environments(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        (
            'app { name: "x"; version: "0.1.0"; }\n'
            'environment[name="local"] {\n'
            "  runtime: docker-compose;\n"
            '  env_file: ".env";\n'
            "}\n"
            'environment[name="prod"] {\n'
            "  runtime: docker-compose;\n"
            '  env_file: ".env.prod";\n'
            "}\n"
        ),
    )
    data = yaml.safe_load(generate_from_doql(spec))
    envs = data["environments"]
    assert set(envs) == {"local", "prod"}
    assert envs["local"]["env_file"] == ".env"
    assert envs["prod"]["env_file"] == ".env.prod"


def test_depend_steps_become_taskfile_deps(tmp_path: Path) -> None:
    """``step-N: depend target=X;`` from a dependency-only Makefile target
    must emit ``deps: [X, ...]`` in the generated Taskfile, not shell
    commands that would try to execute ``depend target=X`` literally.
    """
    spec = _write_spec(
        tmp_path,
        (
            'workflow[name="install"] {\n'
            '  trigger: "manual";\n'
            "  step-1: depend target=install-backend;\n"
            "  step-2: depend target=install-frontend;\n"
            "}\n"
            'workflow[name="release"] {\n'
            "  step-1: depend target=test;\n"
            "  step-2: run cmd=twine upload dist/*;\n"
            "}\n"
        ),
    )
    data = yaml.safe_load(generate_from_doql(spec))

    install = data["tasks"]["install"]
    assert install.get("deps") == ["install-backend", "install-frontend"]
    assert "cmds" not in install

    # Mixed workflow: deps come first, then cmds
    release = data["tasks"]["release"]
    assert release.get("deps") == ["test"]
    assert release.get("cmds") == ["twine upload dist/*"]


def test_scheduled_workflow_preserves_schedule(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        (
            'workflow[name="backup"] {\n'
            "  trigger: schedule;\n"
            '  schedule: "0 2 * * *";\n'
            "  step-1: run cmd=./scripts/backup.sh;\n"
            "}\n"
        ),
    )
    data = yaml.safe_load(generate_from_doql(spec))
    backup = data["tasks"]["backup"]
    assert backup["cmds"] == ["./scripts/backup.sh"]
    assert backup["schedule"] == "0 2 * * *"


def test_deploy_target_appears_in_description(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path, ('app { name: "x"; version: "0.1.0"; }\ndeploy {\n  target: docker-compose;\n}\n')
    )
    data = yaml.safe_load(generate_from_doql(spec))
    assert "docker-compose" in data["description"]


# ── end-to-end ────────────────────────────────────────────────


def test_output_round_trips_to_taskfile_config(tmp_path: Path) -> None:
    """Generated YAML must be loadable by the real Taskfile parser."""
    spec = _write_spec(
        tmp_path,
        (
            'app { name: "svc"; version: "2.0.0"; }\n'
            'workflow[name="up"] {\n'
            "  step-1: run cmd=docker compose up -d;\n"
            "}\n"
            'environment[name="local"] {\n'
            "  runtime: docker-compose;\n"
            '  env_file: ".env";\n'
            "}\n"
        ),
    )
    data = yaml.safe_load(generate_from_doql(spec))
    config = TaskfileConfig.from_dict(data)
    assert config.name == "svc"
    assert "up" in config.tasks
    assert "local" in config.environments


def test_handles_adopt_generated_spec_verbatim(tmp_path: Path) -> None:
    """This mirrors the exact shape emitted by ``doql adopt`` so any future
    churn in the emitter surfaces as a test failure instead of silent data
    loss.
    """
    spec = _write_spec(
        tmp_path,
        (
            "app {\n"
            '  name: "semcod";\n'
            '  version: "0.1.10";\n'
            "}\n"
            "\n"
            'database[name="postgres"] {\n'
            '  type: "postgresql";\n'
            "  url: env.DATABASE_URL;\n"
            "}\n"
            "\n"
            'workflow[name="lint"] {\n'
            "  step-1: run cmd=ruff check .;\n"
            "}\n"
            "\n"
            "deploy {\n"
            "  target: docker-compose;\n"
            "  compose_file: docker-compose.yml;\n"
            "}\n"
            "\n"
            'environment[name="local"] {\n'
            "  runtime: docker-compose;\n"
            '  env_file: ".env";\n'
            "}\n"
        ),
    )
    data = yaml.safe_load(generate_from_doql(spec))
    assert data["name"] == "semcod"
    assert data["tasks"]["lint"]["cmds"] == ["ruff check ."]
    assert data["environments"]["local"]["env_file"] == ".env"
