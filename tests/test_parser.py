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

    def test_validate_missing_script_file(self, tmp_path):
        """Validate warns when a task references a script that doesn't exist."""
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"doctor": {"script": "scripts/nonexistent.sh"}},
        }))
        config = load_taskfile(taskfile)
        warnings = validate_taskfile(config)
        assert any("missing script" in w for w in warnings)

    def test_validate_existing_script_file(self, tmp_path):
        """No warning when script file exists."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "doctor.sh").write_text("#!/bin/bash\necho ok")
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"doctor": {"script": "scripts/doctor.sh"}},
        }))
        config = load_taskfile(taskfile)
        warnings = validate_taskfile(config)
        assert not any("missing script" in w for w in warnings)

    def test_validate_circular_dependency(self):
        """Validate detects circular dependencies between tasks."""
        config = TaskfileConfig.from_dict({
            "tasks": {
                "a": {"cmds": ["echo a"], "deps": ["b"]},
                "b": {"cmds": ["echo b"], "deps": ["a"]},
            }
        })
        warnings = validate_taskfile(config)
        assert any("Circular dependency" in w for w in warnings)

    def test_validate_no_circular_dependency(self):
        """No warning for valid dependency chains."""
        config = TaskfileConfig.from_dict({
            "tasks": {
                "build": {"cmds": ["echo build"]},
                "deploy": {"cmds": ["echo deploy"], "deps": ["build"]},
            }
        })
        warnings = validate_taskfile(config)
        assert not any("Circular dependency" in w for w in warnings)

    def test_validate_missing_env_file_reference(self, tmp_path):
        """Validate warns when environment references a missing env_file."""
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
            "environments": {
                "prod": {"env_file": ".env.prod"},
            },
        }))
        config = load_taskfile(taskfile)
        warnings = validate_taskfile(config)
        assert any("missing env_file" in w for w in warnings)
