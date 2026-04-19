"""Tests for venv / dependency checks (checks_venv.py)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch


from taskfile.diagnostics.checks_venv import (
    check_venv,
    check_dependencies,
    check_poetry_lock,
    _find_venv,
    _installed_packages,
    _pkg_name,
)
from taskfile.diagnostics.models import (
    FixStrategy,
    IssueCategory,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)


# ─── _pkg_name ────────────────────────────────────────────────────


class TestPkgName:
    def test_bare_name(self):
        assert _pkg_name("requests") == "requests"

    def test_version_specifier(self):
        assert _pkg_name("requests>=2.0") == "requests"

    def test_extras(self):
        assert _pkg_name("uvicorn[standard]>=0.27") == "uvicorn"

    def test_dash_to_underscore(self):
        assert _pkg_name("some-pkg>=1.0") == "some_pkg"

    def test_env_marker(self):
        assert _pkg_name("pywin32; sys_platform == 'win32'") == "pywin32"


# ─── _find_venv ───────────────────────────────────────────────────


class TestFindVenv:
    def test_finds_dot_venv(self, tmp_path):
        venv_dir = tmp_path / ".venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python").write_text("#!/bin/sh")
        result = _find_venv(tmp_path)
        assert result == tmp_path / ".venv"

    def test_finds_plain_venv(self, tmp_path):
        venv_dir = tmp_path / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python").write_text("#!/bin/sh")
        result = _find_venv(tmp_path)
        assert result == tmp_path / "venv"

    def test_returns_none_when_no_venv(self, tmp_path):
        result = _find_venv(tmp_path)
        assert result is None


# ─── check_venv ───────────────────────────────────────────────────


class TestCheckVenv:
    def test_no_pyproject_no_requirements_silent(self, tmp_path):
        """No Python project markers → no issue."""
        issues = check_venv(tmp_path)
        assert issues == []

    def test_pyproject_without_venv_raises_issue(self, tmp_path):
        """pyproject.toml present but no .venv → warn."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        issues = check_venv(tmp_path)
        assert len(issues) == 1
        issue = issues[0]
        assert issue.category == IssueCategory.DEPENDENCY_MISSING
        assert issue.severity == SEVERITY_WARNING
        assert issue.fix_strategy == FixStrategy.CONFIRM
        assert issue.layer == 1
        assert "virtual environment" in issue.message.lower()

    def test_requirements_txt_without_venv_raises_issue(self, tmp_path):
        """requirements.txt present but no .venv → warn."""
        (tmp_path / "requirements.txt").write_text("requests\n")
        issues = check_venv(tmp_path)
        assert len(issues) == 1

    def test_venv_exists_no_issue(self, tmp_path):
        """When .venv/bin/python exists, no issue."""
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").write_text("#!/bin/sh")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        issues = check_venv(tmp_path)
        assert issues == []

    def test_poetry_lock_suggests_poetry_install(self, tmp_path):
        """poetry.lock present → fix command uses 'poetry install'."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        (tmp_path / "poetry.lock").write_text("")
        issues = check_venv(tmp_path)
        assert len(issues) == 1
        assert "poetry install" in issues[0].fix_command


# ─── _installed_packages ─────────────────────────────────────────


class TestInstalledPackages:
    def test_returns_set_of_package_names(self):
        fake_output = "requests==2.31.0\npytest==7.4.0\nsome-pkg==1.0\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=fake_output)
            result = _installed_packages(Path("/fake/python"))
        assert "requests" in result
        assert "pytest" in result
        assert "some_pkg" in result  # dash normalised to underscore

    def test_timeout_returns_none(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=[], timeout=15)
            result = _installed_packages(Path("/fake/python"))
        assert result is None

    def test_not_found_returns_none(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = _installed_packages(Path("/missing/python"))
        assert result is None


# ─── check_dependencies ──────────────────────────────────────────


class TestCheckDependencies:
    def test_no_pyproject_silent(self, tmp_path):
        issues = check_dependencies(project_root=tmp_path)
        assert issues == []

    def test_missing_package_returns_issue(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'x'\n"
            "[project.optional-dependencies]\ndev = ['nonexistent_pkg_xyz>=1.0']\n"
        )
        with patch("taskfile.diagnostics.checks_venv._installed_packages") as mock_pkg:
            mock_pkg.return_value = set()  # nothing installed
            issues = check_dependencies(groups=["dev"], project_root=tmp_path)
        assert len(issues) >= 1
        assert any("nonexistent_pkg_xyz" in i.message for i in issues)
        assert issues[0].fix_strategy == FixStrategy.CONFIRM

    def test_installed_package_no_issue(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'x'\n"
            "[project.optional-dependencies]\ndev = ['nonexistent_pkg_xyz>=1.0']\n"
        )
        with patch("taskfile.diagnostics.checks_venv._installed_packages") as mock_pkg:
            mock_pkg.return_value = {"nonexistent_pkg_xyz"}
            issues = check_dependencies(groups=["dev"], project_root=tmp_path)
        assert issues == []

    def test_uses_poetry_install_when_lock_present(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'x'\n"
            "[project.optional-dependencies]\ndev = ['nonexistent_pkg_xyz>=0.1']\n"
        )
        (tmp_path / "poetry.lock").write_text("")
        with patch("taskfile.diagnostics.checks_venv._installed_packages") as mock_pkg:
            mock_pkg.return_value = set()
            issues = check_dependencies(groups=["dev"], project_root=tmp_path)
        assert any("poetry install" in i.fix_command for i in issues)


# ─── check_poetry_lock ───────────────────────────────────────────


class TestCheckPoetryLock:
    def test_no_pyproject_silent(self, tmp_path):
        issues = check_poetry_lock(tmp_path)
        assert issues == []

    def test_non_poetry_project_without_lock_silent(self, tmp_path):
        """pyproject.toml without [tool.poetry] → no lock warning."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        issues = check_poetry_lock(tmp_path)
        assert issues == []

    def test_poetry_project_without_lock_warns(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
        issues = check_poetry_lock(tmp_path)
        assert len(issues) == 1
        assert "poetry.lock is missing" in issues[0].message
        assert issues[0].fix_command == "poetry lock"

    def test_lock_in_sync_returns_no_issue(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
        (tmp_path / "poetry.lock").write_text("# lock")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            issues = check_poetry_lock(tmp_path)
        assert issues == []

    def test_lock_out_of_sync_returns_issue(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
        (tmp_path / "poetry.lock").write_text("# lock")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="pyproject.toml changed", stderr="")
            issues = check_poetry_lock(tmp_path)
        assert len(issues) == 1
        assert "out of sync" in issues[0].message
        assert issues[0].fix_command == "poetry lock --no-update"

    def test_poetry_not_installed_returns_info(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
        (tmp_path / "poetry.lock").write_text("# lock")
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            issues = check_poetry_lock(tmp_path)
        assert len(issues) == 1
        assert "poetry is not installed" in issues[0].message
        assert issues[0].severity == SEVERITY_INFO


# ─── ProjectDiagnostics integration ──────────────────────────────


class TestProjectDiagnosticsVenvMethods:
    def test_has_venv_methods(self):
        from taskfile.diagnostics import ProjectDiagnostics

        diag = ProjectDiagnostics()
        assert hasattr(diag, "check_venv")
        assert hasattr(diag, "check_dependencies")
        assert hasattr(diag, "check_poetry_lock")

    def test_check_venv_populates_issues(self, tmp_path):
        from taskfile.diagnostics import ProjectDiagnostics

        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        diag = ProjectDiagnostics()
        with patch("taskfile.diagnostics.checks_venv._find_venv", return_value=None):
            with patch("taskfile.diagnostics.checks_venv.Path.cwd", return_value=tmp_path):
                # Call directly with tmp_path to avoid cwd dependency
                from taskfile.diagnostics.checks_venv import check_venv as _cv

                diag._add_issues(_cv(tmp_path))
        assert len(diag._issues) == 1
        assert "virtual environment" in diag._issues[0].message.lower()
