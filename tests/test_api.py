"""Tests for the Taskfile REST API (FastAPI)."""

from __future__ import annotations

import json
import pytest
import yaml
from pathlib import Path

from fastapi.testclient import TestClient

from taskfile.api.app import create_app


@pytest.fixture
def sample_taskfile(tmp_path) -> Path:
    """Create a sample Taskfile.yml for testing."""
    tf = tmp_path / "Taskfile.yml"
    tf.write_text(yaml.dump({
        "version": "1",
        "name": "test-app",
        "description": "Test application",
        "variables": {
            "APP": "myapp",
            "TAG": "latest",
            "REGISTRY": "ghcr.io/test",
        },
        "environments": {
            "local": {
                "container_runtime": "docker",
                "compose_command": "docker compose",
                "env_file": ".env.local",
            },
            "prod": {
                "ssh_host": "prod.example.com",
                "ssh_user": "deploy",
                "container_runtime": "podman",
                "service_manager": "quadlet",
            },
        },
        "environment_groups": {
            "kiosks": {
                "members": ["prod"],
                "strategy": "rolling",
                "max_parallel": 2,
            },
        },
        "platforms": {
            "web": {
                "desc": "Web application",
                "variables": {"PORT": "8080"},
                "deploy_cmd": "docker compose up -d",
            },
        },
        "functions": {
            "notify": {
                "lang": "python",
                "code": "print('notified')",
                "desc": "Send notification",
            },
        },
        "tasks": {
            "build": {
                "desc": "Build Docker image",
                "cmds": ["echo building ${APP}:${TAG}"],
                "tags": ["ci"],
                "stage": "build",
            },
            "test": {
                "desc": "Run tests",
                "cmds": ["echo testing"],
                "tags": ["ci"],
                "stage": "test",
            },
            "deploy": {
                "desc": "Deploy to environment",
                "deps": ["build"],
                "env": ["local", "prod"],
                "cmds": [
                    "@local echo deploying locally",
                    "@remote echo deploying remotely",
                ],
            },
            "logs": {
                "desc": "View logs",
                "env": ["local", "prod"],
                "platform": ["web"],
                "cmds": [
                    "@local echo local logs",
                    "@remote echo remote logs",
                ],
            },
        },
        "pipeline": {
            "stages": [
                {"name": "test", "tasks": ["test"]},
                {"name": "build", "tasks": ["build"]},
            ],
        },
    }))
    return tf


@pytest.fixture
def client(sample_taskfile) -> TestClient:
    """Create a test client with a sample Taskfile."""
    app = create_app(str(sample_taskfile))
    return TestClient(app)


# ─── Health ──────────────────────────────────────────


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["taskfile_found"] is True
        assert data["task_count"] == 4
        assert data["env_count"] == 2

    def test_health_no_taskfile(self, tmp_path):
        app = create_app(str(tmp_path / "nonexistent.yml"))
        c = TestClient(app)
        r = c.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["taskfile_found"] is False


# ─── Taskfile info ───────────────────────────────────


class TestTaskfileInfo:
    def test_get_taskfile(self, client):
        r = client.get("/taskfile")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "test-app"
        assert data["version"] == "1"
        assert data["default_env"] == "local"
        assert len(data["tasks"]) == 4
        assert len(data["environments"]) == 2
        assert len(data["platforms"]) == 1
        assert len(data["functions"]) == 1
        assert len(data["pipeline_stages"]) == 2

    def test_get_taskfile_variables(self, client):
        r = client.get("/taskfile")
        data = r.json()
        assert data["variables"]["APP"] == "myapp"
        assert data["variables"]["TAG"] == "latest"


# ─── Tasks ───────────────────────────────────────────


class TestTasks:
    def test_list_all(self, client):
        r = client.get("/tasks")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 4
        names = {t["name"] for t in data}
        assert names == {"build", "test", "deploy", "logs"}

    def test_list_filter_env(self, client):
        r = client.get("/tasks", params={"env": "prod"})
        data = r.json()
        names = {t["name"] for t in data}
        # build and test have no env_filter (match all), deploy and logs match prod
        assert "build" in names
        assert "deploy" in names
        assert "logs" in names

    def test_list_filter_platform(self, client):
        r = client.get("/tasks", params={"platform": "web"})
        data = r.json()
        names = {t["name"] for t in data}
        # logs has platform: [web], others have no platform_filter (match all)
        assert "logs" in names
        assert "build" in names

    def test_list_filter_tag(self, client):
        r = client.get("/tasks", params={"tag": "ci"})
        data = r.json()
        names = {t["name"] for t in data}
        assert names == {"build", "test"}

    def test_get_task_detail(self, client):
        r = client.get("/tasks/build")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "build"
        assert data["description"] == "Build Docker image"
        assert "echo building ${APP}:${TAG}" in data["commands"]
        assert data["tags"] == ["ci"]
        assert data["stage"] == "build"

    def test_get_task_with_deps(self, client):
        r = client.get("/tasks/deploy")
        data = r.json()
        assert data["deps"] == ["build"]
        assert data["env_filter"] == ["local", "prod"]

    def test_get_task_not_found(self, client):
        r = client.get("/tasks/nonexistent")
        assert r.status_code == 404
        assert "nonexistent" in r.json()["detail"]


# ─── Run tasks ───────────────────────────────────────


class TestRunTasks:
    def test_run_dry_run(self, client):
        r = client.post("/run", json={
            "tasks": ["build"],
            "dry_run": True,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["dry_run"] is True
        assert data["env"] == "local"
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task"] == "build"

    def test_run_unknown_task(self, client):
        r = client.post("/run", json={"tasks": ["nonexistent"]})
        assert r.status_code == 404
        assert "nonexistent" in r.json()["detail"]

    def test_run_with_env(self, client):
        r = client.post("/run", json={
            "tasks": ["test"],
            "env": "local",
            "dry_run": True,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["env"] == "local"

    def test_run_with_variables(self, client):
        r = client.post("/run", json={
            "tasks": ["build"],
            "variables": {"TAG": "v2.0"},
            "dry_run": True,
        })
        assert r.status_code == 200

    def test_run_empty_tasks(self, client):
        r = client.post("/run", json={"tasks": []})
        assert r.status_code == 422  # Pydantic validation: min_length=1


# ─── Validate ────────────────────────────────────────


class TestValidate:
    def test_validate_ok(self, client):
        r = client.post("/validate", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["task_count"] == 4
        assert data["env_count"] == 2
        assert isinstance(data["warnings"], list)

    def test_validate_with_path(self, client, sample_taskfile):
        r = client.post("/validate", json={"path": str(sample_taskfile)})
        assert r.status_code == 200
        assert r.json()["valid"] is True


# ─── Environments ────────────────────────────────────


class TestEnvironments:
    def test_list_environments(self, client):
        r = client.get("/environments")
        assert r.status_code == 200
        data = r.json()
        names = {e["name"] for e in data}
        assert "local" in names
        assert "prod" in names

    def test_local_env_details(self, client):
        r = client.get("/environments/local")
        assert r.status_code == 200
        data = r.json()
        assert data["container_runtime"] == "docker"
        assert data["compose_command"] == "docker compose"
        assert data["is_remote"] is False

    def test_prod_env_details(self, client):
        r = client.get("/environments/prod")
        assert r.status_code == 200
        data = r.json()
        assert data["ssh_host"] == "prod.example.com"
        assert data["ssh_user"] == "deploy"
        assert data["container_runtime"] == "podman"
        assert data["service_manager"] == "quadlet"
        assert data["is_remote"] is True

    def test_env_not_found(self, client):
        r = client.get("/environments/staging")
        assert r.status_code == 404


# ─── Environment Groups ─────────────────────────────


class TestGroups:
    def test_list_groups(self, client):
        r = client.get("/groups")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "kiosks"
        assert data[0]["strategy"] == "rolling"
        assert data[0]["members"] == ["prod"]


# ─── Platforms ───────────────────────────────────────


class TestPlatforms:
    def test_list_platforms(self, client):
        r = client.get("/platforms")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "web"
        assert data[0]["variables"]["PORT"] == "8080"


# ─── Functions ───────────────────────────────────────


class TestFunctions:
    def test_list_functions(self, client):
        r = client.get("/functions")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "notify"
        assert data[0]["lang"] == "python"
        assert data[0]["has_code"] is True


# ─── Pipeline ────────────────────────────────────────


class TestPipeline:
    def test_list_stages(self, client):
        r = client.get("/pipeline")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert data[0]["name"] == "test"
        assert data[0]["tasks"] == ["test"]


# ─── Variables ───────────────────────────────────────


class TestVariables:
    def test_list_variables(self, client):
        r = client.get("/variables")
        assert r.status_code == 200
        data = r.json()
        assert data["APP"] == "myapp"
        assert data["TAG"] == "latest"
        assert data["REGISTRY"] == "ghcr.io/test"


# ─── Schema ─────────────────────────────────────────


class TestSchema:
    def test_get_schema(self, client):
        r = client.get("/schema")
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Taskfile"
        assert "$defs" in data
        assert "Task" in data["$defs"]
        assert "Environment" in data["$defs"]
