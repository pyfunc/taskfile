"""Generate a ``Taskfile.yml`` from a ``.doql.css`` declarative spec.

``doql adopt`` captures a project's workflows, deploy target and environments
into ``app.doql.css``. This module is the reverse path: read that spec and
emit an equivalent ``Taskfile.yml`` so users can switch between the two
formats without hand-editing.

We parse the CSS-like format with a small local regex parser rather than
depending on the ``doql`` package — keeping ``taskfile`` installable on its
own. The features we read are deliberately minimal:

* ``app { name: "..."; version: "..."; }`` → Taskfile ``name`` / ``description``
* ``workflow[name="X"] { step-N: run cmd=...; }`` → ``tasks[X].cmds``
* ``environment[name="Y"] { env_file: ".env.Y"; }`` → ``environments[Y]``
* ``deploy { target: docker-compose; }`` → hint in description

Anything else is ignored — it's richer information that has no Taskfile
counterpart.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# ── public API ───────────────────────────────────────────────


def generate_from_doql(spec_path: str | Path) -> str:
    """Read a ``.doql.css`` file and return Taskfile YAML as a string."""
    import yaml

    path = Path(spec_path)
    text = path.read_text(encoding="utf-8")
    data = _parse_doql_css(text)

    taskfile: dict[str, Any] = {
        "version": "1",
        "name": data.get("app_name") or path.stem.replace(".doql", ""),
        "description": _build_description(data),
        "variables": {
            "APP_NAME": data.get("app_name") or "app",
        },
        "environments": _build_environments(data),
        "tasks": _build_tasks(data),
    }

    return yaml.safe_dump(taskfile, sort_keys=False, default_flow_style=False)


# ── parser ───────────────────────────────────────────────────


_BLOCK_RE = re.compile(
    r"(?P<selector>[a-zA-Z_][\w-]*(?:\[[^\]]*\])?)\s*\{(?P<body>[^{}]*)\}",
    re.MULTILINE,
)
_PROP_RE = re.compile(r"\s*([a-zA-Z_][\w-]*)\s*:\s*([^;]+);", re.MULTILINE)
_NAME_ATTR_RE = re.compile(r'\[name="([^"]+)"\]')
_TYPE_ATTR_RE = re.compile(r'\[type="([^"]+)"\]')


def _parse_doql_css(text: str) -> dict[str, Any]:
    """Return a dict with app / workflows / environments / deploy info."""
    app: dict[str, str] = {}
    workflows: list[dict[str, Any]] = []
    environments: list[dict[str, Any]] = []
    deploy: dict[str, str] = {}

    for m in _BLOCK_RE.finditer(text):
        selector = m.group("selector")
        body = m.group("body")
        props = _extract_props(body)
        tag = selector.split("[", 1)[0]

        if tag == "app":
            app.update(props)
        elif tag == "workflow":
            name_match = _NAME_ATTR_RE.search(selector)
            if name_match:
                parsed = _extract_workflow_steps(body)
                workflows.append({
                    "name": name_match.group(1),
                    "props": props,
                    "cmds": parsed["cmds"],
                    "deps": parsed["deps"],
                })
        elif tag == "environment":
            name_match = _NAME_ATTR_RE.search(selector)
            if name_match:
                environments.append({
                    "name": name_match.group(1),
                    "props": props,
                })
        elif tag == "deploy":
            deploy.update(props)

    return {
        "app_name": _unquote(app.get("name", "")),
        "app_version": _unquote(app.get("version", "")),
        "workflows": workflows,
        "environments": environments,
        "deploy": deploy,
    }


def _extract_props(body: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in _PROP_RE.finditer(body)}


def _extract_workflow_steps(body: str) -> dict[str, list[str]]:
    """Split ``step-N: ...;`` lines into ``cmds`` and ``deps`` in emission
    order.

    Two shapes produced by the adopt scanner are recognised:

    * ``step-N: run cmd=<shell>;``    → ``cmds``
    * ``step-N: depend target=<task>;`` → ``deps``
    """
    cmds: list[tuple[int, str]] = []
    deps: list[tuple[int, str]] = []
    for m in re.finditer(r"step-(\d+)\s*:\s*([^;]+);", body):
        idx = int(m.group(1))
        value = m.group(2).strip()
        kind, payload = _classify_step(value)
        if kind == "cmd" and payload:
            cmds.append((idx, payload))
        elif kind == "depend" and payload:
            deps.append((idx, payload))
    cmds.sort(key=lambda t: t[0])
    deps.sort(key=lambda t: t[0])
    return {
        "cmds": [v for _, v in cmds],
        "deps": [v for _, v in deps],
    }


def _classify_step(value: str) -> tuple[str, str | None]:
    """Return ``("cmd"|"depend", payload)`` for a raw step value."""
    # depend target=<name>
    m = re.match(r"depend\s+target=(.*)$", value)
    if m:
        return "depend", m.group(1).strip() or None
    # run cmd=<shell> (or any leading verb followed by cmd=)
    m = re.match(r"(?:\w+\s+)?cmd=(.*)$", value)
    if m:
        return "cmd", m.group(1).strip() or None
    # Bare value — treat as command
    return "cmd", value.strip() or None


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


# ── Taskfile builders ────────────────────────────────────────


def _build_description(data: dict[str, Any]) -> str:
    parts = ["Generated from app.doql.css"]
    if data.get("app_version"):
        parts.append(f"v{data['app_version']}")
    if data.get("deploy", {}).get("target"):
        parts.append(f"(deploy: {data['deploy']['target']})")
    return " ".join(parts)


def _build_environments(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    envs: dict[str, dict[str, Any]] = {}
    for env in data["environments"]:
        name = env["name"]
        props = env["props"]
        entry: dict[str, Any] = {
            "container_runtime": "docker",
            "compose_command": "docker compose",
        }
        if "env_file" in props:
            entry["env_file"] = _unquote(props["env_file"])
        if "ssh_host" in props:
            entry["ssh_host"] = _unquote(props["ssh_host"])
        envs[name] = entry
    if not envs:
        envs["local"] = {
            "container_runtime": "docker",
            "compose_command": "docker compose",
        }
    return envs


def _build_tasks(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for wf in data["workflows"]:
        name = wf["name"]
        cmds = wf.get("cmds") or []
        deps = wf.get("deps") or []
        props = wf["props"]

        task: dict[str, Any] = {
            "desc": f"[from doql] workflow: {name}",
        }
        if deps:
            task["deps"] = deps
        if cmds:
            task["cmds"] = cmds
        if "schedule" in props:
            task["schedule"] = _unquote(props["schedule"])

        tasks[name] = task

    if not tasks:
        # No workflows in the spec — leave a single stub so the Taskfile
        # parses cleanly.
        tasks["noop"] = {
            "desc": "No workflows defined in app.doql.css",
            "cmds": ["echo 'Add WORKFLOW blocks to app.doql.css and rerun.'"],
        }
    return tasks
