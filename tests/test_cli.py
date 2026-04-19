"""Tests for taskfile package."""

import yaml


# ─── Model Tests ─────────────────────────────────────


class TestCLI:
    """Test CLI commands using click's CliRunner."""

    def test_list_command(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "name": "test-project",
                    "tasks": {"hello": {"cmds": ["echo hi"], "desc": "Say hello"}},
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "list"])
        if result.exit_code != 0:
            print(result.output)
            print(result.exception)
        assert result.exit_code == 0
        assert "hello" in result.output

    def test_validate_command(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "tasks": {"build": {"cmds": ["echo build"]}},
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "validate"])
        if result.exit_code != 0:
            print(result.output)
            print(result.exception)
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_run_with_dry_run(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            yaml.dump(
                {
                    "version": "1",
                    "tasks": {"hello": {"cmds": ["echo hello"]}},
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "--dry-run", "run", "hello"])
        if result.exit_code != 0:
            print(result.output)
            print(result.exception)
        assert result.exit_code == 0
        assert "dry run" in result.output.lower()

    def test_deploy_local_dry_run(self, tmp_path):
        from click.testing import CliRunner
        from taskfile.cli import main

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            yaml.dump(
                {
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
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "--env", "local", "--dry-run", "deploy"])
        if result.exit_code != 0:
            print(result.output)
            print(result.exception)
        assert result.exit_code == 0
        assert "local" in result.output.lower()

    def test_deploy_quadlet_dry_run(self, tmp_path):
        """Test that deploy with quadlet manager works in dry-run mode."""
        from click.testing import CliRunner
        from taskfile.cli import main

        # Create compose file
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {"image": "myapp:latest", "ports": ["3000:3000"]},
                    }
                }
            )
        )

        # Create env file
        envfile = tmp_path / ".env.prod"
        envfile.write_text("DOMAIN=example.com\n")

        # Create Taskfile
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            yaml.dump(
                {
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
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(main, ["-f", str(taskfile), "--env", "prod", "--dry-run", "deploy"])
        if result.exit_code != 0:
            print(result.output)
            print(result.exception)
        assert result.exit_code == 0
        assert "quadlet" in result.output.lower()
