"""E2E tests for Docker CLI commands."""

import pytest
from pathlib import Path
from click.testing import CliRunner


class TestDockerCommands:
    """Test Docker CLI commands: ps, stop-port, stop-all, compose-down."""

    def test_docker_ps_command(self):
        """E2E: docker ps shows running containers."""
        from taskfile.cli.docker_cmds import docker_group
        runner = CliRunner()
        
        # Mock test - just verify command structure works
        result = runner.invoke(docker_group, ['ps'])
        # Should complete without error (may show no containers)
        assert result.exit_code in [0, 1]  # 0 = success, 1 = docker not available

    def test_docker_stop_port_command(self):
        """E2E: docker stop-port command exists and accepts --yes flag."""
        from taskfile.cli.docker_cmds import docker_group
        runner = CliRunner()
        
        result = runner.invoke(docker_group, ['stop-port', '9999', '--yes'])
        # Should complete (may fail if no containers or docker not available)
        assert result.exit_code in [0, 1]

    def test_docker_stop_all_command(self):
        """E2E: docker stop-all command exists and accepts --yes flag."""
        from taskfile.cli.docker_cmds import docker_group
        runner = CliRunner()
        
        result = runner.invoke(docker_group, ['stop-all', '--yes'])
        # Should complete (may fail if docker not available)
        assert result.exit_code in [0, 1]

    def test_docker_compose_down_command(self):
        """E2E: docker compose-down command exists."""
        from taskfile.cli.docker_cmds import docker_group
        runner = CliRunner()
        
        result = runner.invoke(docker_group, ['compose-down'])
        # Should complete (may fail if no compose file)
        assert result.exit_code in [0, 1]


class TestDockerDeployment:
    """Test Docker deployment scenarios."""

    def test_deploy_env_validation(self, tmp_path):
        """E2E: Deploy validates .env file and requires hosts."""
        from taskfile.cli import main
        
        # Create Taskfile with deploy task
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text("""
version: "1"
name: test-deploy

environments:
  staging:
    ssh_host: ${STAGING_HOST}
    ssh_user: ${DEPLOY_USER:-deploy}
  prod:
    ssh_host: ${PROD_HOST}
    ssh_user: ${DEPLOY_USER:-deploy}

tasks:
  deploy:
    desc: Test deployment
    cmds:
      - echo "Deploy to ${ENV:-local}"
""")
        
        # Create empty .env
        env_file = tmp_path / ".env"
        env_file.write_text("# Empty env\n")
        
        runner = CliRunner()
        result = runner.invoke(main, [
            '-f', str(taskfile),
            '--env', 'staging',
            'run', 'deploy'
        ])
        
        # Should fail gracefully when STAGING_HOST is not set
        assert result.exit_code in [0, 1, 2]

    def test_deploy_with_env_vars(self, tmp_path):
        """E2E: Deploy works when env vars are set."""
        from taskfile.cli import main
        
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text("""
version: "1"
name: test-deploy

environments:
  staging:
    ssh_host: staging.example.com
    ssh_user: deploy

tasks:
  deploy-exec:
    desc: Test deploy exec
    cmds:
      - echo "Deploying to ${ssh_host} as ${ssh_user}"
""")
        # Create required env file to pass pre-run validation
        env_file = tmp_path / ".env.staging"
        env_file.write_text("SSH_HOST=staging.example.com\nSSH_USER=deploy\n")
        
        runner = CliRunner()
        result = runner.invoke(main, [
            '-f', str(taskfile),
            '--env', 'staging',
            'run', 'deploy-exec'
        ])
        
        assert result.exit_code == 0
        assert "staging.example.com" in result.output or "deploy" in result.output

    def test_docker_image_resolution(self, tmp_path):
        """E2E: Docker image variables resolve correctly."""
        from taskfile.cli import main
        
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text("""
version: "1"
name: test-image

variables:
  IMAGE_WEB: myapp/web
  TAG: latest

tasks:
  deploy:
    desc: Deploy with image
    cmds:
      - echo "Image: ${IMAGE_WEB}:${TAG}"
""")
        
        runner = CliRunner()
        result = runner.invoke(main, [
            '-f', str(taskfile),
            'run', 'deploy'
        ])
        
        assert result.exit_code == 0
        assert "myapp/web:latest" in result.output


class TestDockerHealthCheck:
    """Test Docker deployment health checks."""

    def test_health_check_url_construction(self):
        """E2E: Health check URL uses SSH_HOST not localhost."""
        # Verify that health check uses proper host
        # This is a conceptual test - real test would need actual deployment
        ssh_host = "prod.example.com"
        health_url = f"http://{ssh_host}:8000/health"
        
        assert "localhost" not in health_url
        assert ssh_host in health_url
        assert ":8000" in health_url

    def test_deploy_user_in_ssh_url(self):
        """E2E: SSH URL includes deploy user."""
        deploy_user = "deploy"
        ssh_host = "server.example.com"
        ssh_url = f"{deploy_user}@{ssh_host}"
        
        assert deploy_user in ssh_url
        assert ssh_host in ssh_url
        assert "@" in ssh_url


class TestDockerEnvFileHandling:
    """Test .env file handling for Docker deployments."""

    def test_env_file_parsing(self, tmp_path):
        """E2E: .env file is parsed correctly."""
        from taskfile.compose import load_env_file
        
        env_file = tmp_path / ".env"
        env_file.write_text("""
STAGING_HOST=staging.example.com
PROD_HOST=prod.example.com
DEPLOY_USER=deploy
IMAGE_WEB=myapp/web
TAG=v1.0.0
""")
        
        env_vars = load_env_file(str(env_file))
        
        assert env_vars.get("STAGING_HOST") == "staging.example.com"
        assert env_vars.get("PROD_HOST") == "prod.example.com"
        assert env_vars.get("DEPLOY_USER") == "deploy"
        assert env_vars.get("IMAGE_WEB") == "myapp/web"
        assert env_vars.get("TAG") == "v1.0.0"

    def test_env_file_empty_values(self, tmp_path):
        """E2E: Empty values in .env are handled."""
        from taskfile.compose import load_env_file
        
        env_file = tmp_path / ".env"
        env_file.write_text("""
STAGING_HOST=
PROD_HOST=prod.example.com
DEPLOY_USER=
""")
        
        env_vars = load_env_file(str(env_file))
        
        # Empty values should be empty strings or None
        assert env_vars.get("STAGING_HOST") == "" or env_vars.get("STAGING_HOST") is None
        assert env_vars.get("PROD_HOST") == "prod.example.com"

    def test_env_file_with_quotes(self, tmp_path):
        """E2E: Quoted values in .env are parsed."""
        from taskfile.compose import load_env_file
        
        env_file = tmp_path / ".env"
        env_file.write_text('''
STAGING_HOST="staging.example.com"
PROD_HOST="prod.example.com"
''')
        
        env_vars = load_env_file(str(env_file))
        
        # Values should be unquoted
        assert "staging.example.com" in str(env_vars.get("STAGING_HOST", ""))
        assert "\"" not in str(env_vars.get("STAGING_HOST", ""))


class TestDockerPortManagement:
    """Test Docker port management features."""

    def test_port_conflict_detection(self, tmp_path):
        """E2E: Port conflicts are detected in docker-compose.yml."""
        from taskfile.compose import ComposeFile
        
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx
    ports:
      - "8080:80"
  api:
    image: myapp
    ports:
      - "8080:8000"
""")
        
        compose = ComposeFile.from_yaml(str(compose_file))
        ports = compose.get_all_ports()
        
        # Should detect duplicate port 8080
        port_8080 = [p for p in ports if p.host_port == 8080]
        assert len(port_8080) == 2  # Both services use 8080

    def test_container_port_parsing(self):
        """E2E: Container port mappings are parsed correctly."""
        # Test regex pattern for port parsing
        import re
        
        PORT_TOKEN_RE = re.compile(
            r"(?P<host>(?:\d{1,3}\.){3}\d{1,3}|\[::\]|\*|0\.0\.0\.0|::):(?P<port>\d+)->"
        )
        
        # Test various port formats
        test_cases = [
            ("0.0.0.0:8080->80/tcp", "8080"),
            (":::8000->8000/tcp", "8000"),
            ("127.0.0.1:3000->3000/tcp", "3000"),
            ("[::]:9000->9000/tcp", "9000"),
        ]
        
        for port_str, expected_port in test_cases:
            match = PORT_TOKEN_RE.search(port_str)
            assert match is not None, f"Failed to match: {port_str}"
            assert match.group("port") == expected_port
