"""Tests for landing page generator."""

import pytest
from pathlib import Path

from taskfile.landing import (
    generate_landing_page,
    build_landing_page,
    create_landing_nginx_config,
    create_landing_compose_service,
    LANDING_TEMPLATE,
)


class TestGenerateLandingPage:
    """Tests for landing page HTML generation."""

    def test_basic_generation(self):
        """Test basic landing page generation."""
        html = generate_landing_page(
            app_name="MyApp",
            tag="v1.0.0",
            domain="example.com",
        )

        assert "MyApp" in html
        assert "v1.0.0" in html
        assert "example.com" in html
        assert "<!DOCTYPE html>" in html
        assert "Desktop Downloads" in html

    def test_download_links(self):
        """Test that download links are generated correctly."""
        html = generate_landing_page(
            app_name="TestApp",
            tag="v2.1.0",
            domain="test.com",
        )

        # Check Windows download link
        assert "/releases/v2.1.0/TestApp-v2.1.0.exe" in html
        # Check macOS download link
        assert "/releases/v2.1.0/TestApp-v2.1.0.dmg" in html
        # Check Linux download link
        assert "/releases/v2.1.0/TestApp-v2.1.0.AppImage" in html

    def test_web_app_link(self):
        """Test web application link generation."""
        html = generate_landing_page(
            app_name="MyApp",
            tag="v1.0.0",
            domain="example.com",
        )

        assert "https://app.example.com" in html
        assert "Open Web App" in html

    def test_custom_github_repo(self):
        """Test custom GitHub repository in footer."""
        html = generate_landing_page(
            app_name="MyApp",
            tag="v1.0.0",
            domain="example.com",
            github_repo="user/repo",
        )

        assert "github.com/user/repo" in html

    def test_default_github_repo(self):
        """Test default GitHub repository generation."""
        html = generate_landing_page(
            app_name="MyApp",
            tag="v1.0.0",
            domain="example.com",
        )

        # Should use lowercase app name as default
        assert "github.com/myapp/myapp" in html

    def test_release_date_and_year(self):
        """Test release date and year placeholders."""
        html = generate_landing_page(
            app_name="MyApp",
            tag="v1.0.0",
            domain="example.com",
            release_date="2026-03-05",
            year="2026",
        )

        assert "Released 2026-03-05" in html
        assert "© 2026 MyApp" in html


class TestBuildLandingPage:
    """Tests for landing page file creation."""

    def test_build_creates_directory(self, tmp_path):
        """Test that build creates output directory if needed."""
        output_dir = tmp_path / "landing_output"

        build_landing_page(
            output_dir=output_dir,
            app_name="TestApp",
            tag="v1.0.0",
            domain="test.com",
        )

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_build_creates_index_html(self, tmp_path):
        """Test that build creates index.html file."""
        output_dir = tmp_path / "landing"

        result = build_landing_page(
            output_dir=output_dir,
            app_name="TestApp",
            tag="v1.0.0",
            domain="test.com",
        )

        assert result.exists()
        assert result.name == "index.html"
        content = result.read_text()
        assert "TestApp" in content

    def test_build_overwrites_existing(self, tmp_path):
        """Test that build overwrites existing file."""
        output_dir = tmp_path / "landing"
        output_dir.mkdir()
        existing_file = output_dir / "index.html"
        existing_file.write_text("OLD CONTENT")

        build_landing_page(
            output_dir=output_dir,
            app_name="NewApp",
            tag="v2.0.0",
            domain="new.com",
        )

        content = existing_file.read_text()
        assert "NewApp" in content
        assert "v2.0.0" in content


class TestCreateLandingNginxConfig:
    """Tests for nginx configuration generation."""

    def test_basic_config(self):
        """Test basic nginx config generation."""
        config = create_landing_nginx_config(
            domain="example.com",
            landing_dir="/var/www/landing",
            releases_dir="/var/www/releases",
        )

        assert "server_name example.com" in config
        assert "root /var/www/landing" in config
        assert "alias /var/www/releases/" in config
        assert "location /releases/" in config

    def test_listening_directive(self):
        """Test that listening directive is included."""
        config = create_landing_nginx_config(
            domain="example.com",
            landing_dir="/var/www/landing",
            releases_dir="/var/www/releases",
        )

        assert "listen 80" in config


class TestCreateLandingComposeService:
    """Tests for docker-compose service generation."""

    def test_basic_service(self):
        """Test basic compose service generation."""
        service = create_landing_compose_service(
            domain="example.com",
            landing_port=8080,
            traefik_enabled=False,
        )

        assert service["image"] == "nginx:alpine"
        assert service["container_name"] == "landing"
        assert service["restart"] == "unless-stopped"
        assert "8080:80" in service["ports"]

    def test_volumes_mounting(self):
        """Test that volumes are correctly mounted."""
        service = create_landing_compose_service(
            domain="example.com",
        )

        volumes = service["volumes"]
        assert any("./dist/landing:/usr/share/nginx/html:ro" in v for v in volumes)
        assert any("./dist/releases:/usr/share/nginx/html/releases:ro" in v for v in volumes)

    def test_traefik_labels_enabled(self):
        """Test Traefik labels when enabled."""
        service = create_landing_compose_service(
            domain="example.com",
            traefik_enabled=True,
        )

        labels = service["labels"]
        assert labels["traefik.enable"] == "true"
        assert "Host(`example.com`)" in labels["traefik.http.routers.landing.rule"]
        assert labels["traefik.http.routers.landing.tls"] == "${TLS_ENABLED:-false}"

    def test_traefik_labels_disabled(self):
        """Test that Traefik labels are absent when disabled."""
        service = create_landing_compose_service(
            domain="example.com",
            traefik_enabled=False,
        )

        assert "labels" not in service


class TestLandingTemplate:
    """Tests for the landing page template itself."""

    def test_template_contains_placeholders(self):
        """Test that template has all required placeholders."""
        required_placeholders = [
            "{{APP_NAME}}",
            "{{TAG}}",
            "{{DOMAIN}}",
            "{{RELEASE_DATE}}",
            "{{YEAR}}",
            "{{GITHUB_REPO}}",
        ]

        for placeholder in required_placeholders:
            assert placeholder in LANDING_TEMPLATE

    def test_template_is_valid_html(self):
        """Test that template produces valid HTML structure."""
        html = generate_landing_page(
            app_name="Test",
            tag="v1.0.0",
            domain="test.com",
        )

        # Basic HTML structure checks
        assert html.startswith("<!DOCTYPE html>")
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html
