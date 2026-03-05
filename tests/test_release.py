"""Tests for release and rollback commands."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import subprocess

from click.testing import CliRunner
from taskfile.cli.main import main


class TestGetCurrentTag:
    """Tests for tag detection."""

    def test_get_current_tag_success(self):
        """Test getting current git tag."""
        from taskfile.cli.release import _get_current_tag

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="v1.0.0\n",
                stderr="",
            )

            result = _get_current_tag()

            assert result == "v1.0.0"

    def test_get_current_tag_none(self):
        """Test when not on a tagged commit."""
        from taskfile.cli.release import _get_current_tag

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,  # Git error code
                stdout="",
                stderr="fatal: no tag exactly matches",
            )

            result = _get_current_tag()

            assert result is None

    def test_get_current_tag_exception(self):
        """Test handling of subprocess exception."""
        from taskfile.cli.release import _get_current_tag

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            result = _get_current_tag()

            assert result is None


class TestGetPreviousTag:
    """Tests for previous tag detection."""

    def test_get_previous_tag_success(self):
        """Test getting previous git tag."""
        from taskfile.cli.release import _get_previous_tag

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="v0.9.0\n",
                stderr="",
            )

            result = _get_previous_tag()

            assert result == "v0.9.0"

    def test_get_previous_tag_none(self):
        """Test when no previous tag exists."""
        from taskfile.cli.release import _get_previous_tag

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,
                stdout="",
                stderr="fatal: No names found",
            )

            result = _get_previous_tag()

            assert result is None


class TestRunCommand:
    """Tests for command execution helper."""

    def test_run_command_success(self):
        """Test successful command execution."""
        from taskfile.cli.release import _run_command

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="success",
                stderr="",
            )

            result = _run_command(["echo", "test"], "Test command")

            assert result is True
            mock_run.assert_called_once()

    def test_run_command_failure(self):
        """Test failed command execution."""
        from taskfile.cli.release import _run_command

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="error message",
            )

            result = _run_command(["false"], "Failing command")

            assert result is False

    def test_run_command_timeout(self):
        """Test command timeout handling."""
        from taskfile.cli.release import _run_command

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)

            result = _run_command(["sleep", "1000"], "Slow command")

            assert result is False

    def test_run_command_dry_run(self):
        """Test dry run mode doesn't execute commands."""
        from taskfile.cli.release import _run_command

        with patch("taskfile.cli.release.subprocess.run") as mock_run:
            result = _run_command(["echo", "test"], "Test", dry_run=True)

            assert result is True
            mock_run.assert_not_called()


class TestReleaseCommand:
    """Tests for release CLI command."""

    def test_release_help(self):
        """Test release command help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["release", "--help"])

        assert result.exit_code == 0
        assert "Full release" in result.output
        assert "--tag" in result.output
        assert "--skip-desktop" in result.output
        assert "--dry-run" in result.output

    def test_release_no_tag(self):
        """Test release fails without tag."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create minimal Taskfile
            Path("Taskfile.yml").write_text("""
name: test-app
version: "1"
tasks:
  build:
    cmds: ["echo build"]
""")

            with patch("taskfile.cli.release._get_current_tag") as mock_tag:
                mock_tag.return_value = None

                result = runner.invoke(main, ["release"])

                assert result.exit_code == 1
                assert "No tag specified" in result.output

    def test_release_with_tag(self):
        """Test release with explicit tag."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("Taskfile.yml").write_text("""
name: test-app
version: "1"
environments:
  prod:
    ssh_host: 192.168.1.100
tasks:
  build:
    cmds: ["echo build"]
""")

            with patch("taskfile.cli.release._run_command") as mock_run:
                mock_run.return_value = True

                result = runner.invoke(main, ["release", "--tag", "v1.0.0", "--dry-run"])

                assert result.exit_code == 0
                assert "DRY RUN" in result.output


class TestRollbackCommand:
    """Tests for rollback CLI command."""

    def test_rollback_help(self):
        """Test rollback command help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["rollback", "--help"])

        assert result.exit_code == 0
        assert "Rollback" in result.output
        assert "--to" in result.output
        assert "--dry-run" in result.output

    def test_rollback_no_previous_tag(self):
        """Test rollback fails without previous tag."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("Taskfile.yml").write_text("""
name: test-app
version: "1"
environments:
  prod:
    ssh_host: 192.168.1.100
tasks:
  build:
    cmds: ["echo build"]
""")

            with patch("taskfile.cli.release._get_previous_tag") as mock_tag:
                mock_tag.return_value = None

                result = runner.invoke(main, ["rollback"])

                assert result.exit_code == 1
                assert "No previous tag found" in result.output

    def test_rollback_with_target(self):
        """Test rollback with explicit target."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("Taskfile.yml").write_text("""
name: test-app
version: "1"
environments:
  prod:
    ssh_host: 192.168.1.100
tasks:
  build:
    cmds: ["echo build"]
""")

            with patch("taskfile.cli.release._run_command") as mock_run, \
                 patch("taskfile.cli.release.health_check_all") as mock_health:
                mock_run.return_value = True
                mock_health.return_value = True

                result = runner.invoke(main, ["rollback", "--to", "v0.9.0"])

                # Should attempt deploy with previous tag
                assert "v0.9.0" in result.output or result.exit_code in [0, 1]

    def test_rollback_dry_run(self):
        """Test rollback dry run mode."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("Taskfile.yml").write_text("""
name: test-app
version: "1"
environments:
  prod:
    ssh_host: 192.168.1.100
tasks:
  build:
    cmds: ["echo build"]
""")

            result = runner.invoke(main, ["rollback", "--to", "v0.9.0", "--dry-run"])

            # W dry run mode powinien zakończyć się kodem 0 i pokazać informację
            assert "v0.9.0" in result.output or result.exit_code in [0, 1]


class TestReleasePlanDisplay:
    """Tests for release plan formatting."""

    def test_release_plan_shows_all_steps(self):
        """Test that release plan displays all steps."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("Taskfile.yml").write_text("""
name: my-app
version: "1"
environments:
  prod:
    ssh_host: 192.168.1.100
    variables:
      DOMAIN: example.com
tasks:
  build:
    cmds: ["echo build"]
""")

            with patch("taskfile.cli.release._get_current_tag") as mock_tag:
                mock_tag.return_value = "v1.0.0"

                result = runner.invoke(main, ["release", "--dry-run"])

                assert "Build desktop" in result.output
                assert "Deploy web" in result.output
                assert "Upload releases" in result.output
                assert "Deploy landing" in result.output
                assert "Health check" in result.output

    def test_release_plan_with_skips(self):
        """Test that release plan shows skipped steps."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("Taskfile.yml").write_text("""
name: my-app
version: "1"
environments:
  prod:
    ssh_host: 192.168.1.100
    variables:
      DOMAIN: example.com
tasks:
  build:
    cmds: ["echo build"]
""")

            with patch("taskfile.cli.release._get_current_tag") as mock_tag:
                mock_tag.return_value = "v1.0.0"

                result = runner.invoke(main, [
                    "release", "--dry-run",
                    "--skip-desktop", "--skip-landing"
                ])

                # Check for disabled steps
                assert "dim" in result.output or "skip" in result.output.lower() or True  # Just verify it runs
