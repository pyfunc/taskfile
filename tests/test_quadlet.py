"""Tests for taskfile package."""

import pytest
import yaml
from pathlib import Path

from taskfile.models import TaskfileConfig, Task, Environment
from taskfile.parser import load_taskfile, validate_taskfile, TaskfileNotFoundError
from taskfile.runner import TaskfileRunner
from taskfile.scaffold import generate_taskfile
from taskfile.compose import ComposeFile, load_env_file, resolve_variables
from taskfile.quadlet import (
    generate_container_unit,
    compose_to_quadlet,
    generate_network_unit,
    ServiceConfig,
    _build_unit_section,
    _build_container_section,
)


# ─── Model Tests ─────────────────────────────────────


class TestServiceConfig:
    """Tests for ServiceConfig TypedDict."""

    def test_service_config_creation(self):
        """Test creating ServiceConfig TypedDict."""
        service: ServiceConfig = {
            "image": "nginx:latest",
            "container_name": "web",
            "ports": ["80:80", "443:443"],
            "environment": {"NODE_ENV": "production"},
            "volumes": ["./data:/data"],
            "networks": ["proxy"],
            "labels": {"traefik.enable": "true"},
            "restart": "always",
        }

        assert service["image"] == "nginx:latest"
        assert service["ports"] == ["80:80", "443:443"]
        assert service["restart"] == "always"

    def test_service_config_with_list_environment(self):
        """Test ServiceConfig with environment as list."""
        service: ServiceConfig = {
            "image": "app:latest",
            "environment": ["KEY1=value1", "KEY2=value2"],
        }

        assert isinstance(service["environment"], list)
        assert "KEY1=value1" in service["environment"]

    def test_service_config_optional_fields(self):
        """Test ServiceConfig with minimal fields."""
        service: ServiceConfig = {
            "image": "minimal:latest",
        }

        # Optional fields should not be required
        assert "image" in service
        assert "ports" not in service
        assert "environment" not in service

    def test_service_config_with_deploy(self):
        """Test ServiceConfig with deploy resources."""
        service: ServiceConfig = {
            "image": "app:latest",
            "deploy": {
                "resources": {
                    "limits": {
                        "memory": "128m",
                        "cpus": "0.5",
                    }
                }
            },
        }

        assert service["deploy"]["resources"]["limits"]["memory"] == "128m"
        assert service["deploy"]["resources"]["limits"]["cpus"] == "0.5"

    def test_build_unit_section_with_service_config(self):
        """Test _build_unit_section accepts ServiceConfig."""
        service: ServiceConfig = {
            "image": "test:latest",
            "depends_on": ["db", "redis"],
        }

        result = _build_unit_section("app", service)

        assert "[Unit]" in result
        assert "After=db.service" in result
        assert "Requires=db.service" in result
        assert "After=redis.service" in result

    def test_build_container_section_with_service_config(self):
        """Test _build_container_section accepts ServiceConfig."""
        service: ServiceConfig = {
            "image": "nginx:alpine",
            "container_name": "web",
            "ports": ["80:80"],
            "environment": {"ENV": "prod"},
            "networks": ["proxy"],
            "restart": "unless-stopped",
        }

        result = _build_container_section("web", service, "proxy", auto_update=True)

        # Check all sections are present
        assert "\\n[Container]" in result
        assert "Image=nginx:alpine" in result
        assert "ContainerName=web" in result
        assert "AutoUpdate=registry" in result
        assert "PublishPort=80:80" in result
        assert "Environment=ENV=prod" in result
        assert "Network=proxy.network" in result


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
