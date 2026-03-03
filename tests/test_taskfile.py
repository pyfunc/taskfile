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


class TestTask:
    def test_should_run_on_all_envs(self):
        task = Task(name="build", env_filter=None)
        assert task.should_run_on("local") is True
        assert task.should_run_on("prod") is True

    def test_should_run_on_filtered(self):
        task = Task(name="deploy", env_filter=["prod", "staging"])
        assert task.should_run_on("prod") is True
        assert task.should_run_on("local") is False


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


# ─── Parser Tests ────────────────────────────────────

class TestParser:
    def test_load_from_file(self, tmp_path):
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hi"]}},
        }))
        config = load_taskfile(taskfile)
        assert "hello" in config.tasks

    def test_not_found(self, tmp_path):
        with pytest.raises(TaskfileNotFoundError):
            load_taskfile(tmp_path / "nonexistent.yml")

    def test_validate_missing_dep(self):
        config = TaskfileConfig.from_dict({
            "tasks": {
                "deploy": {"cmds": ["echo"], "deps": ["nonexistent"]},
            }
        })
        warnings = validate_taskfile(config)
        assert any("nonexistent" in w for w in warnings)

    def test_validate_empty_commands(self):
        config = TaskfileConfig.from_dict({
            "tasks": {
                "empty": {"desc": "nothing here"},
            }
        })
        warnings = validate_taskfile(config)
        assert any("no commands" in w for w in warnings)


# ─── Runner Tests ────────────────────────────────────

class TestRunner:
    def _make_runner(self, tasks_data: dict, env_name="local", **kwargs):
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
        return TaskfileRunner(config=config, env_name=env_name, **kwargs)

    def test_expand_variables(self):
        runner = self._make_runner({"t": {"cmds": ["echo"]}})
        assert runner.expand_variables("${APP}:${TAG}") == "test:latest"
        assert runner.expand_variables("{{APP}}:{{TAG}}") == "test:latest"

    def test_run_simple_task(self):
        runner = self._make_runner({
            "hello": {"cmds": ["echo hello"]},
        })
        assert runner.run_task("hello") is True

    def test_run_unknown_task(self):
        runner = self._make_runner({
            "hello": {"cmds": ["echo hello"]},
        })
        assert runner.run_task("nonexistent") is False

    def test_env_filter_skips_task(self):
        runner = self._make_runner(
            {"deploy": {"cmds": ["echo deploy"], "env": ["prod"]}},
            env_name="local",
        )
        # Should skip (return True) but not execute
        assert runner.run_task("deploy") is True

    def test_dry_run(self):
        runner = self._make_runner(
            {"hello": {"cmds": ["echo hello"]}},
            dry_run=True,
        )
        assert runner.run_task("hello") is True

    def test_dependency_chain(self):
        runner = self._make_runner({
            "build": {"cmds": ["echo build"]},
            "test": {"cmds": ["echo test"], "deps": ["build"]},
            "deploy": {"cmds": ["echo deploy"], "deps": ["test"]},
        })
        assert runner.run_task("deploy") is True
        assert "build" in runner._executed
        assert "test" in runner._executed
        assert "deploy" in runner._executed

    def test_failed_command(self):
        runner = self._make_runner({
            "fail": {"cmds": ["exit 1"]},
        })
        assert runner.run_task("fail") is False

    def test_ignore_errors(self):
        runner = self._make_runner({
            "fail": {"cmds": ["exit 1"], "ignore_errors": True},
        })
        assert runner.run_task("fail") is True


# ─── Scaffold Tests ──────────────────────────────────

class TestScaffold:
    @pytest.mark.parametrize("template", ["minimal", "web", "podman", "codereview", "full"])
    def test_generate_valid_yaml(self, template):
        content = generate_taskfile(template)
        data = yaml.safe_load(content)
        assert isinstance(data, dict)
        assert "tasks" in data

    @pytest.mark.parametrize("template", ["minimal", "web", "podman", "codereview", "full"])
    def test_generated_config_parses(self, template):
        content = generate_taskfile(template)
        data = yaml.safe_load(content)
        config = TaskfileConfig.from_dict(data)
        assert len(config.tasks) > 0
        assert len(config.environments) > 0


# ─── Compose Parser Tests ────────────────────────────

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


class TestComposeFile:
    def test_load_compose(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(yaml.dump({
            "services": {
                "app": {
                    "image": "myapp:latest",
                    "ports": ["3000:3000"],
                    "labels": {
                        "traefik.enable": "true",
                        "traefik.http.routers.app.rule": "Host(`app.${DOMAIN}`)",
                    },
                }
            }
        }))

        envfile = tmp_path / ".env.test"
        envfile.write_text("DOMAIN=example.com\n")

        cf = ComposeFile(compose, env_file=envfile)
        assert "app" in cf.services
        labels = cf.get_traefik_labels("app")
        assert "traefik.http.routers.app.rule" in labels
        assert "example.com" in labels["traefik.http.routers.app.rule"]

    def test_service_names(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(yaml.dump({
            "services": {
                "web": {"image": "nginx"},
                "db": {"image": "postgres"},
                "redis": {"image": "redis"},
            }
        }))
        cf = ComposeFile(compose)
        assert sorted(cf.service_names()) == ["db", "redis", "web"]


# ─── Quadlet Generator Tests ─────────────────────────

class TestQuadletGenerator:
    def test_generate_container_unit(self):
        service = {
            "image": "ghcr.io/softreck/app:latest",
            "ports": ["3000:3000"],
            "environment": {"NODE_ENV": "production", "PORT": "3000"},
            "volumes": ["app-data:/data"],
            "networks": ["proxy"],
            "labels": {
                "traefik.enable": "true",
                "traefik.http.routers.app.rule": "Host(`app.codereview.pl`)",
            },
            "restart": "always",
            "deploy": {
                "resources": {
                    "limits": {"memory": "96m", "cpus": "0.5"}
                }
            },
        }
        result = generate_container_unit("app", service)

        assert "[Unit]" in result
        assert "[Container]" in result
        assert "[Service]" in result
        assert "[Install]" in result
        assert "Image=ghcr.io/softreck/app:latest" in result
        assert "ContainerName=app" in result
        assert "AutoUpdate=registry" in result
        assert "PublishPort=3000:3000" in result
        assert "Environment=NODE_ENV=production" in result
        assert "Volume=app-data.volume:/data" in result
        assert "Network=proxy.network" in result
        assert "Label=traefik.enable=true" in result
        assert "--memory=96m" in result
        assert "--cpus=0.5" in result
        assert "Restart=always" in result

    def test_generate_with_depends_on(self):
        service = {
            "image": "myapp:latest",
            "depends_on": ["db", "redis"],
            "networks": ["backend"],
        }
        result = generate_container_unit("app", service)
        assert "After=db.service" in result
        assert "Requires=db.service" in result
        assert "After=redis.service" in result

    def test_generate_network_unit(self):
        result = generate_network_unit("proxy")
        assert "NetworkName=proxy" in result
        assert "Driver=bridge" in result

    def test_compose_to_quadlet(self, tmp_path):
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(yaml.dump({
            "services": {
                "web": {
                    "image": "nginx:alpine",
                    "ports": ["80:80"],
                    "networks": ["proxy"],
                },
                "app": {
                    "image": "myapp:latest",
                    "networks": ["proxy"],
                    "depends_on": ["web"],
                },
            }
        }))

        env_file = tmp_path / ".env.prod"
        env_file.write_text("TAG=v1.0\n")

        output_dir = tmp_path / "quadlet"
        compose = ComposeFile(compose_file, env_file=env_file)
        generated = compose_to_quadlet(compose, output_dir)

        # Should generate: proxy.network + web.container + app.container
        filenames = [f.name for f in generated]
        assert "proxy.network" in filenames
        assert "web.container" in filenames
        assert "app.container" in filenames

        # Verify content
        app_content = (output_dir / "app.container").read_text()
        assert "After=web.service" in app_content

    def test_compose_to_quadlet_with_filter(self, tmp_path):
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(yaml.dump({
            "services": {
                "web": {"image": "nginx"},
                "app": {"image": "myapp"},
                "db": {"image": "postgres"},
            }
        }))
        output_dir = tmp_path / "quadlet"
        compose = ComposeFile(compose_file)
        generated = compose_to_quadlet(
            compose, output_dir, services_filter=["app", "web"]
        )
        filenames = [f.name for f in generated]
        assert "app.container" in filenames
        assert "web.container" in filenames
        assert "db.container" not in filenames


# ─── CLI Tests ───────────────────────────────────────

class TestCLI:
    """Test CLI commands using click's CliRunner."""

    def test_list_command(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "name": "test-project",
            "tasks": {"hello": {"cmds": ["echo hi"], "desc": "Say hello"}},
        }))

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "list"])
        assert result.exit_code == 0
        assert "hello" in result.output

    def test_validate_command(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"build": {"cmds": ["echo build"]}},
        }))

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "validate"])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_run_with_dry_run(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"cmds": ["echo hello"]}},
        }))

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "--dry-run", "run", "hello"])
        assert result.exit_code == 0
        assert "dry run" in result.output.lower()

    def test_deploy_local_dry_run(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "name": "test",
            "environments": {
                "local": {
                    "container_runtime": "docker",
                    "compose_command": "docker compose",
                    "service_manager": "compose",
                    "env_file": ".env.local",
                }
            },
            "tasks": {},
        }))

        runner = CliRunner()
        result = runner.invoke(main, [
            "-f", str(taskfile), "--env", "local", "--dry-run", "deploy"
        ])
        assert result.exit_code == 0
        assert "local" in result.output.lower()

    def test_deploy_quadlet_dry_run(self, tmp_path):
        """Test that deploy with quadlet manager works in dry-run mode."""
        from click.testing import CliRunner
        from taskfile.cli import main

        # Create compose file
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(yaml.dump({
            "services": {
                "app": {"image": "myapp:latest", "ports": ["3000:3000"]},
            }
        }))

        # Create env file
        envfile = tmp_path / ".env.prod"
        envfile.write_text("DOMAIN=example.com\n")

        # Create Taskfile
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "name": "test-quadlet",
            "environments": {
                "local": {"service_manager": "compose"},
                "prod": {
                    "ssh_host": "example.com",
                    "ssh_user": "deploy",
                    "container_runtime": "podman",
                    "service_manager": "quadlet",
                    "compose_file": str(compose),
                    "env_file": str(envfile),
                    "quadlet_dir": str(tmp_path / "quadlet"),
                    "quadlet_remote_dir": "~/.config/containers/systemd",
                },
            },
            "tasks": {},
        }))

        runner = CliRunner()
        result = runner.invoke(main, [
            "-f", str(taskfile), "--env", "prod", "--dry-run", "deploy"
        ])
        assert result.exit_code == 0
        assert "quadlet" in result.output.lower()


# ─── Codereview.pl Example Validation ────────────────

class TestCodereviewExample:
    """Validate the codereview.pl example files parse correctly."""

    EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "codereview.pl"

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "examples" / "codereview.pl" / "Taskfile.yml").exists(),
        reason="codereview.pl example not present",
    )
    def test_taskfile_parses(self):
        config = load_taskfile(self.EXAMPLE_DIR / "Taskfile.yml")
        assert config.name == "codereview.pl"
        assert "local" in config.environments
        assert "prod" in config.environments
        assert config.environments["prod"].service_manager == "quadlet"
        assert config.environments["prod"].ssh_host is not None
        assert len(config.tasks) > 5

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "examples" / "codereview.pl" / "docker-compose.yml").exists(),
        reason="codereview.pl example not present",
    )
    def test_compose_parses_with_env_local(self):
        compose = ComposeFile(
            self.EXAMPLE_DIR / "docker-compose.yml",
            env_file=self.EXAMPLE_DIR / ".env.local",
        )
        assert "app" in compose.services
        assert "api" in compose.services
        assert "db" in compose.services
        assert "traefik" in compose.services
        assert "redis" in compose.services

        # Check Traefik labels resolved with local domain
        labels = compose.get_traefik_labels("app")
        assert "codereview.localhost" in labels.get("traefik.http.routers.app.rule", "")

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "examples" / "codereview.pl" / "docker-compose.yml").exists(),
        reason="codereview.pl example not present",
    )
    def test_compose_parses_with_env_prod(self):
        compose = ComposeFile(
            self.EXAMPLE_DIR / "docker-compose.yml",
            env_file=self.EXAMPLE_DIR / ".env.prod",
        )
        labels = compose.get_traefik_labels("app")
        assert "codereview.pl" in labels.get("traefik.http.routers.app.rule", "")

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "examples" / "codereview.pl" / "docker-compose.yml").exists(),
        reason="codereview.pl example not present",
    )
    def test_quadlet_generation_from_example(self, tmp_path):
        compose = ComposeFile(
            self.EXAMPLE_DIR / "docker-compose.yml",
            env_file=self.EXAMPLE_DIR / ".env.prod",
        )
        generated = compose_to_quadlet(compose, tmp_path / "quadlet")
        filenames = [f.name for f in generated]

        assert "app.container" in filenames
        assert "api.container" in filenames
        assert "db.container" in filenames
        assert "traefik.container" in filenames
        assert "redis.container" in filenames
        assert "proxy.network" in filenames

        # Verify prod values in generated Quadlet
        app_content = (tmp_path / "quadlet" / "app.container").read_text()
        assert "ghcr.io/softreck" in app_content
        assert "codereview.pl" in app_content
        assert "AutoUpdate=registry" in app_content
        assert "--memory=96m" in app_content


# ═══════════════════════════════════════════════════════════
#  Pipeline & CI/CD Generator Tests
# ═══════════════════════════════════════════════════════════

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


class TestCIGenerator:
    """Test CI/CD config generation."""

    @pytest.fixture
    def config(self):
        from taskfile.models import TaskfileConfig
        return TaskfileConfig.from_dict({
            "name": "testproject",
            "variables": {"REGISTRY": "ghcr.io/test"},
            "environments": {
                "local": {"container_runtime": "docker"},
                "prod": {
                    "ssh_host": "vps.example.com",
                    "ssh_user": "deploy",
                    "container_runtime": "podman",
                },
            },
            "tasks": {
                "test": {"cmds": ["pytest"], "stage": "test"},
                "build": {"cmds": ["docker build ."], "stage": "build"},
                "deploy": {"cmds": ["deploy.sh"], "env": ["prod"]},
            },
            "pipeline": {
                "stages": [
                    {"name": "test", "tasks": ["test"]},
                    {"name": "build", "tasks": ["build"], "docker_in_docker": True},
                    {"name": "deploy", "tasks": ["deploy"], "env": "prod", "when": "manual"},
                ],
                "branches": ["main"],
                "python_version": "3.11",
                "secrets": ["SSH_PRIVATE_KEY"],
            },
        })

    def test_list_targets(self):
        from taskfile.cigen import list_targets
        targets = list_targets()
        names = [t[0] for t in targets]
        assert "github" in names
        assert "gitlab" in names
        assert "gitea" in names
        assert "drone" in names
        assert "jenkins" in names
        assert "makefile" in names

    def test_generate_github(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "github", tmp_path)
        assert path.exists()
        assert path.name == "taskfile.yml"
        content = path.read_text()
        assert "actions/checkout@v4" in content
        assert "taskfile" in content
        assert "workflow_dispatch" in content
        assert "pip install taskfile" in content

    def test_generate_gitlab(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "gitlab", tmp_path)
        assert path.exists()
        content = path.read_text()
        assert "stages:" in content
        assert "docker:dind" in content
        assert "$CI_COMMIT_SHORT_SHA" in content
        assert "when: manual" in content

    def test_generate_gitea(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "gitea", tmp_path)
        assert path.exists()
        content = path.read_text()
        assert "actions/checkout@v4" in content

    def test_generate_drone(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "drone", tmp_path)
        assert path.exists()
        content = path.read_text()
        assert "kind: pipeline" in content

    def test_generate_jenkins(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "jenkins", tmp_path)
        assert path.exists()
        content = path.read_text()
        assert "pipeline {" in content
        assert "stage(" in content

    def test_generate_makefile(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "makefile", tmp_path)
        assert path.exists()
        content = path.read_text()
        assert ".PHONY:" in content
        assert "stage-test:" in content
        assert "pipeline:" in content

    def test_generate_all(self, config, tmp_path):
        from taskfile.cigen import generate_all_ci
        paths = generate_all_ci(config, tmp_path)
        assert len(paths) == 6  # all targets

    def test_generate_unknown_target(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        with pytest.raises(ValueError, match="Unknown CI target"):
            generate_ci(config, "nonexistent", tmp_path)

    def test_preview(self, config):
        from taskfile.cigen import preview_ci
        content = preview_ci(config, "github")
        assert "actions/checkout" in content
        # Preview should not create files
        assert isinstance(content, str)

    def test_github_ssh_setup_for_prod(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "github", tmp_path)
        content = path.read_text()
        assert "SSH_PRIVATE_KEY" in content
        assert "~/.ssh/id_ed25519" in content

    def test_github_dind_for_build(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "github", tmp_path)
        content = path.read_text()
        assert "REGISTRY_TOKEN" in content
        assert "docker login" in content

    def test_gitlab_branches(self, config, tmp_path):
        from taskfile.cigen import generate_ci
        path = generate_ci(config, "gitlab", tmp_path)
        content = path.read_text()
        assert "main" in content


class TestCIRunner:
    """Test local CI/CD pipeline runner."""

    @pytest.fixture
    def config(self):
        from taskfile.models import TaskfileConfig
        return TaskfileConfig.from_dict({
            "name": "testpipeline",
            "tasks": {
                "echo-test": {"cmds": ["echo test-passed"]},
                "echo-build": {"cmds": ["echo build-passed"]},
                "echo-deploy": {"cmds": ["echo deploy-passed"]},
            },
            "pipeline": {
                "stages": [
                    {"name": "test", "tasks": ["echo-test"]},
                    {"name": "build", "tasks": ["echo-build"]},
                    {"name": "deploy", "tasks": ["echo-deploy"], "when": "manual"},
                ],
            },
        })

    def test_run_full_pipeline(self, config):
        from taskfile.cirunner import PipelineRunner
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run()
        assert success
        # Manual stage should be skipped
        assert len(runner.results) == 2
        assert runner.results[0].name == "test"
        assert runner.results[1].name == "build"

    def test_run_specific_stage(self, config):
        from taskfile.cirunner import PipelineRunner
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run(stage_filter=["build"])
        assert success
        assert len(runner.results) == 1
        assert runner.results[0].name == "build"

    def test_run_manual_stage(self, config):
        from taskfile.cirunner import PipelineRunner
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run(stage_filter=["deploy"])
        assert success
        assert len(runner.results) == 1
        assert runner.results[0].name == "deploy"

    def test_skip_stage(self, config):
        from taskfile.cirunner import PipelineRunner
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run(skip_stages=["build"])
        assert success
        assert len(runner.results) == 1
        assert runner.results[0].name == "test"

    def test_stop_at(self, config):
        from taskfile.cirunner import PipelineRunner
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run(stop_at="test")
        assert success
        assert len(runner.results) == 1
        assert runner.results[0].name == "test"

    def test_empty_pipeline(self):
        from taskfile.models import TaskfileConfig
        from taskfile.cirunner import PipelineRunner
        config = TaskfileConfig.from_dict({"tasks": {"echo": {"cmds": ["echo hi"]}}})
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run()
        assert success  # empty pipeline = pass

    def test_stage_results(self, config):
        from taskfile.cirunner import PipelineRunner
        runner = PipelineRunner(config=config, dry_run=True)
        runner.run()
        for result in runner.results:
            assert result.success
            assert result.elapsed >= 0
            assert len(result.tasks) > 0

    def test_stage_env_override(self):
        from taskfile.models import TaskfileConfig
        from taskfile.cirunner import PipelineRunner
        config = TaskfileConfig.from_dict({
            "name": "test",
            "environments": {
                "local": {},
                "prod": {"ssh_host": "vps.test"},
            },
            "tasks": {
                "deploy": {"cmds": ["echo deploying"], "env": ["prod"]},
            },
            "pipeline": {
                "stages": [
                    {"name": "deploy", "tasks": ["deploy"], "env": "prod"},
                ],
            },
        })
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run()
        assert success


class TestCodereviewPipeline:
    """Test pipeline features with the codereview.pl example."""

    EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "codereview.pl"

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "examples" / "codereview.pl" / "Taskfile.yml").exists(),
        reason="codereview.pl example not present",
    )
    def test_pipeline_parses(self):
        from taskfile.parser import load_taskfile
        config = load_taskfile(self.EXAMPLE_DIR / "Taskfile.yml")
        assert len(config.pipeline.stages) == 4
        stage_names = [s.name for s in config.pipeline.stages]
        assert "test" in stage_names
        assert "deploy" in stage_names

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "examples" / "codereview.pl" / "Taskfile.yml").exists(),
        reason="codereview.pl example not present",
    )
    def test_generate_all_from_codereview(self, tmp_path):
        from taskfile.parser import load_taskfile
        from taskfile.cigen import generate_all_ci
        config = load_taskfile(self.EXAMPLE_DIR / "Taskfile.yml")
        paths = generate_all_ci(config, tmp_path)
        assert len(paths) == 6
        filenames = [p.name for p in paths]
        assert "taskfile.yml" in filenames  # github
        assert ".gitlab-ci.yml" in filenames
        assert "Makefile" in filenames
        assert "Jenkinsfile" in filenames

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "examples" / "codereview.pl" / "Taskfile.yml").exists(),
        reason="codereview.pl example not present",
    )
    def test_ci_run_dry(self):
        from taskfile.parser import load_taskfile
        from taskfile.cirunner import PipelineRunner
        config = load_taskfile(self.EXAMPLE_DIR / "Taskfile.yml")
        runner = PipelineRunner(config=config, dry_run=True)
        success = runner.run()
        assert success
        # Manual 'deploy' stage should be skipped
        stage_names = [r.name for r in runner.results]
        assert "deploy" not in stage_names
