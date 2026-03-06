"""Tests for taskfile package."""

import pytest
import yaml
from pathlib import Path

from taskfile.models import TaskfileConfig, Task, Environment
from taskfile.parser import load_taskfile, validate_taskfile, TaskfileNotFoundError
from taskfile.runner import TaskfileRunner
from taskfile.scaffold import generate_taskfile
from taskfile.compose import ComposeFile, load_env_file, resolve_variables
from taskfile.quadlet import generate_container_unit, compose_to_quadlet, generate_network_unit


# ─── Model Tests ─────────────────────────────────────


class TestEnvironment:
    def test_ssh_target(self):
        env = Environment(name="prod", ssh_host="example.com", ssh_user="deploy")
        assert env.ssh_target == "deploy@example.com"

    def test_ssh_target_none_when_no_host(self):
        env = Environment(name="local")
        assert env.ssh_target is None

    def test_resolve_variables(self):
        env = Environment(name="prod", variables={"TAG": "v2"})
        result = env.resolve_variables({"APP": "test", "TAG": "v1"})
        assert result["APP"] == "test"
        assert result["TAG"] == "v2"  # env overrides global

    def test_new_fields_defaults(self):
        env = Environment(name="local")
        assert env.compose_file == "docker-compose.yml"
        assert env.env_file is None
        assert env.quadlet_dir == "deploy/quadlet"
        assert env.quadlet_remote_dir == "~/.config/containers/systemd"

    def test_new_fields_from_dict(self):
        data = {
            "version": "1",
            "environments": {
                "prod": {
                    "ssh_host": "example.com",
                    "env_file": ".env.prod",
                    "quadlet_dir": "deploy/prod",
                    "quadlet_remote_dir": "/etc/containers/systemd",
                    "service_manager": "quadlet",
                }
            },
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        prod = config.environments["prod"]
        assert prod.env_file == ".env.prod"
        assert prod.quadlet_dir == "deploy/prod"
        assert prod.quadlet_remote_dir == "/etc/containers/systemd"
        assert prod.service_manager == "quadlet"

class TestSmartDefaults:
    """Test smart defaults in _parse_environments."""

    def test_remote_env_defaults_to_podman_quadlet(self):
        data = {
            "environments": {
                "prod": {"ssh_host": "example.com"},
            },
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        prod = config.environments["prod"]
        assert prod.container_runtime == "podman"
        assert prod.service_manager == "quadlet"
        assert prod.ssh_key == "~/.ssh/id_ed25519"
        assert prod.env_file == ".env.prod"

    def test_local_env_defaults_to_docker_compose(self):
        data = {
            "environments": {
                "dev": {},
            },
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        dev = config.environments["dev"]
        assert dev.container_runtime == "docker"
        assert dev.compose_command == "docker compose"
        assert dev.service_manager == "compose"
        assert dev.ssh_key is None
        assert dev.env_file == ".env.dev"

    def test_explicit_override_beats_smart_defaults(self):
        data = {
            "environments": {
                "prod": {
                    "ssh_host": "example.com",
                    "container_runtime": "docker",
                    "service_manager": "compose",
                    "ssh_key": "~/.ssh/custom_key",
                    "env_file": ".env.production",
                },
            },
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        prod = config.environments["prod"]
        assert prod.container_runtime == "docker"
        assert prod.service_manager == "compose"
        assert prod.ssh_key == "~/.ssh/custom_key"
        assert prod.env_file == ".env.production"

    def test_empty_env_section_gets_local(self):
        config = TaskfileConfig.from_dict({"tasks": {}})
        assert "local" in config.environments
        local = config.environments["local"]
        assert local.container_runtime == "docker"


class TestEnvironmentDefaults:
    """Test environment_defaults merging into environments."""

    def test_defaults_applied_to_all_envs(self):
        data = {
            "environment_defaults": {
                "ssh_user": "pi",
                "ssh_key": "~/.ssh/fleet",
                "container_runtime": "podman",
            },
            "environments": {
                "node-1": {"ssh_host": "10.0.0.1"},
                "node-2": {"ssh_host": "10.0.0.2"},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        for name in ("node-1", "node-2"):
            env = config.environments[name]
            assert env.ssh_user == "pi"
            assert env.ssh_key == "~/.ssh/fleet"
            assert env.container_runtime == "podman"

    def test_env_overrides_defaults(self):
        data = {
            "environment_defaults": {
                "ssh_user": "pi",
                "container_runtime": "podman",
            },
            "environments": {
                "local": {"container_runtime": "docker"},
                "node-1": {"ssh_host": "10.0.0.1", "ssh_user": "admin"},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        assert config.environments["local"].container_runtime == "docker"
        assert config.environments["node-1"].ssh_user == "admin"

    def test_variables_deep_merged(self):
        data = {
            "environment_defaults": {
                "variables": {"COMMON": "shared", "LEVEL": "info"},
            },
            "environments": {
                "gw-1": {
                    "ssh_host": "10.0.0.1",
                    "variables": {"GATEWAY_ID": "gw-1", "LEVEL": "debug"},
                },
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        gw = config.environments["gw-1"]
        assert gw.variables["COMMON"] == "shared"
        assert gw.variables["GATEWAY_ID"] == "gw-1"
        assert gw.variables["LEVEL"] == "debug"  # env overrides default


class TestAddons:
    """Test addons: system expansion into tasks."""

    def test_postgres_addon(self):
        data = {
            "addons": [
                {"postgres": {"db_name": "myapp", "backup_dir": "/tmp/bak"}},
            ],
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        assert "db-status" in config.tasks
        assert "db-backup" in config.tasks
        assert "db-migrate" in config.tasks
        assert "db-vacuum" in config.tasks
        assert "db-prune-backups" in config.tasks
        assert "/tmp/bak" in config.tasks["db-backup"].commands[0]

    def test_monitoring_addon(self):
        data = {
            "addons": [
                {"monitoring": {"grafana": "http://g:3000"}},
            ],
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        assert "mon-status" in config.tasks
        assert "mon-alerts" in config.tasks
        assert "mon-setup" in config.tasks

    def test_redis_addon(self):
        data = {
            "addons": [
                {"redis": {"url": "redis://myredis:6380"}},
            ],
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        assert "redis-status" in config.tasks
        assert "redis-info" in config.tasks
        # Check host/port parsing
        assert "myredis" in config.tasks["redis-status"].commands[0]
        assert "6380" in config.tasks["redis-status"].commands[0]

    def test_multiple_addons(self):
        data = {
            "addons": [
                {"postgres": {"db_name": "x"}},
                {"redis": {}},
            ],
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        assert "db-status" in config.tasks
        assert "redis-status" in config.tasks

    def test_addon_string_shorthand(self):
        data = {
            "addons": ["postgres"],
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        assert "db-status" in config.tasks

    def test_user_task_overrides_addon(self):
        data = {
            "addons": [{"postgres": {}}],
            "tasks": {
                "db-status": {"desc": "Custom status", "cmds": ["echo custom"]},
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["db-status"].description == "Custom status"

    def test_unknown_addon_raises(self):
        import pytest
        data = {
            "addons": ["nonexistent"],
            "tasks": {},
        }
        with pytest.raises(ValueError, match="Unknown addon"):
            TaskfileConfig.from_dict(data)


class TestDeployRecipe:
    """Test deploy: recipe expansion into tasks."""

    def test_quadlet_recipe_generates_tasks(self):
        data = {
            "variables": {"APP_NAME": "myapp", "REGISTRY": "ghcr.io/org"},
            "deploy": {
                "strategy": "quadlet",
                "images": {
                    "api": "services/api/Dockerfile",
                    "web": "services/web/Dockerfile",
                },
                "registry": "ghcr.io/org",
                "health_check": "/health",
            },
            "tasks": {"lint": {"cmds": ["ruff check ."]}},
        }
        config = TaskfileConfig.from_dict(data)
        # Recipe should generate: build-api, build-web, build-all, push-api, push-web, push-all, deploy, health, rollback
        assert "build-api" in config.tasks
        assert "build-web" in config.tasks
        assert "build-all" in config.tasks
        assert "push-all" in config.tasks
        assert "deploy" in config.tasks
        assert "health" in config.tasks
        assert "rollback" in config.tasks
        # User-defined task preserved
        assert "lint" in config.tasks
        # deploy task uses quadlet strategy
        assert "quadlet" in config.tasks["deploy"].description.lower()

    def test_compose_recipe(self):
        data = {
            "deploy": {
                "strategy": "compose",
                "images": {"app": "Dockerfile"},
                "registry": "ghcr.io/org",
            },
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        assert "deploy" in config.tasks
        assert "compose" in config.tasks["deploy"].description.lower()

    def test_user_task_overrides_recipe(self):
        data = {
            "deploy": {
                "strategy": "quadlet",
                "images": {"api": "Dockerfile"},
                "registry": "ghcr.io/org",
            },
            "tasks": {
                "deploy": {"desc": "My custom deploy", "cmds": ["echo custom"]},
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["deploy"].description == "My custom deploy"
        assert config.tasks["deploy"].commands == ["echo custom"]

    def test_single_image_no_build_all(self):
        data = {
            "deploy": {
                "strategy": "ssh-push",
                "images": {"app": "Dockerfile"},
                "registry": "ghcr.io/org",
            },
            "tasks": {},
        }
        config = TaskfileConfig.from_dict(data)
        assert "build-app" in config.tasks
        assert "build-all" not in config.tasks  # only 1 image, no build-all needed


class TestHostsShorthand:
    """Test hosts: compact syntax expansion."""

    def test_basic_hosts_expansion(self):
        data = {
            "hosts": {
                "_defaults": {"user": "deploy", "runtime": "podman"},
                "prod-eu": {"host": "eu.example.com", "region": "eu-west-1"},
                "prod-us": {"host": "us.example.com", "region": "us-east-1"},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        assert "prod-eu" in config.environments
        assert "prod-us" in config.environments
        eu = config.environments["prod-eu"]
        assert eu.ssh_host == "eu.example.com"
        assert eu.ssh_user == "deploy"
        assert eu.container_runtime == "podman"
        assert eu.variables.get("REGION") == "eu-west-1"

    def test_hosts_with_groups(self):
        data = {
            "hosts": {
                "prod-eu": {"host": "eu.example.com"},
                "prod-us": {"host": "us.example.com"},
                "_groups": {
                    "all-prod": {
                        "members": ["prod-eu", "prod-us"],
                        "strategy": "canary",
                        "canary_count": 1,
                    },
                },
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        assert "all-prod" in config.environment_groups
        grp = config.environment_groups["all-prod"]
        assert grp.strategy == "canary"
        assert grp.members == ["prod-eu", "prod-us"]

    def test_hosts_string_shorthand(self):
        data = {
            "hosts": {
                "_defaults": {"user": "pi", "key": "~/.ssh/fleet"},
                "node-1": "192.168.1.10",
                "node-2": "192.168.1.11",
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        n1 = config.environments["node-1"]
        assert n1.ssh_host == "192.168.1.10"
        assert n1.ssh_user == "pi"
        assert n1.ssh_key == "~/.ssh/fleet"

    def test_hosts_extra_keys_become_variables(self):
        data = {
            "hosts": {
                "gw": {"host": "10.0.0.1", "gateway_id": "factory-1", "protocol": "mqtt"},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        gw = config.environments["gw"]
        assert gw.variables["GATEWAY_ID"] == "factory-1"
        assert gw.variables["PROTOCOL"] == "mqtt"

    def test_hosts_merged_with_existing_environments(self):
        data = {
            "environments": {
                "local": {"container_runtime": "docker"},
            },
            "hosts": {
                "prod": {"host": "prod.example.com"},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        assert "local" in config.environments
        assert "prod" in config.environments

    def test_hosts_entry_overrides_defaults(self):
        data = {
            "hosts": {
                "_defaults": {"user": "deploy", "env_file": ".env.prod"},
                "special": {"host": "s.example.com", "user": "admin", "env_file": ".env.special"},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        s = config.environments["special"]
        assert s.ssh_user == "admin"
        assert s.env_file == ".env.special"


class TestTask:
    def test_should_run_on_all_envs(self):
        task = Task(name="build", env_filter=None)
        assert task.should_run_on("local") is True
        assert task.should_run_on("prod") is True

    def test_should_run_on_filtered(self):
        task = Task(name="deploy", env_filter=["prod", "staging"])
        assert task.should_run_on("prod") is True
        assert task.should_run_on("local") is False

    def test_parallel_default_false(self):
        task = Task(name="t")
        assert task.parallel is False

    def test_parallel_from_dict(self):
        data = {
            "tasks": {
                "pub": {
                    "cmds": ["echo"],
                    "parallel": True,
                    "deps": ["a", "b"],
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["pub"].parallel is True

    def test_continue_on_error_alias(self):
        """Test that continue_on_error maps to ignore_errors."""
        data = {
            "tasks": {
                "pub": {
                    "cmds": ["echo"],
                    "continue_on_error": True,
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["pub"].ignore_errors is True

    def test_condition_field(self):
        data = {
            "tasks": {
                "pub": {
                    "cmds": ["echo"],
                    "condition": "test -f pyproject.toml",
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["pub"].condition == "test -f pyproject.toml"

class TestTaskfileConfig:
    def test_from_dict_minimal(self):
        data = {
            "version": "1",
            "name": "test",
            "tasks": {
                "build": {"cmds": ["echo build"]},
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.name == "test"
        assert "build" in config.tasks
        assert "local" in config.environments

    def test_from_dict_shorthand_tasks(self):
        data = {
            "tasks": {
                "hello": ["echo hello", "echo world"],
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.tasks["hello"].commands == ["echo hello", "echo world"]

    def test_from_dict_full(self):
        data = {
            "version": "1",
            "name": "full-test",
            "variables": {"APP": "myapp"},
            "default_env": "local",
            "environments": {
                "local": {"container_runtime": "docker"},
                "prod": {
                    "ssh_host": "server.com",
                    "ssh_user": "deploy",
                    "container_runtime": "podman",
                },
            },
            "tasks": {
                "build": {
                    "desc": "Build it",
                    "cmds": ["docker build ."],
                    "deps": [],
                },
                "deploy": {
                    "desc": "Deploy it",
                    "cmds": ["echo deploy"],
                    "deps": ["build"],
                    "env": ["prod"],
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert config.environments["prod"].ssh_host == "server.com"
        assert config.tasks["deploy"].env_filter == ["prod"]
        assert config.tasks["deploy"].deps == ["build"]

class TestEnvFile:
    def test_load_env_file(self, tmp_path):
        envfile = tmp_path / ".env.test"
        envfile.write_text(
            "DOMAIN=example.com\n"
            "TAG=v1.2.3\n"
            'QUOTED="hello world"\n'
            "# comment\n"
            "\n"
            "EMPTY=\n"
        )
        env = load_env_file(envfile)
        assert env["DOMAIN"] == "example.com"
        assert env["TAG"] == "v1.2.3"
        assert env["QUOTED"] == "hello world"
        assert env["EMPTY"] == ""

    def test_load_missing_env_file(self):
        env = load_env_file("/nonexistent/.env")
        assert env == {}

class TestResolveVariables:
    def test_simple_var(self):
        assert resolve_variables("${APP}", {"APP": "myapp"}) == "myapp"

    def test_default_value(self):
        assert resolve_variables("${APP:-fallback}", {}) == "fallback"

    def test_default_not_used(self):
        assert resolve_variables("${APP:-fallback}", {"APP": "real"}) == "real"

    def test_simple_dollar(self):
        assert resolve_variables("$APP", {"APP": "myapp"}) == "myapp"

    def test_unresolved_kept(self):
        result = resolve_variables("${UNKNOWN}", {})
        assert result == "${UNKNOWN}"

    def test_mixed(self):
        result = resolve_variables(
            "Host(`${APP}.${DOMAIN:-localhost}`)",
            {"APP": "web"},
        )
        assert result == "Host(`web.localhost`)"

class TestPipelineConfig:
    """Test PipelineConfig parsing."""

    def test_from_dict_basic(self):
        from taskfile.models import PipelineConfig
        data = {
            "stages": [
                {"name": "test", "tasks": ["lint", "test"]},
                {"name": "build", "tasks": ["build"], "docker_in_docker": True},
                {"name": "deploy", "tasks": ["deploy"], "env": "prod", "when": "manual"},
            ],
            "branches": ["main", "develop"],
        }
        p = PipelineConfig.from_dict(data)
        assert len(p.stages) == 3
        assert p.stages[0].name == "test"
        assert p.stages[0].tasks == ["lint", "test"]
        assert p.stages[1].docker_in_docker is True
        assert p.stages[2].env == "prod"
        assert p.stages[2].when == "manual"
        assert p.branches == ["main", "develop"]

    def test_from_dict_shorthand(self):
        from taskfile.models import PipelineConfig
        data = {"stages": ["test", "build", "deploy"]}
        p = PipelineConfig.from_dict(data)
        assert len(p.stages) == 3
        assert p.stages[0].name == "test"
        assert p.stages[0].tasks == ["test"]

    def test_from_dict_empty(self):
        from taskfile.models import PipelineConfig
        p = PipelineConfig.from_dict({})
        assert p.stages == []
        assert p.python_version == "3.12"
        assert p.runner_image == "ubuntu-latest"

    def test_infer_from_tasks(self):
        from taskfile.models import PipelineConfig, Task
        p = PipelineConfig.from_dict({})
        tasks = {
            "lint": Task(name="lint", stage="test"),
            "unit-test": Task(name="unit-test", stage="test"),
            "build": Task(name="build", stage="build"),
            "deploy": Task(name="deploy", stage="deploy"),
            "cleanup": Task(name="cleanup"),  # no stage
        }
        p.infer_from_tasks(tasks)
        assert len(p.stages) == 3
        assert p.stages[0].name == "test"
        assert set(p.stages[0].tasks) == {"lint", "unit-test"}

    def test_infer_skipped_when_stages_exist(self):
        from taskfile.models import PipelineConfig, Task
        data = {"stages": [{"name": "custom", "tasks": ["build"]}]}
        p = PipelineConfig.from_dict(data)
        tasks = {"lint": Task(name="lint", stage="test")}
        p.infer_from_tasks(tasks)
        # Should NOT add inferred stages because explicit stages exist
        assert len(p.stages) == 1
        assert p.stages[0].name == "custom"

    def test_taskfile_config_parses_pipeline(self):
        from taskfile.models import TaskfileConfig
        data = {
            "name": "myproject",
            "tasks": {
                "test": {"cmds": ["pytest"], "stage": "test"},
                "build": {"cmds": ["docker build ."], "stage": "build"},
            },
            "pipeline": {
                "stages": [
                    {"name": "test", "tasks": ["test"]},
                    {"name": "build", "tasks": ["build"], "docker_in_docker": True},
                ],
                "branches": ["main"],
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert len(config.pipeline.stages) == 2
        assert config.pipeline.stages[1].docker_in_docker is True
        assert config.tasks["test"].stage == "test"

    def test_taskfile_config_infers_pipeline(self):
        from taskfile.models import TaskfileConfig
        data = {
            "tasks": {
                "lint": {"cmds": ["ruff ."], "stage": "test"},
                "test": {"cmds": ["pytest"], "stage": "test"},
                "build": {"cmds": ["docker build ."], "stage": "build"},
            },
        }
        config = TaskfileConfig.from_dict(data)
        assert len(config.pipeline.stages) == 2


class TestEnvironmentGroup:
    """Test EnvironmentGroup parsing."""

    def test_parse_groups(self):
        from taskfile.models import TaskfileConfig
        data = {
            "environment_groups": {
                "kiosks": {
                    "members": ["kiosk-lobby", "kiosk-cafe"],
                    "strategy": "rolling",
                    "max_parallel": 1,
                },
                "sensors": {
                    "members": ["sensor-yard", "sensor-roof"],
                    "strategy": "parallel",
                    "max_parallel": 5,
                },
            },
            "environments": {
                "kiosk-lobby": {"ssh_host": "192.168.1.50", "ssh_user": "pi"},
                "kiosk-cafe": {"ssh_host": "192.168.1.51", "ssh_user": "pi"},
                "sensor-yard": {"ssh_host": "192.168.1.60", "ssh_user": "pi"},
                "sensor-roof": {"ssh_host": "192.168.1.61", "ssh_user": "pi"},
            },
            "tasks": {"deploy": {"cmds": ["echo deploy"]}},
        }
        config = TaskfileConfig.from_dict(data)
        assert len(config.environment_groups) == 2
        assert config.environment_groups["kiosks"].strategy == "rolling"
        assert config.environment_groups["kiosks"].members == ["kiosk-lobby", "kiosk-cafe"]
        assert config.environment_groups["kiosks"].max_parallel == 1
        assert config.environment_groups["sensors"].strategy == "parallel"

    def test_parse_groups_defaults(self):
        from taskfile.models import TaskfileConfig
        data = {
            "environment_groups": {
                "fleet": {"members": ["a", "b"]},
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        grp = config.environment_groups["fleet"]
        assert grp.strategy == "parallel"
        assert grp.max_parallel == 5
        assert grp.canary_count == 1

    def test_parse_groups_empty(self):
        from taskfile.models import TaskfileConfig
        data = {"tasks": {"t": {"cmds": ["echo"]}}}
        config = TaskfileConfig.from_dict(data)
        assert config.environment_groups == {}

    def test_canary_count(self):
        from taskfile.models import TaskfileConfig
        data = {
            "environment_groups": {
                "displays": {
                    "members": ["d1", "d2", "d3"],
                    "strategy": "canary",
                    "canary_count": 1,
                },
            },
            "tasks": {"t": {"cmds": ["echo"]}},
        }
        config = TaskfileConfig.from_dict(data)
        grp = config.environment_groups["displays"]
        assert grp.strategy == "canary"
        assert grp.canary_count == 1
        assert len(grp.members) == 3
