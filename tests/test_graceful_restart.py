"""Tests for Phase 11 — Graceful Restart Pattern.

Covers:
- _graceful_restart_cmds: stop → sleep → start pattern
- _post_deploy_health_cmds: per-service + HTTP health verification
- Graceful restart wired into all deploy strategies (quadlet, ssh-push, rollback)
- Post-deploy health gate task generation
- Configurable restart_delay
"""

import pytest

from taskfile.deploy_recipes import (
    expand_deploy_recipe,
    _graceful_restart_cmds,
    _post_deploy_health_cmds,
)


# ═══════════════════════════════════════════════════════════════════════
# 1. _graceful_restart_cmds
# ═══════════════════════════════════════════════════════════════════════


class TestGracefulRestartCmds:

    def test_default_delay(self):
        cmds = _graceful_restart_cmds("web")
        assert len(cmds) == 3
        assert "stop" in cmds[0]
        assert "web" in cmds[0]
        assert cmds[1] == "sleep 3"
        assert "start" in cmds[2]
        assert "web" in cmds[2]

    def test_custom_delay(self):
        cmds = _graceful_restart_cmds("api", restart_delay=10)
        assert cmds[1] == "sleep 10"

    def test_zero_delay(self):
        cmds = _graceful_restart_cmds("worker", restart_delay=0)
        assert cmds[1] == "sleep 0"

    def test_uses_app_name_var(self):
        cmds = _graceful_restart_cmds("db")
        assert "${APP_NAME}-db" in cmds[0]
        assert "${APP_NAME}-db" in cmds[2]

    def test_stop_before_start(self):
        cmds = _graceful_restart_cmds("svc")
        assert "stop" in cmds[0]
        assert "start" in cmds[2]

    def test_uses_remote_prefix(self):
        cmds = _graceful_restart_cmds("web")
        assert cmds[0].startswith("@remote")
        assert cmds[2].startswith("@remote")

    def test_sleep_is_local(self):
        """Sleep runs locally (no @remote prefix)."""
        cmds = _graceful_restart_cmds("web")
        assert not cmds[1].startswith("@remote")


# ═══════════════════════════════════════════════════════════════════════
# 2. _post_deploy_health_cmds
# ═══════════════════════════════════════════════════════════════════════


class TestPostDeployHealthCmds:

    def test_single_service(self):
        cmds = _post_deploy_health_cmds(
            {"web": "Dockerfile"}, "/health", "ghcr.io/test", "${TAG}",
        )
        # One is-active check + one curl
        assert len(cmds) == 2
        assert "is-active" in cmds[0]
        assert "web" in cmds[0]
        assert "curl" in cmds[1]
        assert "/health" in cmds[1]

    def test_multiple_services(self):
        images = {"api": "Dockerfile.api", "web": "Dockerfile.web", "worker": "Dockerfile.worker"}
        cmds = _post_deploy_health_cmds(images, "/healthz", "ghcr.io/x", "${TAG}")
        # 3 is-active checks + 1 curl
        assert len(cmds) == 4
        assert "api" in cmds[0]
        assert "web" in cmds[1]
        assert "worker" in cmds[2]
        assert "/healthz" in cmds[3]

    def test_uses_domain_var(self):
        cmds = _post_deploy_health_cmds({"svc": "Df"}, "/up", "r", "t")
        assert "${DOMAIN}" in cmds[-1]


# ═══════════════════════════════════════════════════════════════════════
# 3. Quadlet deploy uses graceful restart
# ═══════════════════════════════════════════════════════════════════════


class TestQuadletGracefulRestart:

    def _make_quadlet(self, **overrides):
        section = {
            "strategy": "quadlet",
            "images": {"api": "Dockerfile.api", "web": "Dockerfile.web"},
            "registry": "ghcr.io/test",
            **overrides,
        }
        return expand_deploy_recipe(section, {})

    def test_no_hard_restart_in_deploy(self):
        tasks = self._make_quadlet()
        deploy_cmds = tasks["deploy"]["cmds"]
        for cmd in deploy_cmds:
            assert "restart" not in cmd, f"Found hard restart: {cmd}"

    def test_has_stop_and_start(self):
        tasks = self._make_quadlet()
        deploy_cmds = tasks["deploy"]["cmds"]
        stops = [c for c in deploy_cmds if "stop" in c]
        starts = [c for c in deploy_cmds if "start" in c]
        assert len(stops) == 2  # api + web
        assert len(starts) == 2

    def test_has_sleep_between_stop_start(self):
        tasks = self._make_quadlet()
        deploy_cmds = tasks["deploy"]["cmds"]
        sleeps = [c for c in deploy_cmds if c.startswith("sleep")]
        assert len(sleeps) == 2  # one per service

    def test_default_delay_is_3(self):
        tasks = self._make_quadlet()
        deploy_cmds = tasks["deploy"]["cmds"]
        sleeps = [c for c in deploy_cmds if c.startswith("sleep")]
        assert all(c == "sleep 3" for c in sleeps)

    def test_custom_restart_delay(self):
        tasks = self._make_quadlet(restart_delay=5)
        deploy_cmds = tasks["deploy"]["cmds"]
        sleeps = [c for c in deploy_cmds if c.startswith("sleep")]
        assert all(c == "sleep 5" for c in sleeps)

    def test_desc_says_graceful(self):
        tasks = self._make_quadlet()
        assert "graceful" in tasks["deploy"]["desc"].lower()


# ═══════════════════════════════════════════════════════════════════════
# 4. SSH-push deploy uses graceful restart
# ═══════════════════════════════════════════════════════════════════════


class TestSshPushGracefulRestart:

    def test_no_hard_restart(self):
        tasks = expand_deploy_recipe({
            "strategy": "ssh-push",
            "images": {"worker": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        for cmd in tasks["deploy"]["cmds"]:
            assert "restart" not in cmd

    def test_has_graceful_pattern(self):
        tasks = expand_deploy_recipe({
            "strategy": "ssh-push",
            "images": {"worker": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        cmds = tasks["deploy"]["cmds"]
        assert any("stop" in c for c in cmds)
        assert any("start" in c for c in cmds)
        assert any(c.startswith("sleep") for c in cmds)


# ═══════════════════════════════════════════════════════════════════════
# 5. Rollback uses graceful restart
# ═══════════════════════════════════════════════════════════════════════


class TestRollbackGracefulRestart:

    def test_rollback_no_hard_restart(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"api": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        for cmd in tasks["rollback"]["cmds"]:
            assert "restart" not in cmd

    def test_rollback_has_graceful_pattern(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"api": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        cmds = tasks["rollback"]["cmds"]
        assert any("stop" in c for c in cmds)
        assert any("start" in c for c in cmds)
        assert any(c.startswith("sleep") for c in cmds)


# ═══════════════════════════════════════════════════════════════════════
# 6. Post-deploy health gate
# ═══════════════════════════════════════════════════════════════════════


class TestPostDeployHealthGate:

    def test_post_deploy_task_generated(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        assert "post-deploy" in tasks
        assert "health" in tasks["post-deploy"]["tags"]

    def test_post_deploy_has_retries(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Dockerfile"},
            "registry": "ghcr.io/test",
            "health_retries": 10,
        }, {})
        assert tasks["post-deploy"]["retries"] == 10

    def test_post_deploy_checks_services(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"api": "Df.api", "web": "Df.web"},
            "registry": "ghcr.io/test",
        }, {})
        cmds = tasks["post-deploy"]["cmds"]
        assert any("api" in c and "is-active" in c for c in cmds)
        assert any("web" in c and "is-active" in c for c in cmds)
        assert any("curl" in c for c in cmds)

    def test_post_deploy_uses_custom_health_check(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "health_check": "/api/v1/status",
        }, {})
        cmds = tasks["post-deploy"]["cmds"]
        assert any("/api/v1/status" in c for c in cmds)

    def test_compose_strategy_also_has_post_deploy(self):
        tasks = expand_deploy_recipe({
            "strategy": "compose",
            "images": {"app": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        assert "post-deploy" in tasks


# ═══════════════════════════════════════════════════════════════════════
# 7. Auto-generated ops tasks (status, logs, stop, restart, backup)
# ═══════════════════════════════════════════════════════════════════════


class TestOpsTasksCompose:
    """Ops tasks for compose strategy use docker compose commands."""

    def _make(self, **overrides):
        section = {
            "strategy": "compose",
            "images": {"web": "Dockerfile"},
            "registry": "ghcr.io/test",
            **overrides,
        }
        return expand_deploy_recipe(section, {})

    def test_status_generated(self):
        tasks = self._make()
        assert "status" in tasks
        assert "docker compose ps" in tasks["status"]["cmds"]

    def test_logs_generated(self):
        tasks = self._make()
        assert "logs" in tasks
        assert any("docker compose logs" in c for c in tasks["logs"]["cmds"])

    def test_logs_custom_lines(self):
        tasks = self._make(log_lines=100)
        assert any("--tail=100" in c for c in tasks["logs"]["cmds"])

    def test_stop_generated(self):
        tasks = self._make()
        assert "stop" in tasks
        assert "docker compose stop" in tasks["stop"]["cmds"]

    def test_restart_generated(self):
        tasks = self._make()
        assert "restart" in tasks
        assert "docker compose restart" in tasks["restart"]["cmds"]

    def test_no_backup_by_default(self):
        tasks = self._make()
        assert "backup" not in tasks

    def test_ops_tagged(self):
        tasks = self._make()
        for name in ("status", "logs", "stop", "restart"):
            assert "ops" in tasks[name]["tags"]


class TestOpsTasksQuadlet:
    """Ops tasks for quadlet strategy use systemctl + podman."""

    def _make(self, **overrides):
        section = {
            "strategy": "quadlet",
            "images": {"api": "Df.api", "web": "Df.web"},
            "registry": "ghcr.io/test",
            **overrides,
        }
        return expand_deploy_recipe(section, {})

    def test_status_checks_each_service(self):
        tasks = self._make()
        cmds = tasks["status"]["cmds"]
        assert any("api" in c and "is-active" in c for c in cmds)
        assert any("web" in c and "is-active" in c for c in cmds)

    def test_status_shows_podman_ps(self):
        tasks = self._make()
        cmds = tasks["status"]["cmds"]
        assert any("podman ps" in c for c in cmds)

    def test_logs_per_container(self):
        tasks = self._make()
        cmds = tasks["logs"]["cmds"]
        assert any("api" in c and "podman logs" in c for c in cmds)
        assert any("web" in c and "podman logs" in c for c in cmds)

    def test_logs_custom_lines(self):
        tasks = self._make(log_lines=200)
        cmds = tasks["logs"]["cmds"]
        assert any("--tail=200" in c for c in cmds)

    def test_stop_uses_systemctl(self):
        tasks = self._make()
        cmds = tasks["stop"]["cmds"]
        assert all("systemctl" in c for c in cmds)
        assert any("api" in c for c in cmds)
        assert any("web" in c for c in cmds)

    def test_restart_uses_graceful_pattern(self):
        tasks = self._make()
        cmds = tasks["restart"]["cmds"]
        assert any("stop" in c for c in cmds)
        assert any("start" in c for c in cmds)
        assert any(c.startswith("sleep") for c in cmds)

    def test_restart_custom_delay(self):
        tasks = self._make(restart_delay=10)
        cmds = tasks["restart"]["cmds"]
        sleeps = [c for c in cmds if c.startswith("sleep")]
        assert all(c == "sleep 10" for c in sleeps)

    def test_all_ops_use_remote(self):
        tasks = self._make()
        for name in ("status", "logs", "stop"):
            for cmd in tasks[name]["cmds"]:
                if not cmd.startswith("sleep") and not cmd.startswith("echo"):
                    assert "@remote" in cmd, f"{name}: {cmd} missing @remote"


class TestOpsTasksBackup:
    """Backup task generation."""

    def test_backup_generated_when_paths(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "backup_paths": ["/data/volumes", "/data/config"],
        }, {})
        assert "backup" in tasks
        cmds = tasks["backup"]["cmds"]
        assert any("/data/volumes" in c for c in cmds)
        assert any("/data/config" in c for c in cmds)
        assert any("tar" in c for c in cmds)

    def test_backup_not_generated_without_paths(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
        }, {})
        assert "backup" not in tasks

    def test_backup_tagged(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "backup_paths": ["/data"],
        }, {})
        assert "backup" in tasks["backup"]["tags"]
        assert "ops" in tasks["backup"]["tags"]


class TestOpsTasksSshPush:
    """SSH-push strategy also gets systemd ops tasks."""

    def test_ssh_push_has_ops(self):
        tasks = expand_deploy_recipe({
            "strategy": "ssh-push",
            "images": {"worker": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        for name in ("status", "logs", "stop", "restart"):
            assert name in tasks, f"Missing ops task: {name}"

    def test_ssh_push_uses_systemctl(self):
        tasks = expand_deploy_recipe({
            "strategy": "ssh-push",
            "images": {"worker": "Dockerfile"},
            "registry": "ghcr.io/test",
        }, {})
        assert any("systemctl" in c for c in tasks["stop"]["cmds"])


# ═══════════════════════════════════════════════════════════════════════
# 8. Fixop integration tasks
# ═══════════════════════════════════════════════════════════════════════


class TestFixopIntegration:
    """Fixop doctor/drift-check/fix tasks generated from deploy.fixop config."""

    def test_no_fixop_by_default(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
        }, {})
        assert "doctor" not in tasks
        assert "drift-check" not in tasks

    def test_doctor_generated(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "fixop": {"domains": ["example.com"]},
        }, {})
        assert "doctor" in tasks
        assert "fixop" in tasks["doctor"]["tags"]
        assert any("fixop check" in c for c in tasks["doctor"]["cmds"])

    def test_doctor_with_domains(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "fixop": {"domains": ["a.com", "b.com"]},
        }, {})
        cmds = tasks["doctor"]["cmds"]
        assert any("a.com" in c for c in cmds)
        assert any("b.com" in c for c in cmds)

    def test_doctor_with_containers(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"api": "Df.api", "web": "Df.web"},
            "registry": "ghcr.io/test",
            "fixop": {},
        }, {})
        cmds = tasks["doctor"]["cmds"]
        assert any("--containers" in c and "api" in c and "web" in c for c in cmds)

    def test_drift_check_generated(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "fixop": {"readme": "README.md", "source_dir": "sandbox/"},
        }, {})
        assert "drift-check" in tasks
        cmds = tasks["drift-check"]["cmds"]
        assert any("check_file_drift" in c for c in cmds)

    def test_fix_not_generated_by_default(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "fixop": {},
        }, {})
        assert "fix" not in tasks

    def test_fix_generated_when_auto_fix(self):
        tasks = expand_deploy_recipe({
            "strategy": "quadlet",
            "images": {"web": "Df"},
            "registry": "ghcr.io/test",
            "fixop": {"auto_fix": True},
        }, {})
        assert "fix" in tasks
        assert any("fixop fix --auto" in c for c in tasks["fix"]["cmds"])
