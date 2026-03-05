"""Tests for health check framework."""

import pytest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from taskfile.health import (
    check_http_endpoint,
    check_ssh_service,
    HealthCheckResult,
    HealthReport,
    run_health_checks,
)


class TestCheckHttpEndpoint:
    """Tests for HTTP endpoint health checking."""

    def test_healthy_endpoint(self):
        """Test successful health check."""
        with patch("taskfile.health.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            result = check_http_endpoint("Test Service", "https://example.com")

            assert result.status == "healthy"
            assert result.name == "Test Service"
            assert result.url == "https://example.com"
            assert result.status_code == 200
            assert result.response_time_ms >= 0
            assert result.error is None

    def test_unhealthy_wrong_status(self):
        """Test health check with unexpected status code."""
        with patch("taskfile.health.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 500
            mock_urlopen.return_value = mock_response

            result = check_http_endpoint("Test", "https://example.com", expected_status=200)

            assert result.status == "unhealthy"
            assert result.status_code == 500
            assert "Unexpected status" in result.error

    def test_unhealthy_http_error(self):
        """Test health check with HTTP error."""
        with patch("taskfile.health.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                url="https://example.com",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=None,
            )

            result = check_http_endpoint("Test", "https://example.com")

            assert result.status == "unhealthy"
            assert result.status_code == 404
            assert "HTTP error" in result.error

    def test_unhealthy_url_error(self):
        """Test health check with connection error."""
        with patch("taskfile.health.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")

            result = check_http_endpoint("Test", "https://example.com")

            assert result.status == "unhealthy"
            assert result.status_code is None
            assert "Connection error" in result.error

    def test_expected_404_is_healthy(self):
        """Test that 404 can be expected and considered healthy."""
        with patch("taskfile.health.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 404
            mock_urlopen.return_value = mock_response

            result = check_http_endpoint("Test", "https://example.com", expected_status=404)

            assert result.status == "healthy"
            assert result.status_code == 404


class TestCheckSshService:
    """Tests for SSH service health checking."""

    def test_ssh_healthy(self):
        """Test successful SSH check."""
        with patch("taskfile.health.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="healthy\n",
                stderr="",
            )

            result = check_ssh_service("SSH", "192.168.1.1", "deploy", "~/.ssh/key")

            assert result.status == "healthy"
            assert result.name == "SSH"
            assert "ssh://deploy@192.168.1.1:22" in result.url

    def test_ssh_unhealthy(self):
        """Test failed SSH check."""
        with patch("taskfile.health.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Connection refused",
            )

            result = check_ssh_service("SSH", "192.168.1.1", "deploy")

            assert result.status == "unhealthy"
            assert "SSH failed" in result.error

    def test_ssh_timeout(self):
        """Test SSH check timeout."""
        with patch("taskfile.health.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Timeout")

            result = check_ssh_service("SSH", "192.168.1.1", "deploy")

            assert result.status == "unhealthy"


class TestHealthReport:
    """Tests for HealthReport data class."""

    def test_healthy_count(self):
        """Test counting healthy checks."""
        checks = [
            HealthCheckResult("A", "https://a.com", "healthy", 200, 100.0),
            HealthCheckResult("B", "https://b.com", "unhealthy", 500, 200.0, "Error"),
            HealthCheckResult("C", "https://c.com", "healthy", 200, 150.0),
        ]
        report = HealthReport("degraded", checks)

        assert report.healthy_count == 2
        assert report.unhealthy_count == 1

    def test_empty_report(self):
        """Test empty health report."""
        report = HealthReport("unknown", [])

        assert report.healthy_count == 0
        assert report.unhealthy_count == 0


class TestRunHealthChecks:
    """Tests for comprehensive health check runner."""

    def test_run_checks_all_healthy(self):
        """Test running all health checks successfully."""
        with patch("taskfile.health.check_http_endpoint") as mock_http, \
             patch("taskfile.health.check_ssh_service") as mock_ssh, \
             patch("taskfile.health.check_traefik_dashboard") as mock_traefik:

            mock_http.return_value = HealthCheckResult(
                "Landing", "https://example.com", "healthy", 200, 100.0
            )
            mock_ssh.return_value = HealthCheckResult(
                "SSH", "ssh://deploy@host:22", "healthy", response_time_ms=50.0
            )
            mock_traefik.return_value = HealthCheckResult(
                "Traefik", "http://localhost:8080", "healthy", response_time_ms=30.0
            )

            report = run_health_checks(
                domain="example.com",
                ssh_host="192.168.1.1",
                ssh_user="deploy",
            )

            assert report.overall == "healthy"
            assert len(report.checks) == 4  # landing + web + ssh + traefik
            assert report.healthy_count == 4

    def test_run_checks_no_ssh(self):
        """Test running health checks without SSH."""
        with patch("taskfile.health.check_http_endpoint") as mock_http:
            mock_http.return_value = HealthCheckResult(
                "Landing", "https://example.com", "healthy", 200, 100.0
            )

            report = run_health_checks(
                domain="example.com",
                ssh_host=None,  # Disabled
            )

            assert report.overall == "healthy"
            assert len(report.checks) == 2  # Only landing + web

    def test_run_checks_unhealthy_overall(self):
        """Test that unhealthy checks result in correct overall status."""
        with patch("taskfile.health.check_http_endpoint") as mock_http:
            mock_http.return_value = HealthCheckResult(
                "Landing", "https://example.com", "unhealthy", 500, 100.0, "Error"
            )

            report = run_health_checks(
                domain="example.com",
                check_web=False,
                check_api=False,
                check_landing=True,
            )

            assert report.overall == "unhealthy"
            assert report.healthy_count == 0
            assert report.unhealthy_count == 1
