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


class TestParser:
    def test_load_from_file(self, tmp_path):
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        }))
        config = load_taskfile(taskfile)
        assert "hello" in config.tasks

    def test_not_found(self, tmp_path):
        with pytest.raises(TaskfileNotFoundError):
            load_taskfile(tmp_path / "nonexistent.yml")

    def test_validate_missing_dep(self):
        config = TaskfileConfig.from_dict({
            "tasks": {
                "deploy": {"cmds": ["echo"], "deps": ["nonexistent"]},
            }
        })
        warnings = validate_taskfile(config)
        assert any("nonexistent" in w for w in warnings)

    def test_validate_empty_commands(self):
        config = TaskfileConfig.from_dict({
            "tasks": {
                "empty": {"desc": "nothing here"},
            }
        })
        warnings = validate_taskfile(config)
        assert any("no commands" in w for w in warnings)
