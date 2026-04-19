"""Tests for taskfile package."""

import yaml

from taskfile.compose import ComposeFile


# ─── Model Tests ─────────────────────────────────────


class TestComposeFile:
    def test_load_compose(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(
            yaml.dump(
                {
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
                }
            )
        )

        envfile = tmp_path / ".env.test"
        envfile.write_text("DOMAIN=example.com\n")

        cf = ComposeFile(compose, env_file=envfile)
        assert "app" in cf.services
        labels = cf.get_traefik_labels("app")
        assert "traefik.http.routers.app.rule" in labels
        assert "example.com" in labels["traefik.http.routers.app.rule"]

    def test_service_names(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "web": {"image": "nginx"},
                        "db": {"image": "postgres"},
                        "redis": {"image": "redis"},
                    }
                }
            )
        )
        cf = ComposeFile(compose)
        assert sorted(cf.service_names()) == ["db", "redis", "web"]
