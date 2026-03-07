"""Tests for Phase 9 — Doctor Decomposition.

Covers:
- run_all_checks() consolidates Layer 1-3 pipeline
- _check_ufw_forward_policy infra check
- _check_container_dns infra check
- ProjectDiagnostics facade integration
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from taskfile.diagnostics import ProjectDiagnostics
from taskfile.diagnostics.checks import (
    _check_ufw_forward_policy,
    _check_container_dns,
)
from taskfile.diagnostics.models import IssueCategory


# ═══════════════════════════════════════════════════════════════════════
# 1. run_all_checks() consolidation
# ═══════════════════════════════════════════════════════════════════════


class TestRunAllChecks:
    """Verify run_all_checks() calls the correct checks based on flags."""

    def test_run_all_checks_calls_core_checks(self):
        diag = ProjectDiagnostics()
        with patch.object(diag, 'check_preflight') as m1, \
             patch.object(diag, 'check_taskfile') as m2, \
             patch.object(diag, 'check_env_files') as m3, \
             patch.object(diag, 'check_git') as m4, \
             patch.object(diag, 'check_deploy_artifacts') as m5, \
             patch.object(diag, 'check_docker') as m6, \
             patch.object(diag, 'check_ports') as m7, \
             patch.object(diag, 'validate_taskfile_variables') as m8, \
             patch.object(diag, 'check_placeholder_values') as m9, \
             patch.object(diag, 'check_dependent_files') as m10, \
             patch.object(diag, 'check_registry_access') as m11, \
             patch.object(diag, 'check_ssh_keys') as m12, \
             patch.object(diag, 'check_task_commands') as m13, \
             patch.object(diag, 'check_ssh_connectivity') as m14, \
             patch.object(diag, 'check_remote_health') as m15, \
             patch.object(diag, 'check_ufw_forward_policy') as m16, \
             patch.object(diag, 'check_container_dns') as m17:
            diag.run_all_checks(verbose=False, remote=False)

            # Core checks always called
            m1.assert_called_once()  # preflight
            m2.assert_called_once()  # taskfile
            m3.assert_called_once()  # env_files
            m4.assert_called_once()  # git
            m5.assert_called_once()  # deploy_artifacts
            m6.assert_called_once()  # docker
            m7.assert_called_once()  # ports

            # Verbose/remote checks NOT called
            m13.assert_not_called()  # task_commands
            m14.assert_not_called()  # ssh_connectivity
            m15.assert_not_called()  # remote_health
            m16.assert_not_called()  # ufw
            m17.assert_not_called()  # dns

    def test_run_all_checks_verbose_adds_expensive_checks(self):
        diag = ProjectDiagnostics()
        with patch.object(diag, 'check_preflight'), \
             patch.object(diag, 'check_taskfile'), \
             patch.object(diag, 'check_env_files'), \
             patch.object(diag, 'check_git'), \
             patch.object(diag, 'check_deploy_artifacts'), \
             patch.object(diag, 'check_docker'), \
             patch.object(diag, 'check_ports'), \
             patch.object(diag, 'validate_taskfile_variables'), \
             patch.object(diag, 'check_placeholder_values'), \
             patch.object(diag, 'check_dependent_files'), \
             patch.object(diag, 'check_registry_access'), \
             patch.object(diag, 'check_ssh_keys'), \
             patch.object(diag, 'check_task_commands') as m_task, \
             patch.object(diag, 'check_ssh_connectivity') as m_ssh, \
             patch.object(diag, 'check_remote_health') as m_health, \
             patch.object(diag, 'check_ufw_forward_policy') as m_ufw, \
             patch.object(diag, 'check_container_dns') as m_dns:
            diag.run_all_checks(verbose=True)

            m_task.assert_called_once()
            m_ssh.assert_called_once()
            m_health.assert_called_once()
            m_ufw.assert_called_once()
            m_dns.assert_called_once()

    def test_run_all_checks_remote_adds_infra_checks(self):
        diag = ProjectDiagnostics()
        with patch.object(diag, 'check_preflight'), \
             patch.object(diag, 'check_taskfile'), \
             patch.object(diag, 'check_env_files'), \
             patch.object(diag, 'check_git'), \
             patch.object(diag, 'check_deploy_artifacts'), \
             patch.object(diag, 'check_docker'), \
             patch.object(diag, 'check_ports'), \
             patch.object(diag, 'validate_taskfile_variables'), \
             patch.object(diag, 'check_placeholder_values'), \
             patch.object(diag, 'check_dependent_files'), \
             patch.object(diag, 'check_registry_access'), \
             patch.object(diag, 'check_ssh_keys'), \
             patch.object(diag, 'check_task_commands') as m_task, \
             patch.object(diag, 'check_ssh_connectivity') as m_ssh, \
             patch.object(diag, 'check_remote_health') as m_health, \
             patch.object(diag, 'check_ufw_forward_policy') as m_ufw, \
             patch.object(diag, 'check_container_dns') as m_dns:
            diag.run_all_checks(remote=True)

            m_task.assert_called_once()
            m_ssh.assert_called_once()
            m_health.assert_called_once()
            m_ufw.assert_called_once()
            m_dns.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# 2. _check_ufw_forward_policy
# ═══════════════════════════════════════════════════════════════════════


class TestCheckUfwForwardPolicy:

    @patch("taskfile.diagnostics.checks.shutil.which", return_value=None)
    def test_no_ufw_returns_empty(self, mock_which):
        assert _check_ufw_forward_policy() == []

    @patch("taskfile.diagnostics.checks.subprocess.run")
    @patch("taskfile.diagnostics.checks.shutil.which", return_value="/usr/sbin/ufw")
    def test_ufw_inactive_returns_empty(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(stdout="Status: inactive\n", returncode=0)
        assert _check_ufw_forward_policy() == []

    @patch("taskfile.diagnostics.checks.Path")
    @patch("taskfile.diagnostics.checks.subprocess.run")
    @patch("taskfile.diagnostics.checks.shutil.which", return_value="/usr/sbin/ufw")
    def test_ufw_forward_drop_reports_issue(self, mock_which, mock_run, mock_path_cls):
        mock_run.return_value = MagicMock(stdout="Status: active\n", returncode=0)

        # Mock /etc/default/ufw
        mock_ufw_file = MagicMock()
        mock_ufw_file.exists.return_value = True
        mock_ufw_file.read_text.return_value = 'DEFAULT_FORWARD_POLICY="DROP"\n'
        mock_path_cls.return_value = mock_ufw_file

        issues = _check_ufw_forward_policy()
        assert len(issues) == 1
        assert "FORWARD" in issues[0].message
        assert issues[0].category == IssueCategory.EXTERNAL_ERROR

    @patch("taskfile.diagnostics.checks.Path")
    @patch("taskfile.diagnostics.checks.subprocess.run")
    @patch("taskfile.diagnostics.checks.shutil.which", return_value="/usr/sbin/ufw")
    def test_ufw_forward_accept_no_issue(self, mock_which, mock_run, mock_path_cls):
        mock_run.return_value = MagicMock(stdout="Status: active\n", returncode=0)

        mock_ufw_file = MagicMock()
        mock_ufw_file.exists.return_value = True
        mock_ufw_file.read_text.return_value = 'DEFAULT_FORWARD_POLICY="ACCEPT"\n'
        mock_path_cls.return_value = mock_ufw_file

        issues = _check_ufw_forward_policy()
        assert issues == []


# ═══════════════════════════════════════════════════════════════════════
# 3. _check_container_dns
# ═══════════════════════════════════════════════════════════════════════


class TestCheckContainerDns:

    @patch("taskfile.diagnostics.checks.shutil.which", return_value=None)
    def test_no_podman_returns_empty(self, mock_which):
        assert _check_container_dns() == []

    @patch("taskfile.diagnostics.checks.socket.socket")
    @patch("taskfile.diagnostics.checks.shutil.which", return_value="/usr/bin/podman")
    def test_bridge_unreachable_returns_empty(self, mock_which, mock_socket_cls):
        """If 10.88.0.1 is unreachable, skip (podman not initialized)."""
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("Connection refused")
        mock_socket_cls.return_value = mock_sock

        issues = _check_container_dns()
        assert issues == []
