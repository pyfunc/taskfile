"""Tests for taskfile package."""

import pytest
import yaml
from pathlib import Path

from taskfile.models import TaskfileConfig, Task, Environment
from taskfile.parser import load_taskfile, validate_taskfile, TaskfileNotFoundError
from taskfile.runner import TaskfileRunner
from taskfile.scaffold import generate_taskfile
from taskfile.compose import ComposeFile, load_env_file, resolve_variables
from taskfile.quadlet import generate_container_unit, compose_to_quadlet, generate_network_unit


# ─── Model Tests ─────────────────────────────────────


class TestEnvironment:
    def test_ssh_target(self):
        env = Environment(name="prod", ssh_host="example.com", ssh_user="deploy")
        assert env.ssh_target == "deploy@example.com"

    def test_ssh_target_none_when_no_host(self):
        env = Environment(name="local")
        assert env.ssh_target is None

    def test_resolve_variables(self):
        env = Environment(name="prod", variables={"TAG": "v2"})
        result = env.resolve_variables({"APP": "test", "TAG": "v1"})
        assert result["APP"] == "test"
        assert result["TAG"] == "v2"  # env overrides global

    def test_new_fields_defaults(self):
        env = Environment(name="local")
        assert env.compose_file == "docker-compose.yml"
        assert env.env_file is None
        assert env.quadlet_dir == "deploy/quadlet"
        assert env.quadlet_remote_dir == "~/.config/containers/systemd"

    def test_new_fields_from_dict(self):
        data = {
            "version": "1",
            "environments": {
                "prod": {
                    "ssh_host": "example.com",
                    "env_file": ".env.prod",
                    "quadlet_dir": "deploy/prod",
                    "quadlet_remote_dir": "/etc/containers/systemd",
                    "service_manager": "quadlet",
                }
            },
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        prod = config.environments["prod"]
        assert prod.env_file == ".env.prod"
        assert prod.quadlet_dir == "deploy/prod"
        assert prod.quadlet_remote_dir == "/etc/containers/systemd"
        assert prod.service_manager == "quadlet"

class TestTask:
    def test_should_run_on_all_envs(self):
        task = Task(name="build", env_filter=None)
        assert task.should_run_on("local") is True
        assert task.should_run_on("prod") is True

    def test_should_run_on_filtered(self):
        task = Task(name="deploy", env_filter=["prod", "staging"])
        assert task.should_run_on("prod") is True
        assert task.should_run_on("local") is False

    def test_parallel_default_false(self):
        task = Task(name="t")
        assert task.parallel is False

    def test_parallel_from_dict(self):
        data = {
            "tasks": {
                "pub": {
                    "cmds": ["echo"],
                    "parallel": True,
                    "deps": ["a", "b"],
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["pub"].parallel is True

    def test_continue_on_error_alias(self):
        """Test that continue_on_error maps to ignore_errors."""
        data = {
            "tasks": {
                "pub": {
                    "cmds": ["echo"],
                    "continue_on_error": True,
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["pub"].ignore_errors is True

    def test_condition_field(self):
        data = {
            "tasks": {
                "pub": {
                    "cmds": ["echo"],
                    "condition": "test -f pyproject.toml",
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["pub"].condition == "test -f pyproject.toml"

class TestTaskfileConfig:
    def test_from_dict_minimal(self):
        data = {
            "version": "1",
            "name": "test",
            "tasks": {
                "build": {"cmds": ["echo build"]},
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.name == "test"
        assert "build" in config.tasks
        assert "local" in config.environments

    def test_from_dict_shorthand_tasks(self):
        data = {
            "tasks": {
                "hello": ["echo hello", "echo world"],
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["hello"].commands == ["echo hello", "echo world"]

    def test_from_dict_full(self):
        data = {
            "version": "1",
            "name": "full-test",
            "variables": {"APP": "myapp"},
            "default_env": "local",
            "environments": {
                "local": {"container_runtime": "docker"},
                "prod": {
                    "ssh_host": "server.com",
                    "ssh_user": "deploy",
                    "container_runtime": "podman",
                },
            },
            "tasks": {
                "build": {
                    "desc": "Build it",
                    "cmds": ["docker build ."],
                    "deps": [],
                },
                "deploy": {
                    "desc": "Deploy it",
                    "cmds": ["echo deploy"],
                    "deps": ["build"],
                    "env": ["prod"],
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.environments["prod"].ssh_host == "server.com"
        assert config.tasks["deploy"].env_filter == ["prod"]
        assert config.tasks["deploy"].deps == ["build"]

class TestEnvFile:
    def test_load_env_file(self, tmp_path):
        envfile = tmp_path / ".env.test"
        envfile.write_text(
            "DOMAIN=example.com\n"
            "TAG=v1.2.3\n"
            'QUOTED="hello world"\n'
            "# comment\n"
            "\n"
            "EMPTY=\n"
        )
        env = load_env_file(envfile)
        assert env["DOMAIN"] == "example.com"
        assert env["TAG"] == "v1.2.3"
        assert env["QUOTED"] == "hello world"
        assert env["EMPTY"] == ""

    def test_load_missing_env_file(self):
        env = load_env_file("/nonexistent/.env")
        assert env == {}

class TestResolveVariables:
    def test_simple_var(self):
        assert resolve_variables("${APP}", {"APP": "myapp"}) == "myapp"

    def test_default_value(self):
        assert resolve_variables("${APP:-fallback}", {}) == "fallback"

    def test_default_not_used(self):
        assert resolve_variables("${APP:-fallback}", {"APP": "real"}) == "real"

    def test_simple_dollar(self):
        assert resolve_variables("$APP", {"APP": "myapp"}) == "myapp"

    def test_unresolved_kept(self):
        result = resolve_variables("${UNKNOWN}", {})
        assert result == "${UNKNOWN}"

    def test_mixed(self):
        result = resolve_variables(
            "Host(`${APP}.${DOMAIN:-localhost}`)",
            {"APP": "web"},
        )
        assert result == "Host(`web.localhost`)"

class TestPipelineConfig:
    """Test PipelineConfig parsing."""

    def test_from_dict_basic(self):
        from taskfile.models import PipelineConfig
        data = {
            "stages": [
                {"name": "test", "tasks": ["lint", "test"]},
                {"name": "build", "tasks": ["build"], "docker_in_docker": True},
                {"name": "deploy", "tasks": ["deploy"], "env": "prod", "when": "manual"},
            ],
            "branches": ["main", "develop"],
        }
        p = PipelineConfig.from_dict(data)
        assert len(p.stages) == 3
        assert p.stages[0].name == "test"
        assert p.stages[0].tasks == ["lint", "test"]
        assert p.stages[1].docker_in_docker is True
        assert p.stages[2].env == "prod"
        assert p.stages[2].when == "manual"
        assert p.branches == ["main", "develop"]

    def test_from_dict_shorthand(self):
        from taskfile.models import PipelineConfig
        data = {"stages": ["test", "build", "deploy"]}
        p = PipelineConfig.from_dict(data)
        assert len(p.stages) == 3
        assert p.stages[0].name == "test"
        assert p.stages[0].tasks == ["test"]

    def test_from_dict_empty(self):
        from taskfile.models import PipelineConfig
        p = PipelineConfig.from_dict({})
        assert p.stages == []
        assert p.python_version == "3.12"
        assert p.runner_image == "ubuntu-latest"

    def test_infer_from_tasks(self):
        from taskfile.models import PipelineConfig, Task
        p = PipelineConfig.from_dict({})
        tasks = {
            "lint": Task(name="lint", stage="test"),
            "unit-test": Task(name="unit-test", stage="test"),
            "build": Task(name="build", stage="build"),
            "deploy": Task(name="deploy", stage="deploy"),
            "cleanup": Task(name="cleanup"),  # no stage
        }
        p.infer_from_tasks(tasks)
        assert len(p.stages) == 3
        assert p.stages[0].name == "test"
        assert set(p.stages[0].tasks) == {"lint", "unit-test"}

    def test_infer_skipped_when_stages_exist(self):
        from taskfile.models import PipelineConfig, Task
        data = {"stages": [{"name": "custom", "tasks": ["build"]}]}
        p = PipelineConfig.from_dict(data)
        tasks = {"lint": Task(name="lint", stage="test")}
        p.infer_from_tasks(tasks)
        # Should NOT add inferred stages because explicit stages exist
        assert len(p.stages) == 1
        assert p.stages[0].name == "custom"

    def test_taskfile_config_parses_pipeline(self):
        from taskfile.models import TaskfileConfig
        data = {
            "name": "myproject",
            "tasks": {
                "test": {"cmds": ["pytest"], "stage": "test"},
                "build": {"cmds": ["docker build ."], "stage": "build"},
            },
            "pipeline": {
                "stages": [
                    {"name": "test", "tasks": ["test"]},
                    {"name": "build", "tasks": ["build"], "docker_in_docker": True},
                ],
                "branches": ["main"],
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert len(config.pipeline.stages) == 2
        assert config.pipeline.stages[1].docker_in_docker is True
        assert config.tasks["test"].stage == "test"

    def test_taskfile_config_infers_pipeline(self):
        from taskfile.models import TaskfileConfig
        data = {
            "tasks": {
                "lint": {"cmds": ["ruff ."], "stage": "test"},
                "test": {"cmds": ["pytest"], "stage": "test"},
                "build": {"cmds": ["docker build ."], "stage": "build"},
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert len(config.pipeline.stages) == 2


class TestEnvironmentGroup:
    """Test EnvironmentGroup parsing."""

    def test_parse_groups(self):
        from taskfile.models import TaskfileConfig
        data = {
            "environment_groups": {
                "kiosks": {
                    "members": ["kiosk-lobby", "kiosk-cafe"],
                    "strategy": "rolling",
                    "max_parallel": 1,
                },
                "sensors": {
                    "members": ["sensor-yard", "sensor-roof"],
                    "strategy": "parallel",
                    "max_parallel": 5,
                },
            },
            "environments": {
                "kiosk-lobby": {"ssh_host": "192.168.1.50", "ssh_user": "pi"},
                "kiosk-cafe": {"ssh_host": "192.168.1.51", "ssh_user": "pi"},
                "sensor-yard": {"ssh_host": "192.168.1.60", "ssh_user": "pi"},
                "sensor-roof": {"ssh_host": "192.168.1.61", "ssh_user": "pi"},
            },
            "tasks": {"deploy": {"cmds": ["echo deploy"]}},
        }
        config = TaskfileConfig.from_dict(data)
        assert len(config.environment_groups) == 2
        assert config.environment_groups["kiosks"].strategy == "rolling"
        assert config.environment_groups["kiosks"].members == ["kiosk-lobby", "kiosk-cafe"]
        assert config.environment_groups["kiosks"].max_parallel == 1
        assert config.environment_groups["sensors"].strategy == "parallel"

    def test_parse_groups_defaults(self):
        from taskfile.models import TaskfileConfig
        data = {
            "environment_groups": {
                "fleet": {"members": ["a", "b"]},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        grp = config.environment_groups["fleet"]
        assert grp.strategy == "parallel"
        assert grp.max_parallel == 5
        assert grp.canary_count == 1

    def test_parse_groups_empty(self):
        from taskfile.models import TaskfileConfig
        data = {"tasks": {"t": {"cmds": ["echo"]}}}
        config = TaskfileConfig.from_dict(data)
        assert config.environment_groups == {}

    def test_canary_count(self):
        from taskfile.models import TaskfileConfig
        data = {
            "environment_groups": {
                "displays": {
                    "members": ["d1", "d2", "d3"],
                    "strategy": "canary",
                    "canary_count": 1,
                },
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        grp = config.environment_groups["displays"]
        assert grp.strategy == "canary"
        assert grp.canary_count == 1
        assert len(grp.members) == 3
