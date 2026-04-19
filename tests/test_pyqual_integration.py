"""Tests for pyqual integration with taskfile diagnostics."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from taskfile.diagnostics.checks_pyqual import (
    check_pyqual_installed,
    check_pyqual_quality,
    fix_with_pyqual,
    get_pyqual_summary,
    _map_pyqual_severity,
    _categorize_pyqual_issue,
    _run_pyqual_gates,
)
from taskfile.diagnostics.models import (
    IssueCategory,
    FixStrategy,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)


class TestPyqualInstalled:
    """Test check_pyqual_installed function."""

    def test_pyqual_installed_returns_empty(self):
        """When pyqual is installed, return empty list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = check_pyqual_installed()
            assert result == []
            mock_run.assert_called_once()

    def test_pyqual_not_installed_returns_issue(self):
        """When pyqual is missing, return installable Issue."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = check_pyqual_installed()

            assert len(result) == 1
            issue = result[0]
            assert issue.category == IssueCategory.DEPENDENCY_MISSING
            assert "pyqual is not installed" in issue.message
            assert issue.fix_strategy == FixStrategy.AUTO
            assert issue.fix_command == "pip install pyqual"
            assert issue.layer == 1

    def test_pyqual_timeout_returns_issue(self):
        """When pyqual check times out, handle gracefully."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["pyqual"], timeout=5)
            result = check_pyqual_installed()

            assert len(result) == 1
            assert result[0].category == IssueCategory.DEPENDENCY_MISSING


class TestMapPyqualSeverity:
    """Test severity mapping from pyqual to taskfile."""

    @pytest.mark.parametrize(
        "pyqual_sev,expected",
        [
            ("critical", SEVERITY_ERROR),
            ("high", SEVERITY_ERROR),
            ("medium", SEVERITY_WARNING),
            ("low", SEVERITY_INFO),
            ("unknown", SEVERITY_WARNING),
            ("CRITICAL", SEVERITY_ERROR),  # case insensitive
        ],
    )
    def test_severity_mapping(self, pyqual_sev, expected):
        """Pyqual severity maps correctly to taskfile severity."""
        assert _map_pyqual_severity(pyqual_sev) == expected


class TestCategorizePyqualIssue:
    """Test categorization of pyqual findings."""

    def test_config_issues_categorized_correctly(self):
        """Config-related issues get CONFIG_ERROR category."""
        finding = {"category": "config", "rule": "invalid-yaml"}
        assert _categorize_pyqual_issue(finding) == IssueCategory.CONFIG_ERROR

    def test_yaml_rule_categorized_as_config(self):
        """YAML rule issues get CONFIG_ERROR."""
        finding = {"category": "style", "rule": "yaml-indent"}
        assert _categorize_pyqual_issue(finding) == IssueCategory.CONFIG_ERROR

    def test_dependency_issues_categorized_correctly(self):
        """Dependency issues get DEPENDENCY_MISSING category."""
        finding = {"category": "dependency", "rule": "missing-import"}
        assert _categorize_pyqual_issue(finding) == IssueCategory.DEPENDENCY_MISSING

    def test_runtime_issues_categorized_correctly(self):
        """Runtime/crash issues get RUNTIME_ERROR category."""
        finding = {"category": "runtime", "rule": "crash-risk"}
        assert _categorize_pyqual_issue(finding) == IssueCategory.RUNTIME_ERROR

    def test_default_category_is_config(self):
        """Unknown issues default to CONFIG_ERROR."""
        finding = {"category": "unknown", "rule": "unknown"}
        assert _categorize_pyqual_issue(finding) == IssueCategory.CONFIG_ERROR


class TestRunPyqualGates:
    """Test _run_pyqual_gates function."""

    def test_successful_run_returns_parsed_gates(self):
        """Successful pyqual gates returns parsed data."""
        mock_output = """
┏━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Status ┃ Metric     ┃ Value ┃ Threshold ┃
┡━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ ✅   │ cc         │   4.4 │    ≤ 15.0 │
│ ❌   │ vallm_pass │  41.1 │    ≥ 90.0 │
└──────┴────────────┴───────┴───────────┘
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_output)
            result = _run_pyqual_gates()

            assert result is not None
            assert "cc" in result["passed"]
            assert len(result["failed"]) == 1
            assert result["failed"][0]["metric"] == "vallm_pass"

    def test_failure_returns_none(self):
        """Failed pyqual gates returns None."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = _run_pyqual_gates()
            assert result is None

    def test_timeout_returns_none(self):
        """Timeout returns None gracefully."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["pyqual"], timeout=30)
            result = _run_pyqual_gates()
            assert result is None

    def test_uses_project_path_when_provided(self):
        """Project path is passed to pyqual command."""
        project_path = Path("/some/project")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="")
            _run_pyqual_gates(project_path)

            call_args = mock_run.call_args[0][0]
            assert "--path" in call_args
            assert str(project_path) in call_args


class TestCheckPyqualQuality:
    """Test check_pyqual_quality function."""

    def test_missing_pyqual_returns_install_issue(self):
        """When pyqual not installed, suggest installation."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = check_pyqual_quality()

            assert len(result) == 1
            assert "pyqual is not installed" in result[0].message

    def test_pyqual_failure_returns_error_issue(self):
        """When pyqual fails, return informative issue."""
        with patch("subprocess.run") as mock_run:
            # First call (check installed) succeeds
            # Second call (run gates) fails
            mock_run.side_effect = [
                Mock(returncode=0, stdout="pyqual OK"),  # check installed
                subprocess.TimeoutExpired(cmd=["pyqual"], timeout=30),  # gates check
            ]
            result = check_pyqual_quality()

            assert len(result) == 1
            assert result[0].category == IssueCategory.RUNTIME_ERROR
            assert "pyqual gates check failed" in result[0].message

    def test_converts_failed_gates_to_issues(self):
        """Failed quality gates are converted to Issue objects."""
        mock_output = """
┏━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Status ┃ Metric     ┃ Value ┃ Threshold ┃
┡━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ ✅   │ cc         │   4.4 │    ≤ 15.0 │
│ ❌   │ vallm_pass │  41.1 │    ≥ 90.0 │
└──────┴────────────┴───────┴───────────┘
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_output)
            result = check_pyqual_quality()

            # Should have issues for failed gates (passed gates don't create info when there are failures)
            assert len(result) == 1
            assert "Quality gate failed" in result[0].message
            assert "vallm_pass" in result[0].message
            assert result[0].fix_strategy == FixStrategy.LLM

    def test_all_passed_gates_returns_info(self):
        """All passed gates return info issue."""
        mock_output = """
┏━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Status ┃ Metric     ┃ Value ┃ Threshold ┃
┡━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ ✅   │ cc         │   4.4 │    ≤ 15.0 │
│ ✅   │ coverage   │  85.0 │    ≥ 80.0 │
└──────┴────────────┴───────┴───────────┘
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_output)
            result = check_pyqual_quality()

            assert len(result) == 1  # Just the summary info
            assert result[0].severity == SEVERITY_INFO
            assert "quality gates passed" in result[0].message


class TestFixWithPyqual:
    """Test fix_with_pyqual function."""

    def test_successful_fix_returns_count(self):
        """Successful fix returns count of fixed issues."""
        mock_output = json.dumps({"fixed_count": 5})

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_output, stderr="")
            fixed, failed = fix_with_pyqual()

            assert fixed == 5
            assert failed == []

    def test_failure_returns_error_message(self):
        """Failed fix returns error in failed list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="parse error", stdout="")
            fixed, failed = fix_with_pyqual()

            assert fixed == 0
            assert len(failed) == 1
            assert "parse error" in failed[0]

    def test_not_installed_returns_error(self):
        """When pyqual not installed, return appropriate error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            fixed, failed = fix_with_pyqual()

            assert fixed == 0
            assert len(failed) == 1
            assert "not installed" in failed[0].lower()

    def test_timeout_returns_error(self):
        """Timeout returns appropriate error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["pyqual"], timeout=120)
            fixed, failed = fix_with_pyqual()

            assert fixed == 0
            assert len(failed) == 1
            assert "timed out" in failed[0].lower()


class TestGetPyqualSummary:
    """Test get_pyqual_summary function."""

    def test_summary_returns_correct_counts(self):
        """Summary returns correct counts by gate status."""
        mock_output = """
┏━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Status ┃ Metric     ┃ Value ┃ Threshold ┃
┡━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ ✅   │ cc         │   4.4 │    ≤ 15.0 │
│ ❌   │ vallm_pass │  41.1 │    ≥ 90.0 │
│ ❌   │ coverage   │   N/A │    ≥ 80.0 │
└──────┴────────────┴───────┴───────────┘
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_output)
            summary = get_pyqual_summary()

            assert summary["total"] == 3
            assert summary["passed"] == 1
            assert summary["failed"] == 2

    def test_summary_all_passed(self):
        """Summary with all gates passed."""
        mock_output = """
┏━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Status ┃ Metric     ┃ Value ┃ Threshold ┃
┡━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ ✅   │ cc         │   4.4 │    ≤ 15.0 │
│ ✅   │ coverage   │  85.0 │    ≥ 80.0 │
└──────┴────────────┴───────┴───────────┘
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_output)
            summary = get_pyqual_summary()

            assert summary["total"] == 2
            assert summary["passed"] == 2
            assert summary["failed"] == 0
            assert summary["all_passed"] is True


class TestPyqualIntegrationWithDiagnostics:
    """Test integration with ProjectDiagnostics facade."""

    def test_project_diagnostics_has_pyqual_methods(self):
        """ProjectDiagnostics has pyqual-related methods."""
        from taskfile.diagnostics import ProjectDiagnostics

        diag = ProjectDiagnostics()
        assert hasattr(diag, "check_pyqual_installed")
        assert hasattr(diag, "check_pyqual_quality")
        assert hasattr(diag, "fix_with_pyqual")
        assert hasattr(diag, "get_pyqual_summary")

    def test_check_pyqual_installed_adds_issue_when_missing(self):
        """check_pyqual_installed adds issue to diagnostics."""
        from taskfile.diagnostics import ProjectDiagnostics

        diag = ProjectDiagnostics()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = diag.check_pyqual_installed()

            assert result is False
            assert len(diag._issues) == 1
            assert "pyqual is not installed" in diag._issues[0].message

    def test_check_pyqual_quality_populates_issues(self):
        """check_pyqual_quality populates _issues list."""
        from taskfile.diagnostics import ProjectDiagnostics

        # First call: check_installed (status), Second call: gates
        mock_side_effects = [
            Mock(returncode=0, stdout="pyqual OK"),  # check_installed
            Mock(returncode=0, stdout="│ ❌ │ vallm_pass │ 41.1 │ ≥ 90.0 │"),  # gates
        ]

        diag = ProjectDiagnostics()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = mock_side_effects
            diag.check_pyqual_quality()

            assert len(diag._issues) == 1
            assert "vallm_pass" in diag._issues[0].message

    def test_fix_with_pyqual_delegates_to_function(self):
        """fix_with_pyqual delegates to module function."""
        from taskfile.diagnostics import ProjectDiagnostics

        diag = ProjectDiagnostics()

        with patch("taskfile.diagnostics._fix_with_pyqual_fn") as mock_fix:
            mock_fix.return_value = (3, [])
            result = diag.fix_with_pyqual()

            assert result == (3, [])
            mock_fix.assert_called_once()
