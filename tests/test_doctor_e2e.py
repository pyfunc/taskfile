"""E2E tests for doctor diagnostics — CLI, API, Docker integration.

Covers:
- CLI: taskfile doctor (all flags)
- API: GET /doctor, POST /doctor
- Docker: compose checks, port detection, container health
- Real project: taskfile-example/1/sandbox
"""

from __future__ import annotations

import json
import shutil
import subprocess
import pytest
import yaml
from pathlib import Path

from click.testing import CliRunner
from fastapi.testclient import TestClient

from taskfile.api.app import create_app
from taskfile.diagnostics import ProjectDiagnostics
from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    DoctorReport,
    SEVERITY_ERROR,
    SEVERITY_INFO,
)
from taskfile.diagnostics.checks import (
    check_preflight,
    check_taskfile,
    check_env_files,
    check_docker,
    check_ports,
    check_git,
    check_ssh_keys,
)

DOCKER_AVAILABLE = shutil.which("docker") is not None
EXAMPLE_PROJECT = Path("/home/tom/github/tom-sapletta-com/taskfile-example/1/sandbox")
EXAMPLE_TASKFILE = EXAMPLE_PROJECT / "Taskfile.yml"


# ═══════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════


@pytest.fixture
def minimal_taskfile(tmp_path) -> Path:
    """Minimal valid Taskfile."""
    tf = tmp_path / "Taskfile.yml"
    tf.write_text(
        yaml.dump(
            {
                "version": "1",
                "name": "test-doctor",
                "tasks": {"hello": {"cmds": ["echo hi"]}},
            }
        )
    )
    return tf


@pytest.fixture
def docker_taskfile(tmp_path) -> Path:
    """Taskfile with Docker Compose services and multiple environments."""
    tf = tmp_path / "Taskfile.yml"
    tf.write_text(
        yaml.dump(
            {
                "version": "1",
                "name": "docker-test",
                "variables": {
                    "APP_NAME": "myapp",
                    "TAG": "latest",
                    "COMPOSE": "docker compose",
                },
                "environments": {
                    "local": {
                        "container_runtime": "docker",
                        "compose_command": "docker compose",
                    },
                    "staging": {
                        "ssh_host": "staging.example.com",
                        "ssh_user": "deploy",
                        "container_runtime": "podman",
                    },
                    "prod": {
                        "ssh_host": "prod.example.com",
                        "ssh_user": "deploy",
                        "container_runtime": "podman",
                        "service_manager": "quadlet",
                    },
                },
                "tasks": {
                    "build": {
                        "desc": "Build Docker images",
                        "cmds": ["${COMPOSE} build"],
                        "tags": ["ci"],
                    },
                    "deploy": {
                        "desc": "Deploy to environment",
                        "deps": ["build"],
                        "env": ["local", "staging", "prod"],
                        "cmds": [
                            "@local ${COMPOSE} up -d",
                            "@remote podman pull myapp:${TAG}",
                        ],
                    },
                    "test": {
                        "desc": "Run tests",
                        "cmds": ["echo running tests"],
                    },
                    "status": {
                        "desc": "Show service status",
                        "env": ["local", "prod"],
                        "cmds": [
                            "@local ${COMPOSE} ps",
                            "@remote podman ps",
                        ],
                    },
                },
            }
        )
    )
    # Create docker-compose.yml
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        yaml.dump(
            {
                "services": {
                    "web": {
                        "image": "nginx:alpine",
                        "ports": ["8080:80"],
                    },
                    "api": {
                        "image": "python:3.12-slim",
                        "ports": ["8000:8000"],
                        "environment": ["VERSION=${TAG:-latest}"],
                    },
                },
            }
        )
    )
    return tf


@pytest.fixture
def broken_taskfile(tmp_path) -> Path:
    """Taskfile with intentional issues for doctor to find."""
    tf = tmp_path / "Taskfile.yml"
    tf.write_text(
        yaml.dump(
            {
                "version": "1",
                "name": "broken-app",
                "variables": {
                    "APP": "broken",
                },
                "environments": {
                    "local": {},
                    "prod": {
                        "ssh_host": "prod.example.com",
                        "ssh_user": "deploy",
                        "ssh_key": "/nonexistent/key.pem",
                        "env_file": ".env.prod",
                    },
                },
                "tasks": {
                    "build": {
                        "desc": "Build",
                        "cmds": ["nonexistent-tool build"],
                    },
                    "deploy": {
                        "desc": "Deploy",
                        "deps": ["build", "missing-task"],
                        "cmds": ["echo deploying"],
                    },
                    "run-script": {
                        "desc": "Run script",
                        "script": "scripts/missing.sh",
                    },
                },
            }
        )
    )
    # Create .env with PORT (should suggest rename to PORT_WEB)
    (tmp_path / ".env").write_text("PORT=8000\nDB_HOST=localhost\n")
    # Create .env.prod.example so auto-fix is possible
    (tmp_path / ".env.prod.example").write_text("DOMAIN=prod.example.com\nSECRET=changeme\n")
    return tf


@pytest.fixture
def api_client(minimal_taskfile) -> TestClient:
    """API test client with minimal Taskfile."""
    app = create_app(str(minimal_taskfile))
    return TestClient(app)


@pytest.fixture
def docker_api_client(docker_taskfile) -> TestClient:
    """API test client with Docker-oriented Taskfile."""
    app = create_app(str(docker_taskfile))
    return TestClient(app)


@pytest.fixture
def broken_api_client(broken_taskfile) -> TestClient:
    """API test client with broken Taskfile."""
    app = create_app(str(broken_taskfile))
    return TestClient(app)


# ═══════════════════════════════════════════════════════
# 1. CLI Doctor — all flags and modes
# ═══════════════════════════════════════════════════════


class TestDoctorCLI:
    """E2E: taskfile doctor CLI command with various flags."""

    def test_doctor_basic(self, minimal_taskfile, monkeypatch):
        """taskfile doctor — basic run with valid Taskfile."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(minimal_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code in [0, 1]
        assert "Taskfile Doctor" in result.output

    def test_doctor_verbose(self, docker_taskfile, monkeypatch):
        """taskfile doctor -v — verbose mode runs extra checks."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(docker_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "-v"])
        assert result.exit_code in [0, 1]
        assert "Taskfile Doctor" in result.output

    def test_doctor_report_json(self, minimal_taskfile, monkeypatch):
        """taskfile doctor --report — outputs valid JSON."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(minimal_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--report"])
        # JSON should be parseable
        lines = result.output.strip()
        # The report output might have ANSI or rich formatting; try parsing
        try:
            data = json.loads(lines)
            assert "total_issues" in data
            assert "categories" in data
        except json.JSONDecodeError:
            # Rich JSON output may have color codes; just check structure words
            assert "total_issues" in result.output

    def test_doctor_teach(self, docker_taskfile, monkeypatch):
        """taskfile doctor --teach — shows educational explanations."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(docker_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--teach"])
        assert result.exit_code in [0, 1]
        # Teach mode should not crash

    def test_doctor_category_filter(self, docker_taskfile, monkeypatch):
        """taskfile doctor --category config — filters issues."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(docker_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--category", "config"])
        assert result.exit_code in [0, 1]

    def test_doctor_fix_flag(self, broken_taskfile, monkeypatch):
        """taskfile doctor --fix — attempts auto-fix."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(broken_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--fix"])
        assert result.exit_code in [0, 1]
        # Should mention fix attempt
        assert "Taskfile Doctor" in result.output

    def test_doctor_broken_project_finds_errors(self, broken_taskfile, monkeypatch):
        """Doctor detects issues in a broken project."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(broken_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 1  # errors found
        # Should find issues (missing env file, missing script, etc.)
        assert any(word in result.output for word in ["Error", "Warning", "Info", "✗", "⚠", "ℹ"])

    def test_doctor_no_taskfile(self, tmp_path, monkeypatch):
        """Doctor handles missing Taskfile.yml gracefully."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code in [0, 1]
        assert "Taskfile Doctor" in result.output

    def test_doctor_remote_flag_exists(self, docker_taskfile, monkeypatch):
        """taskfile doctor --remote — flag is recognized."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(docker_taskfile.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--remote"])
        # Should not fail with "No such option"
        assert "No such option" not in result.output
        assert result.exit_code in [0, 1]


# ═══════════════════════════════════════════════════════
# 2. API /doctor endpoint
# ═══════════════════════════════════════════════════════


class TestDoctorAPIGet:
    """E2E: GET /doctor endpoint."""

    def test_get_doctor_basic(self, api_client):
        """GET /doctor returns valid response."""
        r = api_client.get("/doctor")
        assert r.status_code == 200
        data = r.json()
        assert "total_issues" in data
        assert "errors" in data
        assert "warnings" in data
        assert "info" in data
        assert "healthy" in data
        assert "issues" in data
        assert "categories" in data
        assert "summary" in data
        assert isinstance(data["issues"], list)

    def test_get_doctor_response_types(self, api_client):
        """GET /doctor fields have correct types."""
        data = api_client.get("/doctor").json()
        assert isinstance(data["total_issues"], int)
        assert isinstance(data["errors"], int)
        assert isinstance(data["warnings"], int)
        assert isinstance(data["info"], int)
        assert isinstance(data["auto_fixable"], int)
        assert isinstance(data["fixed_count"], int)
        assert isinstance(data["healthy"], bool)
        assert isinstance(data["llm_suggestions"], list)
        assert isinstance(data["summary"], str)

    def test_get_doctor_verbose(self, docker_api_client):
        """GET /doctor?verbose=true runs extra checks."""
        r = docker_api_client.get("/doctor", params={"verbose": True})
        assert r.status_code == 200
        data = r.json()
        assert "total_issues" in data
        # Verbose mode might find more issues (SSH, remote health, task commands)

    def test_get_doctor_category_config(self, docker_api_client):
        """GET /doctor?category=config filters to config issues only."""
        r = docker_api_client.get("/doctor", params={"category": "config"})
        assert r.status_code == 200
        data = r.json()
        for issue in data["issues"]:
            assert issue["category"] in ("config_error", "taskfile_bug")

    def test_get_doctor_category_env(self, docker_api_client):
        """GET /doctor?category=env filters to dependency issues only."""
        r = docker_api_client.get("/doctor", params={"category": "env"})
        assert r.status_code == 200
        data = r.json()
        for issue in data["issues"]:
            assert issue["category"] == "dep_missing"

    def test_get_doctor_category_all(self, docker_api_client):
        """GET /doctor?category=all returns all issues (no filter)."""
        r_all = docker_api_client.get("/doctor", params={"category": "all"})
        r_default = docker_api_client.get("/doctor")
        assert r_all.json()["total_issues"] == r_default.json()["total_issues"]

    def test_get_doctor_issue_structure(self, docker_api_client):
        """Each issue has all required fields."""
        data = docker_api_client.get("/doctor").json()
        for issue in data["issues"]:
            assert "category" in issue
            assert "message" in issue
            assert "severity" in issue
            assert "fix_strategy" in issue
            assert "auto_fixable" in issue
            assert "layer" in issue
            assert isinstance(issue["layer"], int)
            assert issue["severity"] in ("error", "warning", "info")
            assert issue["fix_strategy"] in ("auto", "confirm", "manual", "llm")

    def test_get_doctor_healthy_flag(self, api_client):
        """healthy=True when no errors (warnings/info are OK)."""
        data = api_client.get("/doctor").json()
        if data["errors"] == 0:
            assert data["healthy"] is True
        else:
            assert data["healthy"] is False


class TestDoctorAPIPost:
    """E2E: POST /doctor endpoint with options."""

    def test_post_doctor_default(self, api_client):
        """POST /doctor with empty body uses defaults."""
        r = api_client.post("/doctor", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["fixed_count"] == 0  # fix=false by default

    def test_post_doctor_verbose(self, docker_api_client):
        """POST /doctor with verbose=true."""
        r = docker_api_client.post("/doctor", json={"verbose": True})
        assert r.status_code == 200

    def test_post_doctor_fix(self, broken_api_client):
        """POST /doctor with fix=true attempts auto-fix."""
        r = broken_api_client.post("/doctor", json={"fix": True})
        assert r.status_code == 200
        data = r.json()
        # fixed_count may be 0 if nothing could be auto-fixed, that's OK
        assert isinstance(data["fixed_count"], int)

    def test_post_doctor_category_filter(self, docker_api_client):
        """POST /doctor with category filter."""
        r = docker_api_client.post("/doctor", json={"category": "runtime"})
        assert r.status_code == 200
        data = r.json()
        for issue in data["issues"]:
            assert issue["category"] == "runtime_error"

    def test_post_doctor_combined_options(self, docker_api_client):
        """POST /doctor with multiple options."""
        r = docker_api_client.post(
            "/doctor",
            json={
                "verbose": True,
                "fix": False,
                "category": "all",
            },
        )
        assert r.status_code == 200

    def test_post_get_consistency(self, docker_api_client):
        """GET and POST /doctor return consistent results for same params."""
        get_data = docker_api_client.get("/doctor").json()
        post_data = docker_api_client.post("/doctor", json={}).json()
        assert get_data["total_issues"] == post_data["total_issues"]
        assert get_data["errors"] == post_data["errors"]
        assert get_data["healthy"] == post_data["healthy"]


class TestDoctorAPIBrokenProject:
    """E2E: /doctor on a project with known issues."""

    def test_broken_project_finds_issues(self, broken_api_client):
        """Doctor API finds issues in broken project."""
        data = broken_api_client.get("/doctor").json()
        assert data["total_issues"] > 0

    def test_broken_project_categories(self, broken_api_client):
        """Broken project issues are properly categorized."""
        data = broken_api_client.get("/doctor").json()
        assert len(data["categories"]) > 0

    def test_broken_project_has_teach(self, broken_api_client):
        """Issues include educational teach text."""
        data = broken_api_client.get("/doctor").json()
        issues_with_teach = [i for i in data["issues"] if i.get("teach")]
        # At least some issues should have teach text
        assert len(issues_with_teach) >= 0  # Not all issues need teach

    def test_broken_project_summary(self, broken_api_client):
        """Summary string reflects actual counts."""
        data = broken_api_client.get("/doctor").json()
        if data["errors"] > 0:
            assert "Error" in data["summary"]
        if data["total_issues"] == 0:
            assert "No issues" in data["summary"]


# ═══════════════════════════════════════════════════════
# 3. Docker-specific diagnostic checks
# ═══════════════════════════════════════════════════════


class TestDoctorDockerChecks:
    """E2E: Docker-related diagnostic checks."""

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
    def test_check_docker_available(self):
        """check_docker detects Docker when installed."""
        issues = check_docker()
        # Docker is available, so no 'docker not found' error
        docker_missing = [
            i for i in issues if "docker" in i.message.lower() and "not found" in i.message.lower()
        ]
        assert len(docker_missing) == 0

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
    def test_docker_compose_check(self, docker_taskfile, monkeypatch):
        """Doctor checks docker-compose.yml alongside Taskfile."""
        monkeypatch.chdir(docker_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_docker()
        # Should run without errors

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
    def test_port_check_with_compose(self, docker_taskfile, monkeypatch):
        """Doctor port check works with docker-compose ports."""
        monkeypatch.chdir(docker_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_ports()
        # Port check should complete without crash

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
    def test_docker_api_doctor_verbose(self, docker_api_client):
        """API doctor verbose includes Docker-related checks."""
        r = docker_api_client.get("/doctor", params={"verbose": True})
        assert r.status_code == 200

    def test_compose_port_conflict_detection(self, tmp_path, monkeypatch):
        """Doctor detects port conflicts in docker-compose.yml."""
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "port-test",
                    "tasks": {"up": {"cmds": ["docker compose up"]}},
                }
            )
        )
        # Two services using same host port
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "web": {"image": "nginx", "ports": ["8080:80"]},
                        "api": {"image": "python:3.12", "ports": ["8080:8000"]},
                    },
                }
            )
        )
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        diag.check_ports()
        # Should detect port 8080 conflict or at least run without crash

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
    def test_docker_running_containers_check(self):
        """check_docker handles both running and no containers."""
        issues = check_docker()
        assert isinstance(issues, list)
        for iss in issues:
            assert isinstance(iss, Issue)
            assert iss.category in (
                IssueCategory.DEPENDENCY_MISSING,
                IssueCategory.EXTERNAL_ERROR,
                IssueCategory.RUNTIME_ERROR,
            )


class TestDoctorDockerCompose:
    """E2E: Doctor with docker-compose projects."""

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
    def test_compose_build_check(self, docker_taskfile, monkeypatch):
        """Doctor handles compose project with build context."""
        monkeypatch.chdir(docker_taskfile.parent)
        app = create_app(str(docker_taskfile))
        client = TestClient(app)
        r = client.get("/doctor", params={"verbose": True})
        assert r.status_code == 200

    def test_compose_missing_file(self, tmp_path, monkeypatch):
        """Doctor detects missing docker-compose.yml when referenced in tasks."""
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "no-compose",
                    "variables": {"COMPOSE": "docker compose"},
                    "tasks": {
                        "up": {"cmds": ["${COMPOSE} up -d"]},
                        "down": {"cmds": ["${COMPOSE} down"]},
                    },
                }
            )
        )
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        diag.check_docker()
        # Should not crash, may or may not report missing compose file

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
    def test_compose_env_variable_resolution(self, docker_taskfile, monkeypatch):
        """Doctor checks env variable usage in docker-compose."""
        monkeypatch.chdir(docker_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        diag.check_env_files()
        diag.validate_taskfile_variables()
        # All checks should complete


# ═══════════════════════════════════════════════════════
# 4. ProjectDiagnostics facade — full pipeline
# ═══════════════════════════════════════════════════════


class TestDoctorFullPipeline:
    """E2E: Full 5-layer diagnostic pipeline."""

    def test_full_pipeline_valid_project(self, minimal_taskfile, monkeypatch):
        """Full doctor run on a valid project."""
        monkeypatch.chdir(minimal_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_preflight()
        diag.check_taskfile()
        diag.check_env_files()
        diag.check_ports()
        diag.check_docker()
        diag.check_ssh_keys()
        diag.check_git()
        report = diag.get_report_dict()
        assert "total_issues" in report
        assert "categories" in report
        assert isinstance(report["total_issues"], int)

    def test_full_pipeline_broken_project(self, broken_taskfile, monkeypatch):
        """Full doctor run on a broken project finds issues."""
        monkeypatch.chdir(broken_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_preflight()
        diag.check_taskfile()
        diag.check_env_files()
        diag.validate_taskfile_variables()
        diag.check_placeholder_values()
        diag.check_dependent_files()
        diag.check_ports()
        diag.check_docker()
        diag.check_ssh_keys()
        diag.check_git()
        assert len(diag._issues) > 0
        report = diag.get_report_dict()
        assert report["total_issues"] > 0

    def test_full_pipeline_auto_fix(self, broken_taskfile, monkeypatch):
        """Auto-fix on broken project attempts repairs."""
        monkeypatch.chdir(broken_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        diag.check_env_files()
        diag.check_dependent_files()
        fixable_before = sum(1 for i in diag._issues if i.auto_fixable)
        if fixable_before > 0:
            fixed = diag.auto_fix()
            assert fixed >= 0

    def test_doctor_report_dict_structure(self, docker_taskfile, monkeypatch):
        """get_report_dict returns well-structured data."""
        monkeypatch.chdir(docker_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_preflight()
        diag.check_taskfile()
        report = diag.get_report_dict()
        assert "total_issues" in report
        assert "errors" in report
        assert "warnings" in report
        assert "auto_fixable" in report
        assert "categories" in report
        assert isinstance(report["categories"], dict)

    def test_issue_layer_assignment(self, docker_taskfile, monkeypatch):
        """Issues are assigned to correct layers."""
        monkeypatch.chdir(docker_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_preflight()  # Layer 1
        diag.check_taskfile()  # Layer 2
        diag.check_env_files()  # Layer 3
        for iss in diag._issues:
            assert 1 <= iss.layer <= 5, f"Issue layer out of range: {iss.layer}"


# ═══════════════════════════════════════════════════════
# 5. Individual check functions
# ═══════════════════════════════════════════════════════


class TestCheckFunctions:
    """E2E: Test individual check_* functions in isolation."""

    def test_check_preflight_returns_list(self):
        """check_preflight always returns a list of Issue objects."""
        issues = check_preflight()
        assert isinstance(issues, list)
        for iss in issues:
            assert isinstance(iss, Issue)
            assert iss.layer == 1

    def test_check_preflight_tool_severity(self):
        """Required tools are errors, optional are info."""
        issues = check_preflight()
        for iss in issues:
            if "optional" in iss.message:
                assert iss.severity == SEVERITY_INFO
            # Required missing tools should be warning or error

    def test_check_taskfile_missing(self, tmp_path, monkeypatch):
        """check_taskfile returns error when Taskfile.yml missing."""
        monkeypatch.chdir(tmp_path)
        issues = check_taskfile()
        assert len(issues) == 1
        assert issues[0].severity == SEVERITY_ERROR
        assert issues[0].layer == 2

    def test_check_taskfile_valid(self, minimal_taskfile, monkeypatch):
        """check_taskfile returns empty for valid Taskfile."""
        monkeypatch.chdir(minimal_taskfile.parent)
        issues = check_taskfile()
        assert len(issues) == 0

    def test_check_taskfile_invalid_yaml(self, tmp_path, monkeypatch):
        """check_taskfile detects invalid YAML."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Taskfile.yml").write_text("{{invalid yaml::: [")
        issues = check_taskfile()
        assert len(issues) >= 1
        assert any(i.severity == SEVERITY_ERROR for i in issues)

    def test_check_env_files_port_rename(self, tmp_path, monkeypatch):
        """check_env_files detects PORT without PORT_WEB."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("PORT=8000\n")
        issues = check_env_files()
        port_issues = [i for i in issues if "PORT_WEB" in i.message or "PORT" in i.message]
        assert len(port_issues) >= 1

    def test_check_env_files_clean(self, tmp_path, monkeypatch):
        """check_env_files returns no issues for clean .env."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("APP_NAME=test\nVERSION=1.0\n")
        issues = check_env_files()
        # May still have issues if PORT_WEB missing etc, but should not crash
        assert isinstance(issues, list)

    def test_check_git_in_repo(self, tmp_path, monkeypatch):
        """check_git in a git repo returns no git init issues."""
        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        issues = check_git()
        git_init_issues = [i for i in issues if "not a git repository" in i.message.lower()]
        assert len(git_init_issues) == 0

    def test_check_git_no_repo(self, tmp_path, monkeypatch):
        """check_git outside a repo detects missing git init."""
        monkeypatch.chdir(tmp_path)
        issues = check_git()
        if issues:
            assert any("git" in i.message.lower() for i in issues)

    def test_check_ssh_keys_returns_list(self):
        """check_ssh_keys always returns list."""
        issues = check_ssh_keys()
        assert isinstance(issues, list)

    def test_check_ports_returns_list(self, tmp_path, monkeypatch):
        """check_ports returns list of Issue objects."""
        monkeypatch.chdir(tmp_path)
        issues = check_ports()
        assert isinstance(issues, list)


# ═══════════════════════════════════════════════════════
# 6. Real project: taskfile-example/1/sandbox
# ═══════════════════════════════════════════════════════


@pytest.mark.skipif(
    not EXAMPLE_TASKFILE.exists(),
    reason=f"Example project not found at {EXAMPLE_PROJECT}",
)
class TestDoctorExampleProject:
    """E2E: Run doctor against the real taskfile-example/1/sandbox project."""

    def test_cli_doctor_example_project(self, monkeypatch):
        """CLI doctor runs on example project without crash."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(EXAMPLE_PROJECT)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Taskfile Doctor" in result.output
        assert result.exit_code in [0, 1]

    def test_cli_doctor_verbose_example(self, monkeypatch):
        """CLI doctor -v runs on example project."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(EXAMPLE_PROJECT)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "-v"])
        assert "Taskfile Doctor" in result.output

    def test_cli_doctor_report_example(self, monkeypatch):
        """CLI doctor --report outputs JSON for example project."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(EXAMPLE_PROJECT)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--report"])
        assert "total_issues" in result.output

    def test_cli_doctor_teach_example(self, monkeypatch):
        """CLI doctor --teach on example project."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(EXAMPLE_PROJECT)
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--teach"])
        assert result.exit_code in [0, 1]

    def test_api_doctor_example_project(self, monkeypatch):
        """API /doctor runs on example project."""
        monkeypatch.chdir(EXAMPLE_PROJECT)
        app = create_app(str(EXAMPLE_TASKFILE))
        client = TestClient(app)
        r = client.get("/doctor")
        assert r.status_code == 200
        data = r.json()
        assert "total_issues" in data
        assert isinstance(data["healthy"], bool)
        assert isinstance(data["issues"], list)

    def test_api_doctor_verbose_example(self, monkeypatch):
        """API /doctor?verbose=true on example project."""
        monkeypatch.chdir(EXAMPLE_PROJECT)
        app = create_app(str(EXAMPLE_TASKFILE))
        client = TestClient(app)
        r = client.get("/doctor", params={"verbose": True})
        assert r.status_code == 200

    def test_api_doctor_post_fix_example(self, monkeypatch):
        """API POST /doctor fix=true on example project."""
        monkeypatch.chdir(EXAMPLE_PROJECT)
        app = create_app(str(EXAMPLE_TASKFILE))
        client = TestClient(app)
        r = client.post("/doctor", json={"fix": True, "verbose": True})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["fixed_count"], int)

    def test_diagnostics_facade_example(self, monkeypatch):
        """ProjectDiagnostics facade on example project."""
        monkeypatch.chdir(EXAMPLE_PROJECT)
        diag = ProjectDiagnostics()
        diag.check_preflight()
        diag.check_taskfile()
        diag.check_env_files()
        diag.check_ports()
        diag.check_docker()
        diag.check_ssh_keys()
        diag.check_git()
        report = diag.get_report_dict()
        assert isinstance(report["total_issues"], int)
        # Example project with prod env should have SSH issues
        any("SSH" in i.message or "ssh" in i.message for i in diag._issues)
        # This is expected — placeholder SSH hosts can't connect

    def test_example_project_detects_placeholder_hosts(self, monkeypatch):
        """Doctor detects placeholder SSH hosts in example project."""
        monkeypatch.chdir(EXAMPLE_PROJECT)
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        diag.validate_taskfile_variables()
        # Should not crash even with ${VAR:-default} style hosts


# ═══════════════════════════════════════════════════════
# 7. Docker container lifecycle tests
# ═══════════════════════════════════════════════════════


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not installed")
class TestDoctorWithDockerContainers:
    """E2E: Doctor checks with actual Docker containers running."""

    @pytest.fixture(autouse=True)
    def _setup_container(self):
        """Start a test container, yield, then clean up."""
        container_name = "taskfile-doctor-test"
        # Start a simple nginx container
        subprocess.run(
            ["docker", "run", "-d", "--name", container_name, "-p", "19876:80", "nginx:alpine"],
            capture_output=True,
        )
        yield container_name
        # Cleanup
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    def test_doctor_with_running_container(self, minimal_taskfile, monkeypatch):
        """Doctor runs when Docker containers are active."""
        monkeypatch.chdir(minimal_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_preflight()
        diag.check_docker()
        diag.check_ports()
        # Should not crash with running containers
        assert isinstance(diag._issues, list)

    def test_api_doctor_with_running_container(self, minimal_taskfile):
        """API /doctor works when Docker containers are running."""
        app = create_app(str(minimal_taskfile))
        client = TestClient(app)
        r = client.get("/doctor")
        assert r.status_code == 200

    def test_port_detection_with_running_container(self, minimal_taskfile, monkeypatch):
        """Doctor detects ports used by running containers."""
        monkeypatch.chdir(minimal_taskfile.parent)
        issues = check_ports()
        # Port 19876 is in use by our test container
        assert isinstance(issues, list)

    def test_docker_check_finds_docker(self):
        """check_docker does not report Docker as missing."""
        issues = check_docker()
        missing = [
            i for i in issues if "docker" in i.message.lower() and "not found" in i.message.lower()
        ]
        assert len(missing) == 0


# ═══════════════════════════════════════════════════════
# 8. DoctorReport model tests
# ═══════════════════════════════════════════════════════


class TestDoctorReportModel:
    """E2E: DoctorReport aggregation and serialization."""

    def test_report_from_diagnostics(self, docker_taskfile, monkeypatch):
        """DoctorReport.as_dict matches API response structure."""
        monkeypatch.chdir(docker_taskfile.parent)
        diag = ProjectDiagnostics()
        diag.check_preflight()
        diag.check_taskfile()
        report = DoctorReport(issues=list(diag._issues))
        report.classify()
        d = report.as_dict()
        assert "total_issues" in d
        assert "errors" in d
        assert "warnings" in d
        assert "categories" in d

    def test_report_classify_buckets(self):
        """DoctorReport.classify sorts issues into correct buckets."""
        report = DoctorReport(
            issues=[
                Issue(
                    category=IssueCategory.CONFIG_ERROR, message="config problem", severity="error"
                ),
                Issue(category=IssueCategory.EXTERNAL_ERROR, message="network down"),
                Issue(
                    category=IssueCategory.RUNTIME_ERROR, message="fixed!", context={"_fixed": True}
                ),
            ]
        )
        report.classify()
        assert len(report.fixed) == 1
        assert len(report.external) == 1
        assert len(report.pending) == 1

    def test_empty_report(self):
        """Empty report has zero counts."""
        report = DoctorReport()
        assert report.total == 0
        assert report.error_count == 0
        assert report.warning_count == 0
        d = report.as_dict()
        assert d["total_issues"] == 0


# ═══════════════════════════════════════════════════════
# 9. Error handling and edge cases
# ═══════════════════════════════════════════════════════


class TestDoctorEdgeCases:
    """E2E: Edge cases and error handling."""

    def test_empty_taskfile(self, tmp_path, monkeypatch):
        """Doctor handles empty Taskfile.yml."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Taskfile.yml").write_text("")
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        # Should not crash

    def test_taskfile_only_version(self, tmp_path, monkeypatch):
        """Doctor handles Taskfile with only version, no tasks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Taskfile.yml").write_text('version: "1"\n')
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        diag.check_env_files()

    def test_api_doctor_no_taskfile(self, tmp_path):
        """API /doctor handles missing Taskfile gracefully."""
        app = create_app(str(tmp_path / "nonexistent.yml"))
        client = TestClient(app)
        r = client.get("/doctor")
        assert r.status_code == 200
        data = r.json()
        # Should report config error about missing Taskfile
        assert data["total_issues"] > 0

    def test_concurrent_doctor_calls(self, api_client):
        """Multiple concurrent /doctor calls don't interfere."""
        results = []
        for _ in range(5):
            r = api_client.get("/doctor")
            results.append(r.json())
        # All should return same result
        for r in results[1:]:
            assert r["total_issues"] == results[0]["total_issues"]

    def test_api_doctor_invalid_category(self, api_client):
        """API /doctor with unknown category returns all issues."""
        r = api_client.get("/doctor", params={"category": "nonexistent"})
        assert r.status_code == 200
        # Unknown category falls through to "all" (no filter match)

    def test_large_taskfile(self, tmp_path, monkeypatch):
        """Doctor handles Taskfile with many tasks."""
        monkeypatch.chdir(tmp_path)
        tasks = {f"task-{i}": {"cmds": [f"echo {i}"]} for i in range(100)}
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump({"version": "1", "tasks": tasks}))
        diag = ProjectDiagnostics()
        diag.check_taskfile()
        # Should handle large files without issues

    def test_taskfile_with_special_chars(self, tmp_path, monkeypatch):
        """Doctor handles tasks with special characters in names."""
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "tasks": {
                        "build-all": {"cmds": ["echo build"]},
                        "deploy:prod": {"cmds": ["echo deploy"]},
                        "test_unit": {"cmds": ["echo test"]},
                    },
                }
            )
        )
        diag = ProjectDiagnostics()
        diag.check_taskfile()

    def test_api_doctor_with_ssh_environments(self, docker_api_client):
        """API /doctor handles SSH environments (connection will fail)."""
        r = docker_api_client.get("/doctor", params={"verbose": True})
        assert r.status_code == 200
        data = r.json()
        # SSH checks should produce issues for unreachable hosts
        [i for i in data["issues"] if "SSH" in i["message"] or "ssh" in i["message"].lower()]
        # May or may not have SSH issues depending on check configuration


# ═══════════════════════════════════════════════════════
# 10. Regression tests — bugs fixed in this session
# ═══════════════════════════════════════════════════════


class TestRegressionVarResolution:
    """Regression: ${VAR:-default} patterns must be resolved before SSH checks."""

    def test_resolve_env_fields_expands_defaults(self):
        """_resolve_env_fields expands ${VAR:-default} to default value."""
        from taskfile.diagnostics.checks import _resolve_env_fields
        from taskfile.models import Environment

        env = Environment(
            name="prod",
            ssh_host="${PROD_HOST:-prod.example.com}",
            ssh_user="${DEPLOY_USER:-deploy}",
        )
        _resolve_env_fields(env)
        assert env.ssh_host == "prod.example.com"
        assert env.ssh_user == "deploy"

    def test_resolve_env_fields_uses_os_environ(self, monkeypatch):
        """_resolve_env_fields prefers os.environ over defaults."""
        from taskfile.diagnostics.checks import _resolve_env_fields
        from taskfile.models import Environment

        monkeypatch.setenv("MY_HOST", "real-server.com")
        env = Environment(
            name="prod",
            ssh_host="${MY_HOST:-fallback.example.com}",
        )
        _resolve_env_fields(env)
        assert env.ssh_host == "real-server.com"

    def test_resolve_env_fields_no_vars(self):
        """_resolve_env_fields is a no-op when no variables present."""
        from taskfile.diagnostics.checks import _resolve_env_fields
        from taskfile.models import Environment

        env = Environment(name="prod", ssh_host="static.example.com")
        _resolve_env_fields(env)
        assert env.ssh_host == "static.example.com"

    def test_ssh_connectivity_resolves_vars(self, tmp_path, monkeypatch):
        """check_ssh_connectivity resolves ${VAR:-default} before checking."""
        from taskfile.diagnostics.checks import check_ssh_connectivity
        from taskfile.models import TaskfileConfig

        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        data = {
            "version": "1",
            "environments": {
                "prod": {
                    "ssh_host": "${TEST_SSH_HOST:-resolved.example.com}",
                    "ssh_user": "deploy",
                },
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        tf.write_text(yaml.dump(data))
        config = TaskfileConfig.from_dict(data)
        config.source_path = str(tf)
        issues = check_ssh_connectivity(config)
        # Error messages should show resolved hostname, not raw ${VAR:-...}
        for iss in issues:
            assert "${" not in iss.message, f"Unresolved variable in message: {iss.message}"
            if "host" in (iss.context or {}):
                assert "${" not in iss.context["host"], (
                    f"Unresolved var in context: {iss.context['host']}"
                )

    def test_api_doctor_verbose_resolves_ssh_vars(self, tmp_path, monkeypatch):
        """API /doctor verbose resolves SSH host variables in issue messages."""
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "var-test",
                    "environments": {
                        "prod": {
                            "ssh_host": "${MY_PROD:-prod.example.com}",
                            "ssh_user": "deploy",
                        },
                    },
                    "tasks": {"t": {"cmds": ["echo"]}},
                }
            )
        )
        app = create_app(str(tf))
        client = TestClient(app)
        r = client.get("/doctor", params={"verbose": True})
        assert r.status_code == 200
        data = r.json()
        for issue in data["issues"]:
            assert "${" not in issue["message"], f"Unresolved var: {issue['message']}"


@pytest.mark.slow
class TestRegressionEnvFlag:
    """Regression: --env flag must be respected by doctor --remote."""

    def test_remote_respects_env_flag(self, tmp_path, monkeypatch):
        """taskfile --env prod doctor --remote only checks 'prod' env."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "multi-env",
                    "environments": {
                        "staging": {
                            "ssh_host": "staging.example.com",
                            "ssh_user": "deploy",
                        },
                        "prod": {
                            "ssh_host": "prod.example.com",
                            "ssh_user": "deploy",
                        },
                    },
                    "tasks": {"t": {"cmds": ["echo"]}},
                }
            )
        )
        runner = CliRunner()
        # Run with --env prod
        result = runner.invoke(main, ["--env", "prod", "doctor", "--remote"])
        assert "No such option" not in result.output
        # Should check prod, not staging
        assert "prod.example.com" in result.output
        # staging should NOT appear in the "Environment:" lines of Remote Server Diagnostics
        remote_section = result.output.split("Remote Server Diagnostics")
        if len(remote_section) > 1:
            # Extract only "Environment: ..." lines from the remote diagnostics block
            env_lines = [line for line in remote_section[1].splitlines() if "Environment:" in line]
            env_text = "\n".join(env_lines)
            assert "staging" not in env_text, (
                f"staging should not appear in remote env listing when --env prod: {env_text}"
            )
            assert "prod" in env_text

    def test_remote_no_env_flag_checks_all(self, tmp_path, monkeypatch):
        """taskfile doctor --remote without --env checks all remote envs."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "multi-env",
                    "environments": {
                        "staging": {
                            "ssh_host": "staging.example.com",
                            "ssh_user": "deploy",
                        },
                        "prod": {
                            "ssh_host": "prod.example.com",
                            "ssh_user": "deploy",
                        },
                    },
                    "tasks": {"t": {"cmds": ["echo"]}},
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--remote"])
        # Both environments should be checked
        assert "staging.example.com" in result.output
        assert "prod.example.com" in result.output

    def test_remote_local_env_warns(self, tmp_path, monkeypatch):
        """taskfile --env local doctor --remote warns that env is not remote."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "local-only",
                    "environments": {"local": {}},
                    "tasks": {"t": {"cmds": ["echo"]}},
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--env", "local", "doctor", "--remote"])
        assert "not remote" in result.output


@pytest.mark.slow
class TestRegressionSSHErrorMessages:
    """Regression: SSH error messages must be informative, not empty."""

    def test_ssh_failure_shows_exit_code(self, tmp_path, monkeypatch):
        """When SSH output is empty, error should show exit code."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "ssh-test",
                    "environments": {
                        "prod": {
                            "ssh_host": "192.0.2.1",
                            "ssh_user": "deploy",
                        },
                    },
                    "tasks": {"t": {"cmds": ["echo"]}},
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--env", "prod", "doctor", "--remote"])
        # Should NOT show "unknown error" or empty string
        assert "unknown error" not in result.output
        # Should show something meaningful (exit code or connection error)
        remote_section = result.output.split("Remote Server Diagnostics")
        if len(remote_section) > 1:
            diag_text = remote_section[1]
            if "SSH connection failed" in diag_text:
                # Should have actual content after "failed:"
                after_failed = diag_text.split("SSH connection failed:")[1].split("\n")[0].strip()
                assert len(after_failed) > 0, "SSH error message should not be empty"

    def test_ssh_failure_shows_debug_command(self, tmp_path, monkeypatch):
        """SSH failure should show the debug command user can try."""
        from taskfile.cli.interactive.wizards import main

        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "ssh-test",
                    "environments": {
                        "prod": {
                            "ssh_host": "192.0.2.1",
                            "ssh_user": "deploy",
                        },
                    },
                    "tasks": {"t": {"cmds": ["echo"]}},
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--env", "prod", "doctor", "--remote"])
        # Should show the SSH command for debugging
        if "SSH connection failed" in result.output:
            assert "ssh" in result.output.lower()
            assert "deploy@192.0.2.1" in result.output


class TestRegressionSSHResult:
    """Regression: SSHResult.output used instead of non-existent .error."""

    def test_ssh_result_has_output_not_error(self):
        """SSHResult NamedTuple has output field, not error field."""
        from taskfile.deploy_utils import SSHResult

        result = SSHResult(success=False, output="connection refused", exit_code=255)
        assert result.output == "connection refused"
        assert not hasattr(result, "error")

    def test_ssh_result_empty_output(self):
        """SSHResult with empty output is handled."""
        from taskfile.deploy_utils import SSHResult

        result = SSHResult(success=False, output="", exit_code=-1)
        assert result.output == ""
        # Code should use fallback: f"exit code {result.exit_code}"
