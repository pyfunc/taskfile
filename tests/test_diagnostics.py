"""Tests for diagnostics — new 5-layer package + backward-compat shim."""

import pytest
import yaml
from pathlib import Path

# ─── New package imports ──────────────────────────────
from taskfile.diagnostics.models import (
    IssueCategory as NewCategory,
    FixStrategy,
    Issue,
    DoctorReport,
    CATEGORY_LABELS as NEW_LABELS,
    CATEGORY_HINTS as NEW_HINTS,
)
from taskfile.diagnostics.checks import (
    validate_before_run as new_validate_before_run,
    check_taskfile as new_check_taskfile,
    check_env_files as new_check_env_files,
    check_git as new_check_git,
    check_docker as new_check_docker,
    check_dependent_files as new_check_dependent_files,
    check_examples as new_check_examples,
    check_preflight as new_check_preflight,
)
from taskfile.diagnostics.llm_repair import classify_runtime_error
from taskfile.diagnostics import ProjectDiagnostics as NewProjectDiagnostics

# ─── Old backward-compat imports ──────────────────────
from taskfile.cli.diagnostics import (
    IssueCategory as OldCategory,
    DiagnosticIssue,
    ProjectDiagnostics,
    validate_before_run,
    CATEGORY_LABELS,
    CATEGORY_HINTS,
)
from taskfile.runner.commands import _classify_exit_code
from taskfile.models import TaskfileConfig


# ═══════════════════════════════════════════════════════
# New package tests — 5-category system
# ═══════════════════════════════════════════════════════


class TestNewIssueCategory:
    """Test new 5-category IssueCategory."""

    def test_all_five_categories(self):
        assert NewCategory.TASKFILE_BUG == "taskfile_bug"
        assert NewCategory.CONFIG_ERROR == "config_error"
        assert NewCategory.DEPENDENCY_MISSING == "dep_missing"
        assert NewCategory.RUNTIME_ERROR == "runtime_error"
        assert NewCategory.EXTERNAL_ERROR == "external_error"

    def test_labels_complete(self):
        for cat in NewCategory:
            assert cat in NEW_LABELS, f"Missing label for {cat}"

    def test_hints_complete(self):
        for cat in NewCategory:
            assert cat in NEW_HINTS, f"Missing hint for {cat}"


class TestIssueModel:
    """Test new Issue dataclass."""

    def test_basic_creation(self):
        iss = Issue(
            category=NewCategory.CONFIG_ERROR,
            message="test",
            fix_strategy=FixStrategy.AUTO,
            severity="error",
        )
        assert iss.message == "test"
        assert iss.auto_fixable is True
        assert iss.category == NewCategory.CONFIG_ERROR

    def test_defaults(self):
        iss = Issue(category=NewCategory.RUNTIME_ERROR, message="fail")
        assert iss.severity == "warning"
        assert iss.fix_strategy == FixStrategy.MANUAL
        assert iss.auto_fixable is False
        assert iss.layer == 3

    def test_as_dict(self):
        iss = Issue(
            category=NewCategory.DEPENDENCY_MISSING,
            message="docker not found",
            fix_strategy=FixStrategy.LLM,
            severity="error",
            layer=1,
        )
        d = iss.as_dict()
        assert d["category"] == "dep_missing"
        assert d["severity"] == "error"
        assert d["fix_strategy"] == "llm"
        assert d["layer"] == 1

    def test_fix_strategies(self):
        assert FixStrategy.AUTO == "auto"
        assert FixStrategy.CONFIRM == "confirm"
        assert FixStrategy.MANUAL == "manual"
        assert FixStrategy.LLM == "llm"


class TestDoctorReport:
    """Test DoctorReport aggregation."""

    def test_empty_report(self):
        report = DoctorReport()
        assert report.total == 0
        assert report.error_count == 0

    def test_classify(self):
        report = DoctorReport(issues=[
            Issue(category=NewCategory.CONFIG_ERROR, message="a", severity="error"),
            Issue(category=NewCategory.EXTERNAL_ERROR, message="b"),
            Issue(category=NewCategory.RUNTIME_ERROR, message="c",
                  context={"_fixed": True}),
        ])
        report.classify()
        assert len(report.fixed) == 1
        assert len(report.external) == 1
        assert len(report.pending) == 1


class TestNewChecks:
    """Test pure check_* functions from the new package."""

    def test_check_taskfile_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        issues = new_check_taskfile()
        assert len(issues) == 1
        assert issues[0].category == NewCategory.CONFIG_ERROR
        assert issues[0].severity == "error"

    def test_check_taskfile_valid(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Taskfile.yml").write_text(yaml.dump({
            "version": "1", "tasks": {"hello": {"cmds": ["echo hi"]}},
        }))
        issues = new_check_taskfile()
        assert len(issues) == 0

    def test_check_env_files_port_rename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("PORT=8000\n")
        issues = new_check_env_files()
        port_issues = [i for i in issues if "PORT_WEB" in i.message]
        assert len(port_issues) == 1
        assert port_issues[0].category == NewCategory.CONFIG_ERROR

    def test_check_git_not_repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        issues = new_check_git()
        if issues:
            assert issues[0].category == NewCategory.CONFIG_ERROR
            assert issues[0].fix_strategy == FixStrategy.CONFIRM

    def test_check_dependent_files_missing_script(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump({
            "version": "1", "tasks": {"build": {"script": "scripts/build.sh"}},
        }))
        config = TaskfileConfig.from_dict(yaml.safe_load(tf.read_text()))
        config.source_path = str(tf)
        issues = new_check_dependent_files(config)
        script_issues = [i for i in issues if "script not found" in i.message]
        assert len(script_issues) == 1
        assert script_issues[0].category == NewCategory.CONFIG_ERROR

    def test_check_dependent_files_env_fixable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump({
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }))
        (tmp_path / ".env.prod.example").write_text("DOMAIN=example.com\n")
        config = TaskfileConfig.from_dict(yaml.safe_load(tf.read_text()))
        config.source_path = str(tf)
        issues = new_check_dependent_files(config)
        env_issues = [i for i in issues if "env_file not found" in i.message]
        assert len(env_issues) == 1
        assert env_issues[0].fix_strategy == FixStrategy.AUTO

    def test_check_examples_valid(self, tmp_path):
        ex = tmp_path / "examples" / "minimal"
        ex.mkdir(parents=True)
        (ex / "Taskfile.yml").write_text(yaml.dump({
            "version": "1", "tasks": {"hello": {"cmds": ["echo hi"]}},
        }))
        results = new_check_examples(tmp_path / "examples")
        assert len(results) == 1
        assert results[0]["valid"] is True

    def test_check_examples_missing_env(self, tmp_path):
        ex = tmp_path / "examples" / "myapp"
        ex.mkdir(parents=True)
        (ex / "Taskfile.yml").write_text(yaml.dump({
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }))
        results = new_check_examples(tmp_path / "examples")
        assert results[0]["missing_env_files"] == [".env.prod"]

    def test_check_preflight_returns_issues(self):
        issues = new_check_preflight()
        # Should return list (may be empty if all tools installed)
        assert isinstance(issues, list)


class TestNewValidateBeforeRun:
    """Test new validate_before_run returning Issue objects."""

    def _make_config(self, tmp_path, data):
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump(data))
        config = TaskfileConfig.from_dict(data)
        config.source_path = str(tf.resolve())
        return config

    def test_clean_project(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1", "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        issues = new_validate_before_run(config, "local", ["hello"])
        assert len(issues) == 0

    def test_unknown_task(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1", "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        issues = new_validate_before_run(config, "local", ["nonexistent"])
        assert len(issues) == 1
        assert issues[0].category == NewCategory.CONFIG_ERROR
        assert "Unknown task" in issues[0].message

    def test_missing_env_file(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"deploy": {"cmds": ["echo"]}},
        })
        issues = new_validate_before_run(config, "prod", ["deploy"])
        env_issues = [i for i in issues if i.category == NewCategory.CONFIG_ERROR and "env file" in i.message.lower()]
        assert len(env_issues) == 1

    def test_missing_env_file_with_example(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"deploy": {"cmds": ["echo"]}},
        })
        (tmp_path / ".env.prod.example").write_text("DOMAIN=example.com\n")
        issues = new_validate_before_run(config, "prod", ["deploy"])
        env_issues = [i for i in issues if "env file" in i.message.lower()]
        assert len(env_issues) == 1
        assert env_issues[0].auto_fixable is True
        assert ".env.prod.example" in env_issues[0].message

    def test_missing_script(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1", "tasks": {"build": {"script": "scripts/build.sh"}},
        })
        issues = new_validate_before_run(config, "local", ["build"])
        assert any("script not found" in i.message for i in issues)

    def test_broken_dep(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "tasks": {"deploy": {"cmds": ["echo"], "deps": ["build"]}},
        })
        issues = new_validate_before_run(config, "local", ["deploy"])
        assert any("depends on unknown" in i.message for i in issues)

    def test_missing_ssh_key(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {"prod": {"ssh_host": "ex.com", "ssh_key": "/nonexistent/k"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        })
        issues = new_validate_before_run(config, "prod", ["t"])
        assert any("SSH key not found" in i.message for i in issues)


class TestClassifyRuntimeError:
    """Test LLM-layer classify_runtime_error."""

    def test_command_not_found(self):
        iss = classify_runtime_error(127, "bash: foo: command not found", "foo --bar")
        assert iss.category == NewCategory.DEPENDENCY_MISSING

    def test_permission_denied(self):
        iss = classify_runtime_error(126, "permission denied", "scripts/deploy.sh")
        assert iss.category == NewCategory.CONFIG_ERROR

    def test_connection_refused(self):
        iss = classify_runtime_error(1, "connection refused", "ssh prod")
        assert iss.category == NewCategory.EXTERNAL_ERROR

    def test_oom_kill(self):
        iss = classify_runtime_error(137, "", "heavy-process")
        assert iss.category == NewCategory.EXTERNAL_ERROR
        assert "kill" in iss.message.lower()

    def test_timeout(self):
        iss = classify_runtime_error(124, "", "slow-cmd")
        assert iss.category == NewCategory.EXTERNAL_ERROR
        assert "timed out" in iss.message.lower()

    def test_generic_failure(self):
        iss = classify_runtime_error(1, "error: something went wrong", "myapp")
        assert iss.category == NewCategory.RUNTIME_ERROR
        assert iss.fix_strategy == FixStrategy.LLM


# ═══════════════════════════════════════════════════════
# Backward compatibility tests — old 4-category system
# ═══════════════════════════════════════════════════════


class TestOldIssueCategory:
    """Test old 4-category IssueCategory still works."""

    def test_old_categories_defined(self):
        assert OldCategory.CONFIG == "config"
        assert OldCategory.ENV == "env"
        assert OldCategory.INFRA == "infra"
        assert OldCategory.RUNTIME == "runtime"

    def test_old_labels_complete(self):
        for cat in OldCategory:
            assert cat in CATEGORY_LABELS

    def test_old_hints_complete(self):
        for cat in OldCategory:
            assert cat in CATEGORY_HINTS


class TestOldDiagnosticIssue:
    """Test old DiagnosticIssue backward compat."""

    def test_creation(self):
        iss = DiagnosticIssue("test", "error", True, OldCategory.CONFIG)
        assert iss.message == "test"
        assert iss.severity == "error"
        assert iss.auto_fixable is True
        assert iss.category == OldCategory.CONFIG

    def test_defaults(self):
        iss = DiagnosticIssue("msg")
        assert iss.severity == "warning"
        assert iss.auto_fixable is False

    def test_as_dict(self):
        iss = DiagnosticIssue("fail", "error", False, OldCategory.INFRA)
        d = iss.as_dict()
        assert d["category"] == "infra"
        assert d["auto_fixable"] is False


class TestProjectDiagnosticsBackwardCompat:
    """Test ProjectDiagnostics facade with old-style _add_issue calls."""

    def test_add_issue_old_style(self):
        diag = ProjectDiagnostics()
        diag._add_issue("test", "warning", False, OldCategory.ENV)
        assert len(diag.issues) == 1
        assert len(diag._issues) == 1
        assert diag.issues[0] == ("test", "warning", False)

    def test_add_issue_new_style(self):
        diag = ProjectDiagnostics()
        iss = Issue(category=NewCategory.CONFIG_ERROR, message="new-style")
        diag._add_issue(iss)
        assert len(diag._issues) == 1
        assert diag._issues[0].message == "new-style"

    def test_get_report_dict_empty(self):
        diag = ProjectDiagnostics()
        report = diag.get_report_dict()
        assert report["total_issues"] == 0
        assert report["categories"] == {}

    def test_get_report_dict_mixed(self):
        diag = ProjectDiagnostics()
        diag._add_issue("env missing", "warning", True, OldCategory.ENV)
        diag._add_issue("parse error", "error", False, OldCategory.CONFIG)
        report = diag.get_report_dict()
        assert report["total_issues"] == 2
        assert report["errors"] == 1
        assert report["warnings"] == 1

    def test_check_taskfile_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        diag = ProjectDiagnostics()
        result = diag.check_taskfile()
        assert result is False
        assert len(diag._issues) >= 1

    def test_check_taskfile_valid(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Taskfile.yml").write_text(yaml.dump({
            "version": "1", "tasks": {"hello": {"cmds": ["echo hi"]}},
        }))
        diag = ProjectDiagnostics()
        assert diag.check_taskfile() is True

    def test_check_examples(self, tmp_path):
        ex = tmp_path / "examples" / "minimal"
        ex.mkdir(parents=True)
        (ex / "Taskfile.yml").write_text(yaml.dump({
            "version": "1", "tasks": {"t": {"cmds": ["echo"]}},
        }))
        results = ProjectDiagnostics.check_examples(tmp_path / "examples")
        assert len(results) == 1
        assert results[0]["valid"] is True


class TestOldValidateBeforeRun:
    """Test old validate_before_run returns DiagnosticIssue with old categories."""

    def _make_config(self, tmp_path, data):
        tf = tmp_path / "Taskfile.yml"
        tf.write_text(yaml.dump(data))
        config = TaskfileConfig.from_dict(data)
        config.source_path = str(tf.resolve())
        return config

    def test_clean(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1", "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        issues = validate_before_run(config, "local", ["hello"])
        assert len(issues) == 0

    def test_unknown_task_returns_old_category(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1", "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        issues = validate_before_run(config, "local", ["nonexistent"])
        assert len(issues) == 1
        assert issues[0].category == OldCategory.CONFIG
        assert "Unknown task" in issues[0].message

    def test_missing_env_file(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {"prod": {"env_file": ".env.prod"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        })
        issues = validate_before_run(config, "prod", ["t"])
        env_issues = [i for i in issues if "env file" in i.message.lower()]
        assert len(env_issues) == 1

    def test_missing_ssh_key(self, tmp_path):
        config = self._make_config(tmp_path, {
            "version": "1",
            "environments": {"prod": {"ssh_host": "ex.com", "ssh_key": "/bad/k"}},
            "tasks": {"t": {"cmds": ["echo"]}},
        })
        issues = validate_before_run(config, "prod", ["t"])
        ssh = [i for i in issues if "SSH" in i.message]
        assert len(ssh) == 1
        # New system classifies missing SSH key as config_error → maps to CONFIG
        assert ssh[0].category == OldCategory.CONFIG


# ─── Exit Code Classification Tests ──────────────────


class TestClassifyExitCode:
    """Test _classify_exit_code for error categorization."""

    def test_exit_0_not_called(self):
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
