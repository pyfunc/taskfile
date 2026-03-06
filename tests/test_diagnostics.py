"""Tests for diagnostics refactoring — IssueCategory, validate_before_run, error classification."""

import pytest
import yaml
from pathlib import Path

from taskfile.cli.diagnostics import (
    IssueCategory,
    DiagnosticIssue,
    ProjectDiagnostics,
    validate_before_run,
    CATEGORY_LABELS,
    CATEGORY_HINTS,
)
from taskfile.runner.commands import _classify_exit_code
from taskfile.models import TaskfileConfig


# ─── IssueCategory Tests ─────────────────────────────


class TestIssueCategory:
    """Test IssueCategory enum values and labels."""

    def test_all_categories_defined(self):
        assert IssueCategory.CONFIG == "config"
        assert IssueCategory.ENV == "env"
        assert IssueCategory.INFRA == "infra"
        assert IssueCategory.RUNTIME == "runtime"

    def test_category_labels_complete(self):
        for cat in IssueCategory:
            assert cat in CATEGORY_LABELS, f"Missing label for {cat}"
            assert isinstance(CATEGORY_LABELS[cat], str)

    def test_category_hints_complete(self):
        for cat in IssueCategory:
            assert cat in CATEGORY_HINTS, f"Missing hint for {cat}"
            assert isinstance(CATEGORY_HINTS[cat], str)


class TestDiagnosticIssue:
    """Test DiagnosticIssue data class."""

    def test_basic_creation(self):
        issue = DiagnosticIssue("test message", "error", True, IssueCategory.CONFIG)
        assert issue.message == "test message"
        assert issue.severity == "error"
        assert issue.auto_fixable is True
        assert issue.category == IssueCategory.CONFIG

    def test_defaults(self):
        issue = DiagnosticIssue("msg")
        assert issue.severity == "warning"
        assert issue.auto_fixable is False
        assert issue.category == IssueCategory.CONFIG

    def test_as_dict(self):
        issue = DiagnosticIssue("fail", "error", False, IssueCategory.INFRA)
        d = issue.as_dict()
        assert d == {
            "message": "fail",
            "severity": "error",
            "auto_fixable": False,
            "category": "infra",
        }


# ─── ProjectDiagnostics Tests ────────────────────────


class TestProjectDiagnostics:
    """Test enhanced ProjectDiagnostics with categorization."""

    def test_add_issue_populates_both_lists(self):
        diag = ProjectDiagnostics()
        diag._add_issue("test", "warning", False, IssueCategory.ENV)
        assert len(diag.issues) == 1
        assert len(diag._issues) == 1
        assert diag.issues[0] == ("test", "warning", False)
        assert diag._issues[0].category == IssueCategory.ENV

    def test_get_report_dict_empty(self):
        diag = ProjectDiagnostics()
        report = diag.get_report_dict()
        assert report["total_issues"] == 0
        assert report["errors"] == 0
        assert report["warnings"] == 0
        assert report["auto_fixable"] == 0
        assert report["categories"] == {}

    def test_get_report_dict_categorized(self):
        diag = ProjectDiagnostics()
        diag._add_issue("missing .env", "warning", True, IssueCategory.ENV)
        diag._add_issue("parse error", "error", False, IssueCategory.CONFIG)
        diag._add_issue("docker missing", "warning", False, IssueCategory.INFRA)

        report = diag.get_report_dict()
        assert report["total_issues"] == 3
        assert report["errors"] == 1
        assert report["warnings"] == 2
        assert report["auto_fixable"] == 1
        assert "env" in report["categories"]
        assert "config" in report["categories"]
        assert "infra" in report["categories"]
        assert len(report["categories"]["env"]) == 1
        assert len(report["categories"]["config"]) == 1

    def test_check_taskfile_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        diag = ProjectDiagnostics()
        result = diag.check_taskfile()
        assert result is False
        assert len(diag._issues) == 1
        assert diag._issues[0].category == IssueCategory.CONFIG
        assert diag._issues[0].severity == "error"

    def test_check_taskfile_valid(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        }))
        diag = ProjectDiagnostics()
        result = diag.check_taskfile()
        assert result is True
        assert len(diag._issues) == 0

    def test_check_taskfile_invalid_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text("not: [valid: yaml: {{")
        diag = ProjectDiagnostics()
        result = diag.check_taskfile()
        assert result is False
        assert len(diag._issues) == 1
        assert diag._issues[0].category == IssueCategory.CONFIG

    def test_check_env_files_categorized(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env = tmp_path / ".env"
        env.write_text("PORT=8000\n")
        diag = ProjectDiagnostics()
        diag.check_env_files()
        if diag._issues:
            assert all(i.category == IssueCategory.ENV for i in diag._issues)

    def test_check_docker_categorized(self):
        diag = ProjectDiagnostics()
        diag.check_docker()
        for issue in diag._issues:
            assert issue.category == IssueCategory.INFRA

    def test_check_git_categorized(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        diag = ProjectDiagnostics()
        diag.check_git()
        for issue in diag._issues:
            assert issue.category == IssueCategory.INFRA

    def test_check_dependent_files_missing_script(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump({
            "version": "1",
            "tasks": {"build": {"script": "scripts/build.sh"}},
        }))
        diag = ProjectDiagnostics()
        diag.check_dependent_files()
        script_issues = [i for i in diag._issues if "script not found" in i.message]
        assert len(script_issues) == 1
        assert script_issues[0].category == IssueCategory.CONFIG

    def test_check_dependent_files_missing_env_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump({
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }))
        diag = ProjectDiagnostics()
        diag.check_dependent_files()
        env_issues = [i for i in diag._issues if "env_file not found" in i.message]
        assert len(env_issues) == 1
        assert env_issues[0].category == IssueCategory.ENV
        assert env_issues[0].auto_fixable is False  # no .example file

    def test_check_dependent_files_env_fixable_when_example_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump({
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }))
        (tmp_path / ".env.prod.example").write_text("DOMAIN=example.com\n")
        diag = ProjectDiagnostics()
        diag.check_dependent_files()
        env_issues = [i for i in diag._issues if "env_file not found" in i.message]
        assert len(env_issues) == 1
        assert env_issues[0].auto_fixable is True  # .example exists

    def test_check_examples_valid(self, tmp_path):
        ex_dir = tmp_path / "examples" / "minimal"
        ex_dir.mkdir(parents=True)
        (ex_dir / "Taskfile.yml").write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        }))
        results = ProjectDiagnostics.check_examples(tmp_path / "examples")
        assert len(results) == 1
        assert results[0]["name"] == "minimal"
        assert results[0]["valid"] is True
        assert results[0]["tasks"] == 1

    def test_check_examples_missing_env(self, tmp_path):
        ex_dir = tmp_path / "examples" / "myapp"
        ex_dir.mkdir(parents=True)
        (ex_dir / "Taskfile.yml").write_text(yaml.dump({
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"deploy": {"cmds": ["echo deploy"]}},
        }))
        results = ProjectDiagnostics.check_examples(tmp_path / "examples")
        assert len(results) == 1
        assert results[0]["missing_env_files"] == [".env.prod"]


# ─── validate_before_run Tests ────────────────────────


class TestValidateBeforeRun:
    """Test pre-run validation function."""

    def _make_config(self, tmp_path, data):
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump(data))
        config = TaskfileConfig.from_dict(data)
        config.source_path = str(tf.resolve())
        return config

    def test_no_issues_clean_project(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        issues = validate_before_run(config, "local", ["hello"])
        assert len(issues) == 0

    def test_unknown_task(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        issues = validate_before_run(config, "local", ["nonexistent"])
        assert len(issues) == 1
        assert issues[0].category == IssueCategory.CONFIG
        assert issues[0].severity == "error"
        assert "Unknown task" in issues[0].message

    def test_missing_env_file(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"deploy": {"cmds": ["echo deploy"]}},
        })
        issues = validate_before_run(config, "prod", ["deploy"])
        env_issues = [i for i in issues if i.category == IssueCategory.ENV]
        assert len(env_issues) == 1
        assert "Missing env file" in env_issues[0].message

    def test_missing_env_file_with_example_hint(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"deploy": {"cmds": ["echo deploy"]}},
        })
        (tmp_path / ".env.prod.example").write_text("DOMAIN=example.com\n")
        issues = validate_before_run(config, "prod", ["deploy"])
        env_issues = [i for i in issues if i.category == IssueCategory.ENV]
        assert len(env_issues) == 1
        assert ".env.prod.example" in env_issues[0].message
        assert env_issues[0].auto_fixable is True

    def test_missing_script(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "tasks": {"build": {"script": "scripts/build.sh"}},
        })
        issues = validate_before_run(config, "local", ["build"])
        script_issues = [i for i in issues if "script not found" in i.message]
        assert len(script_issues) == 1
        assert script_issues[0].category == IssueCategory.CONFIG

    def test_broken_dependency(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "tasks": {"deploy": {"cmds": ["echo deploy"], "deps": ["build"]}},
        })
        issues = validate_before_run(config, "local", ["deploy"])
        dep_issues = [i for i in issues if "depends on unknown" in i.message]
        assert len(dep_issues) == 1
        assert dep_issues[0].category == IssueCategory.CONFIG

    def test_missing_ssh_key(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {
                "prod": {
                    "ssh_host": "example.com",
                    "ssh_key": "/nonexistent/key",
                }
            },
            "tasks": {"deploy": {"cmds": ["echo deploy"]}},
        })
        issues = validate_before_run(config, "prod", ["deploy"])
        ssh_issues = [i for i in issues if i.category == IssueCategory.INFRA]
        assert len(ssh_issues) == 1
        assert "SSH key not found" in ssh_issues[0].message

    def test_no_tasks_specified(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        issues = validate_before_run(config, "local", [])
        assert len(issues) == 0


# ─── Exit Code Classification Tests ──────────────────


class TestClassifyExitCode:
    """Test _classify_exit_code for error categorization."""

    def test_exit_0_not_called(self):
        # _classify_exit_code shouldn't normally be called with 0,
        # but let's verify it doesn't crash
        cat, hint = _classify_exit_code(0)
        assert isinstance(cat, str)
        assert isinstance(hint, str)

    def test_exit_1_runtime(self):
        cat, hint = _classify_exit_code(1)
        assert cat == "runtime"

    def test_exit_2_config(self):
        cat, hint = _classify_exit_code(2)
        assert cat == "config"
        assert "arguments" in hint.lower()

    def test_exit_126_permission(self):
        cat, hint = _classify_exit_code(126)
        assert cat == "config"
        assert "permission" in hint.lower()

    def test_exit_127_not_found(self):
        cat, hint = _classify_exit_code(127)
        assert cat == "config"
        assert "not found" in hint.lower()

    def test_exit_124_timeout(self):
        cat, hint = _classify_exit_code(124)
        assert cat == "infra"
        assert "timeout" in hint.lower()

    def test_exit_130_interrupt(self):
        cat, hint = _classify_exit_code(130)
        assert cat == "runtime"
        assert "interrupt" in hint.lower()

    def test_exit_137_sigkill(self):
        cat, hint = _classify_exit_code(137)
        assert cat == "infra"
        assert "killed" in hint.lower()

    def test_exit_143_sigterm(self):
        cat, hint = _classify_exit_code(143)
        assert cat == "infra"
        assert "terminated" in hint.lower()

    def test_exit_unknown_runtime(self):
        cat, hint = _classify_exit_code(42)
        assert cat == "runtime"
        assert "42" in hint
