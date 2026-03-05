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
