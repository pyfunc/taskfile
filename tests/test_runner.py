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


class TestRunner:
    def _make_runner(self, tasks_data: dict, env_name="local", **kwargs):
        data = {
            "variables": {"APP": "test", "TAG": "latest"},
            "environments": {
                "local": {"container_runtime": "docker"},
                "prod": {
                    "ssh_host": "example.com",
                    "container_runtime": "podman",
                },
            },
            "tasks": tasks_data,
        }
        config = TaskfileConfig.from_dict(data)
        return TaskfileRunner(config=config, env_name=env_name, **kwargs)

    def test_expand_variables(self):
        runner = self._make_runner({"t": {"cmds": ["echo"]}})
        assert runner.expand_variables("${APP}:${TAG}") == "test:latest"
        assert runner.expand_variables("{{APP}}:{{TAG}}") == "test:latest"

    def test_run_simple_task(self):
        runner = self._make_runner({
            "hello": {"cmds": ["echo hello"]},
        })
        assert runner.run_task("hello") is True

    def test_run_unknown_task(self):
        runner = self._make_runner({
            "hello": {"cmds": ["echo hello"]},
        })
        assert runner.run_task("nonexistent") is False

    def test_env_filter_skips_task(self):
        runner = self._make_runner(
            {"deploy": {"cmds": ["echo deploy"], "env": ["prod"]}},
            env_name="local",
        )
        # Should skip (return True) but not execute
        assert runner.run_task("deploy") is True

    def test_dry_run(self):
        runner = self._make_runner(
            {"hello": {"cmds": ["echo hello"]}},
            dry_run=True,
        )
        assert runner.run_task("hello") is True

    def test_dependency_chain(self):
        runner = self._make_runner({
            "build": {"cmds": ["echo build"]},
            "test": {"cmds": ["echo test"], "deps": ["build"]},
            "deploy": {"cmds": ["echo deploy"], "deps": ["test"]},
        })
        assert runner.run_task("deploy") is True
        assert "build" in runner._executed
        assert "test" in runner._executed
        assert "deploy" in runner._executed

    def test_failed_command(self):
        runner = self._make_runner({
            "fail": {"cmds": ["exit 1"]},
        })
        assert runner.run_task("fail") is False

    def test_ignore_errors(self):
        runner = self._make_runner({
            "fail": {"cmds": ["exit 1"], "ignore_errors": True},
        })
        assert runner.run_task("fail") is True

    def test_init_environment_existing(self):
        """Test _init_environment with existing environment."""
        runner = self._make_runner({"t": {"cmds": ["echo"]}}, env_name="prod")
        env = runner._init_environment()
        assert env.name == "prod"
        assert env.ssh_host == "example.com"
        assert env.container_runtime == "podman"

    def test_init_environment_missing(self):
        """Test _init_environment creates default for missing env."""
        data = {
            "variables": {},
            "environments": {"local": {"container_runtime": "docker"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config, env_name="nonexistent")
        env = runner._init_environment()
        assert env.name == "nonexistent"
        assert env.container_runtime == "docker"  # Default value

    def test_init_platform_existing(self):
        """Test _init_platform with existing platform."""
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {"web": {"variables": {"PORT": "3000"}}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config, platform_name="web")
        platform = runner._init_platform()
        assert platform is not None
        assert platform.name == "web"
        assert platform.variables["PORT"] == "3000"

    def test_init_platform_missing(self):
        """Test _init_platform returns None for missing platform."""
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {},
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config, platform_name="nonexistent")
        platform = runner._init_platform()
        assert platform is None

    def test_init_platform_none(self):
        """Test _init_platform with no platform specified."""
        runner = self._make_runner({"t": {"cmds": ["echo"]}}, platform_name=None)
        platform = runner._init_platform()
        assert platform is None

    def test_init_variables_resolution(self):
        """Test variable resolution order: global → env → platform → CLI."""
        data = {
            "variables": {"APP": "global", "TAG": "global", "EXTRA": "global"},
            "environments": {
                "test": {
                    "variables": {"TAG": "env", "ENV_VAR": "env"},
                }
            },
            "platforms": {
                "web": {"variables": {"TAG": "platform", "PLATFORM_VAR": "platform"}},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(
            config=config,
            env_name="test",
            platform_name="web",
            var_overrides={"TAG": "cli", "CLI_VAR": "cli"},
        )
        variables = runner._init_variables()

        # CLI overrides all
        assert variables["TAG"] == "cli"
        # Platform overrides env and global
        assert variables["PLATFORM_VAR"] == "platform"
        # Env overrides global
        assert variables["ENV_VAR"] == "env"
        # Global values preserved if not overridden
        assert variables["APP"] == "global"
        assert variables["EXTRA"] == "global"
        # CLI-only variables included
        assert variables["CLI_VAR"] == "cli"
        # Built-in variables
        assert variables["ENV"] == "test"
        assert variables["PLATFORM"] == "web"

    def test_built_in_variables(self):
        """Test that built-in variables are set correctly."""
        runner = self._make_runner({"t": {"cmds": ["echo"]}}, env_name="local")
        variables = runner._init_variables()

        assert variables["ENV"] == "local"
        assert variables["RUNTIME"] == "docker"
        assert variables["COMPOSE"] == "docker compose"
        # PLATFORM not set when no platform
        assert "PLATFORM" not in variables

    def test_parallel_deps(self):
        """Test parallel dependency execution."""
        runner = self._make_runner({
            "dep1": {"cmds": ["echo dep1"]},
            "dep2": {"cmds": ["echo dep2"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["dep1", "dep2"],
                "parallel": True,
            },
        })
        assert runner.run_task("main") is True
        assert "dep1" in runner._executed
        assert "dep2" in runner._executed
        assert "main" in runner._executed

    def test_parallel_deps_with_failure(self):
        """Test parallel deps: one fails, task fails."""
        runner = self._make_runner({
            "dep-ok": {"cmds": ["echo ok"]},
            "dep-fail": {"cmds": ["exit 1"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["dep-ok", "dep-fail"],
                "parallel": True,
            },
        })
        assert runner.run_task("main") is False

    def test_parallel_deps_ignore_errors(self):
        """Test parallel deps with ignore_errors: failure is tolerated."""
        runner = self._make_runner({
            "dep-ok": {"cmds": ["echo ok"]},
            "dep-fail": {"cmds": ["exit 1"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["dep-ok", "dep-fail"],
                "parallel": True,
                "ignore_errors": True,
            },
        })
        assert runner.run_task("main") is True

    def test_condition_true(self):
        """Test task runs when condition is met."""
        runner = self._make_runner({
            "cond": {"cmds": ["echo ok"], "condition": "true"},
        })
        assert runner.run_task("cond") is True

    def test_condition_false(self):
        """Test task is skipped when condition is not met."""
        runner = self._make_runner({
            "cond": {"cmds": ["echo should-not-run"], "condition": "false"},
        })
        assert runner.run_task("cond") is True  # skipped = success
        assert "cond" in runner._executed  # marked as executed (skipped)
