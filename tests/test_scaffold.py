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


class TestScaffold:
    @pytest.mark.parametrize("template", ["minimal", "web", "podman", "codereview", "full", "publish"])
    def test_generate_valid_yaml(self, template):
        content = generate_taskfile(template)
        data = yaml.safe_load(content)
        assert isinstance(data, dict)
        assert "tasks" in data

    @pytest.mark.parametrize("template", ["minimal", "web", "podman", "codereview", "full", "publish"])
    def test_generated_config_parses(self, template):
        content = generate_taskfile(template)
        data = yaml.safe_load(content)
        config = TaskfileConfig.from_dict(data)
        assert len(config.tasks) > 0
        assert len(config.environments) > 0

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
