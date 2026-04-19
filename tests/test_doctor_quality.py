"""Tests for doctor --quality and --quality-fix CLI options."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class TestDoctorQualityOption:
    """Test --quality flag in doctor command."""

    def test_quality_flag_runs_pyqual_check(self):
        """--quality flag triggers pyqual quality analysis."""
        from taskfile.cli.interactive.wizards import _doctor_run_quality_check
        from taskfile.diagnostics import ProjectDiagnostics

        diag = MagicMock(spec=ProjectDiagnostics)
        diag.check_pyqual_installed.return_value = True

        # Mock console to capture output
        with patch("taskfile.cli.interactive.wizards.console") as mock_console:
            _doctor_run_quality_check(diag, fix=False, report=False)

            # Should check if pyqual is installed
            diag.check_pyqual_installed.assert_called_once()
            # Should run quality check
            diag.check_pyqual_quality.assert_called_once()
            # Should print header
            mock_console.print.assert_any_call(
                "\n[bold blue]Layer 3+: Code Quality Analysis (pyqual)...[/]"
            )

    def test_quality_flag_no_pyqual_shows_warning(self):
        """--quality without pyqual installed shows warning."""
        from taskfile.cli.interactive.wizards import _doctor_run_quality_check
        from taskfile.diagnostics import ProjectDiagnostics

        diag = MagicMock(spec=ProjectDiagnostics)
        diag.check_pyqual_installed.return_value = False

        with patch("taskfile.cli.interactive.wizards.console") as mock_console:
            _doctor_run_quality_check(diag, fix=False, report=False)

            # Should check if pyqual is installed
            diag.check_pyqual_installed.assert_called_once()
            # Should NOT run quality check
            diag.check_pyqual_quality.assert_not_called()
            # Should show warning
            mock_console.print.assert_any_call(
                "[yellow]⚠ pyqual not installed — install with: pip install pyqual[/]"
            )

    def test_quality_fix_runs_auto_fix(self):
        """--quality-fix flag runs auto-fix after analysis."""
        from taskfile.cli.interactive.wizards import _doctor_run_quality_check
        from taskfile.diagnostics import ProjectDiagnostics

        diag = MagicMock(spec=ProjectDiagnostics)
        diag.check_pyqual_installed.return_value = True
        diag.fix_with_pyqual.return_value = (3, [])  # 3 fixed, 0 failed

        with patch("taskfile.cli.interactive.wizards.console") as mock_console:
            _doctor_run_quality_check(diag, fix=True, report=False)

            # Should run quality check
            diag.check_pyqual_quality.assert_called_once()
            # Should run auto-fix
            diag.fix_with_pyqual.assert_called_once()
            # Should print fix results
            mock_console.print.assert_any_call("[green]✓ Fixed 3 pyqual issue(s)[/]")

    def test_quality_fix_shows_failed_fixes(self):
        """--quality-fix shows warnings for failed fixes."""
        from taskfile.cli.interactive.wizards import _doctor_run_quality_check
        from taskfile.diagnostics import ProjectDiagnostics

        diag = MagicMock(spec=ProjectDiagnostics)
        diag.check_pyqual_installed.return_value = True
        diag.fix_with_pyqual.return_value = (1, ["complex issue"])  # 1 fixed, 1 failed

        with patch("taskfile.cli.interactive.wizards.console") as mock_console:
            _doctor_run_quality_check(diag, fix=True, report=False)

            diag.fix_with_pyqual.assert_called_once()
            mock_console.print.assert_any_call("[green]✓ Fixed 1 pyqual issue(s)[/]")
            mock_console.print.assert_any_call("[yellow]⚠ Could not fix 1 issue(s)[/]")

    def test_quality_report_mode_no_output(self):
        """--quality with --report suppresses console output."""
        from taskfile.cli.interactive.wizards import _doctor_run_quality_check
        from taskfile.diagnostics import ProjectDiagnostics

        diag = MagicMock(spec=ProjectDiagnostics)
        diag.check_pyqual_installed.return_value = True

        with patch("taskfile.cli.interactive.wizards.console") as mock_console:
            _doctor_run_quality_check(diag, fix=False, report=True)

            # Should still run checks
            diag.check_pyqual_installed.assert_called_once()
            diag.check_pyqual_quality.assert_called_once()
            # Should NOT print anything in report mode
            mock_console.print.assert_not_called()


class TestDoctorCommandIntegration:
    """Test doctor command with quality options — integration level."""

    @pytest.fixture
    def mock_project_diagnostics(self):
        """Create a mock ProjectDiagnostics with quality methods."""
        diag = MagicMock()
        diag.issues = []
        diag._issues = []
        diag.check_pyqual_installed.return_value = True
        diag.fix_with_pyqual.return_value = (0, [])
        return diag

    def test_doctor_with_quality_runs_quality_check(self, mock_project_diagnostics):
        """doctor --quality calls quality check via _doctor_run_quality_check."""
        from click.testing import CliRunner
        from taskfile.cli.interactive.wizards import doctor

        with patch("taskfile.cli.interactive.wizards.ProjectDiagnostics") as mock_diag_cls:
            mock_diag_cls.return_value = mock_project_diagnostics

            runner = CliRunner()
            runner.invoke(doctor, ["--quality"])

            # Should run quality check
            mock_project_diagnostics.check_pyqual_installed.assert_called_once()
            mock_project_diagnostics.check_pyqual_quality.assert_called_once()

    def test_doctor_with_quality_fix_runs_fix(self, mock_project_diagnostics):
        """doctor --quality-fix runs both analysis and fix."""
        from click.testing import CliRunner
        from taskfile.cli.interactive.wizards import doctor

        mock_project_diagnostics.fix_with_pyqual.return_value = (2, [])

        with patch("taskfile.cli.interactive.wizards.ProjectDiagnostics") as mock_diag_cls:
            mock_diag_cls.return_value = mock_project_diagnostics

            runner = CliRunner()
            runner.invoke(doctor, ["--quality-fix"])

            # Should run quality check and fix
            mock_project_diagnostics.check_pyqual_quality.assert_called_once()
            mock_project_diagnostics.fix_with_pyqual.assert_called_once()

    def test_doctor_quality_fix_implies_quality(self, mock_project_diagnostics):
        """--quality-fix implies --quality (runs quality check even without --quality)."""
        from click.testing import CliRunner
        from taskfile.cli.interactive.wizards import doctor

        with patch("taskfile.cli.interactive.wizards.ProjectDiagnostics") as mock_diag_cls:
            mock_diag_cls.return_value = mock_project_diagnostics

            runner = CliRunner()
            # Only --quality-fix, no --quality
            runner.invoke(doctor, ["--quality-fix"])

            # Should still run quality check (implied by --quality-fix)
            mock_project_diagnostics.check_pyqual_installed.assert_called_once()
            mock_project_diagnostics.check_pyqual_quality.assert_called_once()

    def test_doctor_combined_options(self, mock_project_diagnostics):
        """doctor with multiple options works correctly."""
        from click.testing import CliRunner
        from taskfile.cli.interactive.wizards import doctor

        with patch("taskfile.cli.interactive.wizards.ProjectDiagnostics") as mock_diag_cls:
            mock_diag_cls.return_value = mock_project_diagnostics

            runner = CliRunner()
            result = runner.invoke(doctor, ["--verbose", "--quality", "--fix"])

            # Should succeed
            assert result.exit_code in (0, 1)  # 0 = no issues, 1 = issues found
            # Quality check should run
            mock_project_diagnostics.check_pyqual_quality.assert_called_once()


class TestDoctorQualityCLIHelp:
    """Test CLI help text for quality options."""

    def test_quality_option_in_help(self):
        """--quality option appears in doctor help."""
        from click.testing import CliRunner
        from taskfile.cli.interactive.wizards import doctor

        runner = CliRunner()
        result = runner.invoke(doctor, ["--help"])

        assert result.exit_code == 0
        assert "--quality" in result.output
        assert "pyqual" in result.output.lower()

    def test_quality_fix_option_in_help(self):
        """--quality-fix option appears in doctor help."""
        from click.testing import CliRunner
        from taskfile.cli.interactive.wizards import doctor

        runner = CliRunner()
        result = runner.invoke(doctor, ["--help"])

        assert result.exit_code == 0
        assert "--quality-fix" in result.output
        assert "auto-fix" in result.output.lower() or "fix" in result.output.lower()
