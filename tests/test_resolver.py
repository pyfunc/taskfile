"""Tests for TaskResolver — pure logic (no IO) for task resolution and variable expansion."""

import pytest
from taskfile.models import TaskfileConfig
from taskfile.runner.resolver import TaskResolver


class TestTaskResolver:
    """Tests for the pure-logic TaskResolver extracted in Phase 3."""

    def _make_resolver(self, tasks_data: dict, env_name="local", **kwargs):
        data = {
            "variables": {"APP": "test", "TAG": "latest"},
            "environments": {
                "local": {"container_runtime": "docker"},
                "prod": {
                    "ssh_host": "example.com",
                    "container_runtime": "podman",
                },
            },
            "tasks": tasks_data,
        }
        config = TaskfileConfig.from_dict(data)
        return TaskResolver(config, env_name=env_name, **kwargs)

    # ─── Variable expansion ───

    def test_expand_variables_shell_syntax(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}})
        assert resolver.expand_variables("${APP}:${TAG}") == "test:latest"

    def test_expand_variables_mustache_syntax(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}})
        assert resolver.expand_variables("{{APP}}:{{TAG}}") == "test:latest"

    def test_expand_variables_non_string(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}})
        assert resolver.expand_variables(42) == 42

    def test_expand_variables_with_overrides(self):
        resolver = self._make_resolver(
            {"t": {"cmds": ["echo"]}},
            var_overrides={"TAG": "v2.0"},
        )
        assert resolver.expand_variables("${TAG}") == "v2.0"

    # ─── Environment resolution ───

    def test_resolve_existing_environment(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}}, env_name="prod")
        assert resolver.env.name == "prod"
        assert resolver.env.ssh_host == "example.com"
        assert resolver.env.container_runtime == "podman"

    def test_resolve_missing_environment_returns_default(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}}, env_name="staging")
        assert resolver.env.name == "staging"
        assert resolver.env.container_runtime == "docker"  # default

    def test_env_is_defined(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}}, env_name="local")
        assert resolver.env_is_defined() is True

    def test_env_is_not_defined(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}}, env_name="staging")
        assert resolver.env_is_defined() is False

    # ─── Platform resolution ───

    def test_resolve_existing_platform(self):
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {"web": {"variables": {"PORT": "3000"}}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        resolver = TaskResolver(config, platform_name="web")
        assert resolver.platform is not None
        assert resolver.platform.variables["PORT"] == "3000"

    def test_resolve_missing_platform(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}}, platform_name="ios")
        assert resolver.platform is None

    def test_resolve_no_platform(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}})
        assert resolver.platform is None

    def test_platform_is_defined(self):
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {"web": {}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        resolver = TaskResolver(config, platform_name="web")
        assert resolver.platform_is_defined() is True

    def test_platform_is_not_defined(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}}, platform_name="ios")
        assert resolver.platform_is_defined() is False

    # ─── Task lookup ───

    def test_get_task_existing(self):
        resolver = self._make_resolver({"build": {"cmds": ["make"]}})
        task = resolver.get_task("build")
        assert task is not None

    def test_get_task_missing(self):
        resolver = self._make_resolver({"build": {"cmds": ["make"]}})
        assert resolver.get_task("deploy") is None

    def test_available_task_names(self):
        resolver = self._make_resolver(
            {
                "build": {"cmds": ["make"]},
                "test": {"cmds": ["pytest"]},
                "deploy": {"cmds": ["deploy"]},
            }
        )
        assert resolver.available_task_names() == ["build", "deploy", "test"]

    # ─── Task filtering ───

    def test_should_skip_env_filter(self):
        resolver = self._make_resolver(
            {"deploy": {"cmds": ["echo"], "env": ["prod"]}},
            env_name="local",
        )
        task = resolver.get_task("deploy")
        skip, reason = resolver.should_skip_task(task, "deploy")
        assert skip is True
        assert "env" in reason

    def test_should_not_skip_matching_env(self):
        resolver = self._make_resolver(
            {"deploy": {"cmds": ["echo"], "env": ["prod"]}},
            env_name="prod",
        )
        task = resolver.get_task("deploy")
        skip, reason = resolver.should_skip_task(task, "deploy")
        assert skip is False

    def test_should_skip_platform_filter(self):
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {"web": {}, "mobile": {}},
            "tasks": {"web-only": {"cmds": ["echo"], "platform": ["web"]}},
        }
        config = TaskfileConfig.from_dict(data)
        resolver = TaskResolver(config, platform_name="mobile")
        task = resolver.get_task("web-only")
        skip, reason = resolver.should_skip_task(task, "web-only")
        assert skip is True
        assert "platform" in reason

    def test_should_not_skip_no_filters(self):
        resolver = self._make_resolver({"build": {"cmds": ["echo"]}})
        task = resolver.get_task("build")
        skip, reason = resolver.should_skip_task(task, "build")
        assert skip is False

    # ─── Dependency ordering ───

    def test_dependency_order_simple(self):
        resolver = self._make_resolver(
            {
                "build": {"cmds": ["make"]},
                "test": {"cmds": ["pytest"], "deps": ["build"]},
            }
        )
        order = resolver.get_dependency_order("test")
        assert order == ["build", "test"]

    def test_dependency_order_chain(self):
        resolver = self._make_resolver(
            {
                "build": {"cmds": ["make"]},
                "test": {"cmds": ["pytest"], "deps": ["build"]},
                "deploy": {"cmds": ["deploy"], "deps": ["test"]},
            }
        )
        order = resolver.get_dependency_order("deploy")
        assert order == ["build", "test", "deploy"]

    def test_dependency_order_no_deps(self):
        resolver = self._make_resolver({"build": {"cmds": ["make"]}})
        order = resolver.get_dependency_order("build")
        assert order == ["build"]

    def test_circular_dependency_detected(self):
        resolver = self._make_resolver(
            {
                "a": {"cmds": ["echo"], "deps": ["b"]},
                "b": {"cmds": ["echo"], "deps": ["a"]},
            }
        )
        with pytest.raises(ValueError, match="Circular dependency"):
            resolver.get_dependency_order("a")

    # ─── Variable resolution order ───

    def test_variable_resolution_order(self):
        """Test global → env → platform → CLI override order."""
        data = {
            "variables": {"APP": "global", "TAG": "global"},
            "environments": {
                "test": {"variables": {"TAG": "env", "ENV_VAR": "env"}},
            },
            "platforms": {
                "web": {"variables": {"TAG": "platform", "PLAT_VAR": "platform"}},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        resolver = TaskResolver(
            config,
            env_name="test",
            platform_name="web",
            var_overrides={"TAG": "cli"},
        )
        assert resolver.variables["TAG"] == "cli"
        assert resolver.variables["PLAT_VAR"] == "platform"
        assert resolver.variables["ENV_VAR"] == "env"
        assert resolver.variables["APP"] == "global"

    def test_built_in_variables(self):
        resolver = self._make_resolver({"t": {"cmds": ["echo"]}}, env_name="local")
        assert resolver.variables["ENV"] == "local"
        assert resolver.variables["RUNTIME"] == "docker"
        assert resolver.variables["COMPOSE"] == "docker compose"
        assert "PLATFORM" not in resolver.variables

    def test_built_in_platform_variable(self):
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {"web": {}},
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        resolver = TaskResolver(config, platform_name="web")
        assert resolver.variables["PLATFORM"] == "web"
