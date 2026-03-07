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
