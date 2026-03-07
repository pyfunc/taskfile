"""Tests for Phase 8 — Deploy Validation Layer.

Covers:
- _scan_file_for_unresolved: detects ${VAR}, {{VAR}}, placeholders
- check_deploy_artifacts: scans deploy/ directory
- validate-deploy gate in deploy recipes
- resolv.conf auto-generation in quadlet
"""

import pytest
import textwrap
from pathlib import Path

from taskfile.diagnostics.checks import (
    _scan_file_for_unresolved,
    check_deploy_artifacts,
)
from taskfile.diagnostics.models import IssueCategory, SEVERITY_WARNING
from taskfile.models import TaskfileConfig
from taskfile.deploy_recipes import expand_deploy_recipe
from taskfile.quadlet import generate_resolv_conf, _RESOLV_CONF_CONTENT


# ═══════════════════════════════════════════════════════════════════════
# 1. _scan_file_for_unresolved
# ═══════════════════════════════════════════════════════════════════════


class TestScanFileForUnresolved:

    def test_detects_dollar_brace_var(self, tmp_path):
        f = tmp_path / "traefik.yml"
        f.write_text("host: ${DOMAIN}\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert len(issues) == 1
        assert "DOMAIN" in issues[0].message
        assert issues[0].category == IssueCategory.CONFIG_ERROR

    def test_detects_double_brace_var(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("email: {{ACME_EMAIL}}\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert len(issues) == 1
        assert "ACME_EMAIL" in issues[0].message

    def test_detects_placeholder_example_com(self, tmp_path):
        f = tmp_path / "traefik-dynamic.yml"
        f.write_text("rule: Host(`example.com`)\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert any("Placeholder" in i.message for i in issues)

    def test_detects_placeholder_changeme(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("password: changeme\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert any("Placeholder" in i.message for i in issues)

    def test_detects_placeholder_your_domain(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("host: your-domain.com\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert any("Placeholder" in i.message for i in issues)

    def test_skips_comments(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("# host: ${DOMAIN}\n// email: ${EMAIL}\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert len(issues) == 0

    def test_multiple_vars_same_line(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("url: https://${USER}:${PASS}@${HOST}\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        var_issues = [i for i in issues if "Unresolved variable" in i.message]
        assert len(var_issues) == 3

    def test_no_issues_in_clean_file(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("host: myapp.production.com\nport: 8080\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert len(issues) == 0

    def test_context_has_line_number(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("line1: ok\nline2: ${VAR}\nline3: ok\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert issues[0].context["line"] == 2

    def test_context_has_variable_name(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("host: ${MY_HOST}\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert issues[0].context["variable"] == "MY_HOST"

    def test_skips_traefik_dot_templates(self, tmp_path):
        """{{.Name}} is valid Traefik Go template syntax, not a placeholder."""
        f = tmp_path / "traefik.yml"
        f.write_text("name: {{.Name}}\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        # .Name starts with dot — should be skipped
        assert len(issues) == 0

    def test_nonexistent_file_returns_empty(self, tmp_path):
        f = tmp_path / "nonexistent.yml"
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert issues == []

    def test_teach_field_populated(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("host: ${DOMAIN}\n")
        issues = _scan_file_for_unresolved(f, tmp_path)
        assert issues[0].teach is not None
        assert "DOMAIN" in issues[0].teach


# ═══════════════════════════════════════════════════════════════════════
# 2. check_deploy_artifacts (directory scan)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckDeployArtifacts:

    def _make_config(self, tmp_path) -> TaskfileConfig:
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text("version: 1\ntasks:\n  hello:\n    cmds:\n      - echo hi\n")
        config = TaskfileConfig.from_dict({
            "variables": {},
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        })
        config.source_path = str(taskfile)
        return config

    def test_no_deploy_dir_returns_empty(self, tmp_path):
        config = self._make_config(tmp_path)
        issues = check_deploy_artifacts(config)
        assert issues == []

    def test_scans_yml_files(self, tmp_path):
        deploy = tmp_path / "deploy"
        deploy.mkdir()
        (deploy / "traefik.yml").write_text("email: ${ACME_EMAIL}\n")
        config = self._make_config(tmp_path)
        issues = check_deploy_artifacts(config)
        assert any("ACME_EMAIL" in i.message for i in issues)

    def test_scans_container_files(self, tmp_path):
        deploy = tmp_path / "deploy" / "quadlet"
        deploy.mkdir(parents=True)
        (deploy / "app.container").write_text("Image=${REGISTRY}/app:${TAG}\n")
        config = self._make_config(tmp_path)
        issues = check_deploy_artifacts(config)
        var_names = {i.context["variable"] for i in issues if "variable" in (i.context or {})}
        assert "REGISTRY" in var_names
        assert "TAG" in var_names

    def test_scans_conf_files(self, tmp_path):
        deploy = tmp_path / "deploy"
        deploy.mkdir()
        (deploy / "resolv.conf").write_text("nameserver 8.8.8.8\n")
        config = self._make_config(tmp_path)
        issues = check_deploy_artifacts(config)
        assert issues == []

    def test_detects_placeholders_in_deploy(self, tmp_path):
        deploy = tmp_path / "deploy"
        deploy.mkdir()
        (deploy / "traefik-dynamic.yml").write_text(
            "rule: Host(`example.com`)\nemail: your-email@example.com\n"
        )
        config = self._make_config(tmp_path)
        issues = check_deploy_artifacts(config)
        assert len(issues) >= 1

    def test_nested_deploy_subdirs(self, tmp_path):
        deploy = tmp_path / "deploy" / "traefik" / "config"
        deploy.mkdir(parents=True)
        (deploy / "dynamic.yml").write_text("host: ${DOMAIN}\n")
        config = self._make_config(tmp_path)
        issues = check_deploy_artifacts(config)
        assert any("DOMAIN" in i.message for i in issues)


# ═══════════════════════════════════════════════════════════════════════
# 3. validate-deploy gate in deploy recipes
# ═══════════════════════════════════════════════════════════════════════


class TestValidateDeployGate:

    def test_validate_deploy_task_generated(self):
        deploy_section = {
            "strategy": "quadlet",
            "images": {"web": "Dockerfile"},
            "registry": "ghcr.io/test",
        }
        tasks = expand_deploy_recipe(deploy_section, {})
        assert "validate-deploy" in tasks
        assert "validate" in tasks["validate-deploy"]["tags"]

    def test_deploy_depends_on_validate(self):
        deploy_section = {
            "strategy": "quadlet",
            "images": {"web": "Dockerfile"},
            "registry": "ghcr.io/test",
        }
        tasks = expand_deploy_recipe(deploy_section, {})
        assert "validate-deploy" in tasks["deploy"]["deps"]

    def test_validate_deploy_before_push(self):
        """validate-deploy should be in deps alongside push."""
        deploy_section = {
            "strategy": "compose",
            "images": {"api": "Dockerfile.api"},
            "registry": "ghcr.io/test",
        }
        tasks = expand_deploy_recipe(deploy_section, {})
        deps = tasks["deploy"]["deps"]
        assert "validate-deploy" in deps
        assert "push-api" in deps

    def test_validate_deploy_in_ssh_push_strategy(self):
        deploy_section = {
            "strategy": "ssh-push",
            "images": {"worker": "Dockerfile.worker"},
            "registry": "ghcr.io/test",
        }
        tasks = expand_deploy_recipe(deploy_section, {})
        assert "validate-deploy" in tasks["deploy"]["deps"]


# ═══════════════════════════════════════════════════════════════════════
# 4. resolv.conf auto-generation
# ═══════════════════════════════════════════════════════════════════════


class TestResolvConfGeneration:

    def test_generate_resolv_conf(self, tmp_path):
        path = generate_resolv_conf(tmp_path)
        assert path.exists()
        assert path.name == "resolv.conf"
        content = path.read_text()
        assert "8.8.8.8" in content
        assert "1.1.1.1" in content

    def test_resolv_conf_content(self):
        assert "nameserver 8.8.8.8" in _RESOLV_CONF_CONTENT
        assert "nameserver 1.1.1.1" in _RESOLV_CONF_CONTENT
        assert "nameserver 8.8.4.4" in _RESOLV_CONF_CONTENT

    def test_generate_creates_dir(self, tmp_path):
        nested = tmp_path / "deep" / "dir"
        path = generate_resolv_conf(nested)
        assert path.exists()
        assert nested.is_dir()
