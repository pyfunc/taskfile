"""Project-aware customisation for the ``minimal`` scaffold.

When the user runs ``taskfile init --template minimal`` we previously emitted a
generic Taskfile that referenced an unbound ``${COMPOSE}`` variable and a
placeholder ``your-server.example.com`` SSH host. Running any task therefore
failed immediately on a freshly-initialised project.

This module looks at the project root (``pyproject.toml`` / ``package.json`` /
``Makefile`` / ``docker-compose.yml`` / ``Dockerfile``) and overlays the
generated YAML with concrete commands. The result is a Taskfile that runs
out-of-the-box in the most common Python and JS layouts.

Public API:
    customise_minimal(content: str, project_root: Path) -> str
        Returns a rewritten YAML string.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _safe_load(text: str) -> dict[str, Any]:
    import yaml
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _safe_dump(data: dict[str, Any]) -> str:
    import yaml
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


# ── detectors ────────────────────────────────────────────────


def _detect_python(root: Path) -> dict[str, Any] | None:
    """Detect a Python project. Returns metadata or ``None``."""
    pyproj = root / "pyproject.toml"
    setup_py = root / "setup.py"
    requirements = root / "requirements.txt"
    if not (pyproj.exists() or setup_py.exists() or requirements.exists()):
        return None

    info: dict[str, Any] = {
        "name": root.name,
        "has_pyproject": pyproj.exists(),
        "has_setup": setup_py.exists(),
        "has_requirements": requirements.exists(),
        "has_tests": (root / "tests").is_dir() or (root / "test").is_dir(),
        "has_src": (root / "src").is_dir(),
        "uses_ruff": False,
        "uses_pytest": False,
    }

    if pyproj.exists():
        try:
            text = pyproj.read_text()
        except OSError:
            text = ""
        info["uses_ruff"] = "ruff" in text.lower()
        info["uses_pytest"] = "pytest" in text.lower() or info["has_tests"]
        # Try to extract project.name
        try:
            import tomllib  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - py<3.11 fallback
            try:
                import tomli as tomllib  # type: ignore[no-redef,import-not-found]
            except ImportError:
                tomllib = None  # type: ignore[assignment]
        if tomllib is not None:
            try:
                with open(pyproj, "rb") as fh:
                    data = tomllib.load(fh)
                proj_name = data.get("project", {}).get("name")
                if proj_name:
                    info["name"] = proj_name
            except Exception:
                pass

    return info


def _detect_node(root: Path) -> dict[str, Any] | None:
    pkg = root / "package.json"
    if not pkg.exists():
        return None
    import json
    try:
        data = json.loads(pkg.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    return {
        "name": data.get("name") or root.name,
        "scripts": list(scripts.keys()) if isinstance(scripts, dict) else [],
    }


def _detect_compose(root: Path) -> Path | None:
    for candidate in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        p = root / candidate
        if p.exists():
            return p
    return None


def _detect_dockerfile(root: Path) -> bool:
    return (root / "Dockerfile").exists()


def _detect_makefile(root: Path) -> bool:
    return (root / "Makefile").exists()


# ── task builders ────────────────────────────────────────────


def _python_tasks(info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}

    install_cmd = (
        "pip install -e .[dev]" if info["has_pyproject"]
        else "pip install -r requirements.txt" if info["has_requirements"]
        else "pip install -e ."
    )
    tasks["install"] = {
        "desc": "Install Python dependencies (editable)",
        "cmds": [install_cmd],
    }

    if info["uses_pytest"]:
        tasks["test"] = {
            "desc": "Run pytest suite",
            "cmds": ["pytest -q"],
        }

    if info["uses_ruff"]:
        tasks["lint"] = {
            "desc": "Run ruff lint check",
            "cmds": ["ruff check ."],
        }
        tasks["fmt"] = {
            "desc": "Auto-format with ruff",
            "cmds": ["ruff format ."],
        }

    if info["has_pyproject"]:
        tasks["build"] = {
            "desc": "Build wheel + sdist",
            "cmds": ["python -m build"],
        }
        tasks["clean"] = {
            "desc": "Remove build artefacts",
            "cmds": ["rm -rf build/ dist/ *.egg-info"],
        }

    return tasks


def _node_tasks(info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {
        "install": {"desc": "Install npm dependencies", "cmds": ["npm install"]},
    }
    for script in ("build", "test", "lint", "dev", "start"):
        if script in info["scripts"]:
            tasks[script] = {
                "desc": f"Run npm script: {script}",
                "cmds": [f"npm run {script}"],
            }
    return tasks


def _compose_tasks(_compose_path: Path) -> dict[str, dict[str, Any]]:
    return {
        "up": {
            "desc": "Start services via docker compose",
            "cmds": ["docker compose up -d"],
        },
        "down": {
            "desc": "Stop services",
            "cmds": ["docker compose down"],
        },
        "logs": {
            "desc": "Tail compose logs",
            "cmds": ["docker compose logs -f"],
        },
        "ps": {
            "desc": "Show running compose services",
            "cmds": ["docker compose ps"],
        },
    }


def _dockerfile_tasks(name: str) -> dict[str, dict[str, Any]]:
    return {
        "docker-build": {
            "desc": "Build docker image",
            "cmds": [f"docker build -t {name}:latest ."],
        },
    }


# ── public API ───────────────────────────────────────────────


def customise_minimal(content: str, project_root: Path) -> str:
    """Rewrite the *content* of the minimal template based on *project_root*.

    The original template structure (``version`` / ``name`` / ``environments``)
    is preserved. Only the ``tasks`` mapping and ``name``/``variables`` are
    overlaid with project-specific content.
    """
    data = _safe_load(content)
    if not data:
        return content

    py = _detect_python(project_root)
    node = _detect_node(project_root)
    compose = _detect_compose(project_root)
    has_dockerfile = _detect_dockerfile(project_root)
    has_makefile = _detect_makefile(project_root)

    detected_name = (
        (py or {}).get("name")
        or (node or {}).get("name")
        or project_root.name
    )

    # Set name + variables.APP_NAME so referenced ${APP_NAME} resolves.
    data["name"] = detected_name
    variables = data.setdefault("variables", {})
    if isinstance(variables, dict):
        variables["APP_NAME"] = detected_name

    tasks: dict[str, dict[str, Any]] = {}
    if py:
        tasks.update(_python_tasks(py))
    if node:
        # Don't clobber Python tasks with same name unless user has only Node.
        for k, v in _node_tasks(node).items():
            tasks.setdefault(k, v)
    if compose is not None:
        for k, v in _compose_tasks(compose).items():
            tasks.setdefault(k, v)
    if has_dockerfile and "docker-build" not in tasks:
        tasks.update(_dockerfile_tasks(detected_name))

    # Fall back to the generic build/test/run/clean stubs when nothing
    # matched, so the file is still valid.
    if not tasks:
        tasks = data.get("tasks", {}) or {}

    # Merge existing Makefile targets into the generated tasks. Detected
    # language-specific tasks (install/test/…) take precedence — the
    # Makefile may still define unique targets like ``release`` or
    # ``docs`` which we want to preserve.
    if has_makefile:
        for mk_name, mk_task in _import_makefile_tasks(project_root / "Makefile").items():
            tasks.setdefault(mk_name, mk_task)

    # Merge workflows from ``app.doql.css`` when present. This closes the
    # sync loop: if the user ran ``doql adopt`` earlier, every workflow
    # from the spec survives into the Taskfile without overwriting tasks
    # that the project-aware detectors already emitted with richer
    # commands.
    doql_spec = project_root / "app.doql.css"
    if doql_spec.exists():
        for name, task in _import_doql_workflows(doql_spec).items():
            tasks.setdefault(name, task)

    data["tasks"] = tasks
    return _safe_dump(data)


def _import_doql_workflows(doql_path: Path) -> dict[str, dict[str, Any]]:
    """Re-use the :mod:`.from_doql` parser to lift workflows into tasks.

    We only want the ``tasks`` mapping; ``environments`` / ``name`` are
    already populated by the template + project detectors and must not be
    overwritten here.
    """
    try:
        from taskfile.scaffold.from_doql import generate_from_doql
        import yaml
    except Exception:  # pragma: no cover — import guard
        return {}
    try:
        data = yaml.safe_load(generate_from_doql(doql_path)) or {}
    except Exception:
        return {}
    raw_tasks = data.get("tasks") or {}
    if not isinstance(raw_tasks, dict):
        return {}
    return {
        name: task for name, task in raw_tasks.items()
        if isinstance(task, dict) and name != "noop"
    }


def _import_makefile_tasks(makefile_path: Path) -> dict[str, dict[str, Any]]:
    """Run the shared Makefile importer and return ``{task_name: task}``.

    Failures are swallowed — ``init`` must never crash because the user has
    an unparseable Makefile.
    """
    try:
        from taskfile.importer import parse_makefile
    except Exception:  # pragma: no cover — import guard
        return {}
    try:
        content = makefile_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        parsed = parse_makefile(content)
    except Exception:
        return {}
    raw_tasks = parsed.get("tasks") or {}
    # Mark the provenance so users can tell generated vs. imported commands
    # apart in the emitted Taskfile.yml.
    result: dict[str, dict[str, Any]] = {}
    for name, task in raw_tasks.items():
        if not isinstance(task, dict):
            continue
        task = dict(task)  # shallow copy; don't mutate parser output
        desc = task.get("desc")
        if not desc or desc.startswith("Make target:"):
            task["desc"] = f"[imported from Makefile] {name}"
        result[name] = task
    return result
