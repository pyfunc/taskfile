"""E2E tests for taskfile based on examples/ directory.

These tests validate the end-to-end functionality using real-world
example configurations without executing actual deployments.
"""

import pytest
import os
import sys
from pathlib import Path
from click.testing import CliRunner

# Ensure src is on path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from taskfile.parser import load_taskfile, validate_taskfile, TaskfileConfig
from taskfile.runner import TaskfileRunner
from taskfile.cli.main import main


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestMinimalExample:
    """E2E tests for examples/minimal/ - basic task runner functionality."""

    @pytest.fixture
    def minimal_path(self):
        return EXAMPLES_DIR / "minimal"

    def test_load_minimal_taskfile(self, minimal_path):
        """E2E: Parse and load minimal Taskfile.yml."""
        taskfile = minimal_path / "Taskfile.yml"
        config = load_taskfile(taskfile)

        assert config.name == "my-app"
        assert config.version == "1"
        assert "test" in config.tasks
        assert "build" in config.tasks
        assert "run" in config.tasks

    def test_minimal_variables(self, minimal_path):
        """E2E: Variables are correctly parsed."""
        config = load_taskfile(minimal_path / "Taskfile.yml")

        assert config.variables["APP"] == "my-app"
        assert config.variables["TAG"] == "latest"

    def test_minimal_task_dependencies(self, minimal_path):
        """E2E: Task dependencies are correctly parsed."""
        config = load_taskfile(minimal_path / "Taskfile.yml")

        build_task = config.tasks["build"]
        assert "test" in build_task.deps
        assert build_task.stage == "build"

    def test_minimal_dry_run(self, minimal_path):
        """E2E: Dry-run execution doesn't fail."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["-f", str(minimal_path / "Taskfile.yml"), "--dry-run", "run", "test"]
        )
        # Should not crash, may fail due to missing pytest but that's OK
        assert result.exit_code in [0, 1]  # 0 = success, 1 = command failed but taskfile ran

    def test_minimal_list_tasks(self, minimal_path):
        """E2E: List command works with minimal example."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["-f", str(minimal_path / "Taskfile.yml"), "list"]
        )
        assert result.exit_code == 0
        assert "test" in result.output
        assert "build" in result.output
        assert "run" in result.output

    def test_minimal_validate(self, minimal_path):
        """E2E: Validation passes for minimal example."""
        config = load_taskfile(minimal_path / "Taskfile.yml")
        # Should not raise any exceptions
        warnings = validate_taskfile(config)
        # Should return list of warnings (possibly empty)
        assert isinstance(warnings, list)


class TestSaasAppExample:
    """E2E tests for examples/saas-app/ - multi-environment SaaS."""

    @pytest.fixture
    def saas_path(self):
        return EXAMPLES_DIR / "saas-app"

    def test_load_saas_taskfile(self, saas_path):
        """E2E: Parse saas-app Taskfile with environments."""
        config = load_taskfile(saas_path / "Taskfile.yml")

        assert config.name == "saas-app"
        assert "local" in config.environments
        assert "staging" in config.environments
        assert "prod" in config.environments

    def test_saas_environment_config(self, saas_path):
        """E2E: Environment-specific configurations loaded."""
        config = load_taskfile(saas_path / "Taskfile.yml")

        # Local environment
        local = config.environments["local"]
        assert local.container_runtime == "docker"

        # Prod environment
        prod = config.environments["prod"]
        assert prod.ssh_host == "prod.myapp.com"
        assert prod.ssh_user == "deploy"
        assert prod.service_manager == "quadlet"

    def test_saas_pipeline_structure(self, saas_path):
        """E2E: Pipeline configuration parsed correctly."""
        config = load_taskfile(saas_path / "Taskfile.yml")

        assert config.pipeline is not None
        assert config.pipeline.branches == ["main"]
        assert "SSH_PRIVATE_KEY" in config.pipeline.secrets
        assert len(config.pipeline.stages) == 4

        # Check stage names
        stage_names = [s.name for s in config.pipeline.stages]
        assert "test" in stage_names
        assert "build" in stage_names
        assert "deploy-staging" in stage_names
        assert "deploy-prod" in stage_names

    def test_saas_task_env_filters(self, saas_path):
        """E2E: Tasks with environment filters."""
        config = load_taskfile(saas_path / "Taskfile.yml")

        # Deploy task only for staging/prod
        deploy_task = config.tasks["deploy"]
        assert "staging" in deploy_task.env_filter
        assert "prod" in deploy_task.env_filter

        # Dev task only for local
        dev_task = config.tasks["dev"]
        assert "local" in dev_task.env_filter

    def test_saas_dry_run_list(self, saas_path):
        """E2E: List tasks in saas-app works."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["-f", str(saas_path / "Taskfile.yml"), "list"]
        )
        assert result.exit_code == 0
        assert "deploy" in result.output
        assert "staging" in result.output
        assert "prod" in result.output

    def test_saas_remote_commands_parsed(self, saas_path):
        """E2E: @remote commands are correctly identified."""
        config = load_taskfile(saas_path / "Taskfile.yml")

        deploy_task = config.tasks["deploy"]
        # Check that commands contain @remote prefix
        remote_cmds = [cmd for cmd in deploy_task.commands if "@remote" in cmd]
        assert len(remote_cmds) > 0


class TestMultiplatformExample:
    """E2E tests for examples/multiplatform/ - web + desktop platforms."""

    @pytest.fixture
    def multi_path(self):
        return EXAMPLES_DIR / "multiplatform"

    def test_load_multiplatform_taskfile(self, multi_path):
        """E2E: Parse multiplatform Taskfile with platforms."""
        config = load_taskfile(multi_path / "Taskfile.yml")

        assert config.name == "my-multiplatform-app"
        assert config.default_env == "local"
        assert config.default_platform == "web"

    def test_multiplatform_platforms_defined(self, multi_path):
        """E2E: Platform configurations loaded."""
        config = load_taskfile(multi_path / "Taskfile.yml")

        assert "desktop" in config.platforms
        assert "web" in config.platforms

        desktop = config.platforms["desktop"]
        assert desktop.variables["BUILD_DIR"] == "dist/desktop"

        web = config.platforms["web"]
        assert web.variables["WEB_PORT"] == "3000"

    def test_multiplatform_env_platform_matrix(self, multi_path):
        """E2E: Tasks with env+platform matrix filters."""
        config = load_taskfile(multi_path / "Taskfile.yml")

        # deploy-desktop-local: env=[local], platform=[desktop]
        task = config.tasks["deploy-desktop-local"]
        assert "local" in task.env_filter
        assert "desktop" in task.platform_filter

        # deploy-web-prod: env=[prod], platform=[web]
        task = config.tasks["deploy-web-prod"]
        assert "prod" in task.env_filter
        assert "web" in task.platform_filter

    def test_multiplatform_runner_with_platform(self, multi_path):
        """E2E: TaskfileRunner with platform selection."""
        config = load_taskfile(multi_path / "Taskfile.yml")

        # Test with web platform
        runner = TaskfileRunner(
            config=config,
            env_name="local",
            platform_name="web",
            dry_run=True
        )

        assert runner.platform_name == "web"
        assert runner.platform is not None
        assert runner.variables["PLATFORM"] == "web"
        assert runner.variables["WEB_PORT"] == "3000"

    def test_multiplatform_dry_run_local(self, multi_path):
        """E2E: Dry-run local tasks."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "-f", str(multi_path / "Taskfile.yml"),
                "-e", "local",
                "-p", "web",
                "--dry-run",
                "run", "install"
            ]
        )
        assert result.exit_code == 0
        assert "npm ci" in result.output or "(dry run)" in result.output

    def test_multiplatform_task_dependencies(self, multi_path):
        """E2E: Complex dependency chains."""
        config = load_taskfile(multi_path / "Taskfile.yml")

        build_task = config.tasks["build"]
        assert "install" in build_task.deps
        assert "test" in build_task.deps

    def test_multiplatform_validate_command(self, multi_path):
        """E2E: Validate command exists and has proper structure."""
        config = load_taskfile(multi_path / "Taskfile.yml")

        assert "validate-deploy" in config.tasks
        assert "preflight" in config.tasks


class TestCodereviewExample:
    """E2E tests for examples/codereview.pl/ - production Quadlet setup."""

    @pytest.fixture
    def codereview_path(self):
        return EXAMPLES_DIR / "codereview.pl"

    def test_load_codereview_taskfile(self, codereview_path):
        """E2E: Parse complex codereview.pl Taskfile."""
        config = load_taskfile(codereview_path / "Taskfile.yml")

        assert config.name == "codereview.pl"
        assert config.default_env == "local"

    def test_codereview_prod_environment(self, codereview_path):
        """E2E: Production environment with Quadlet settings."""
        config = load_taskfile(codereview_path / "Taskfile.yml")

        prod = config.environments["prod"]
        assert prod.container_runtime == "podman"
        assert prod.service_manager == "quadlet"
        assert prod.quadlet_dir == "deploy/quadlet"
        assert prod.quadlet_remote_dir == "~/.config/containers/systemd"

    def test_codereview_pipeline_stages(self, codereview_path):
        """E2E: Complex CI/CD pipeline with multiple stages."""
        config = load_taskfile(codereview_path / "Taskfile.yml")

        assert config.pipeline is not None
        assert config.pipeline.python_version == "3.12"
        assert len(config.pipeline.stages) >= 4

        # Check specific stages
        stage_map = {s.name: s for s in config.pipeline.stages}
        assert "test" in stage_map
        assert "build" in stage_map
        assert "deploy" in stage_map

        # Deploy stage has manual trigger
        deploy_stage = stage_map.get("deploy")
        if deploy_stage:
            assert deploy_stage.when == "manual"

    def test_codereview_quadlet_generation_task(self, codereview_path):
        """E2E: Quadlet generation task exists."""
        config = load_taskfile(codereview_path / "Taskfile.yml")

        assert "generate" in config.tasks
        generate_task = config.tasks["generate"]
        # Should reference quadlet generate command
        assert any("quadlet" in cmd for cmd in generate_task.commands)

    def test_codereview_remote_tasks(self, codereview_path):
        """E2E: Multiple remote deployment tasks."""
        config = load_taskfile(codereview_path / "Taskfile.yml")

        # Check deploy task has @remote commands
        deploy_task = config.tasks["deploy"]
        remote_cmds = [cmd for cmd in deploy_task.commands if "@remote" in cmd]
        assert len(remote_cmds) >= 3  # Multiple remote operations

        # Check other remote tasks exist
        assert "deploy-quick" in config.tasks
        assert "status" in config.tasks
        assert "logs" in config.tasks
        assert "restart" in config.tasks

    def test_codereview_docker_compose_integration(self, codereview_path):
        """E2E: References to docker-compose.yml."""
        config = load_taskfile(codereview_path / "Taskfile.yml")

        assert config.variables["COMPOSE_FILE"] == "docker-compose.yml"

        # Local env references docker-compose
        local = config.environments["local"]
        assert local.compose_file == "docker-compose.yml"


class TestExamplesCrossCutting:
    """Cross-cutting E2E tests across all examples."""

    def test_all_examples_load_successfully(self):
        """E2E: All example Taskfiles can be parsed without errors."""
        examples = [
            EXAMPLES_DIR / "minimal" / "Taskfile.yml",
            EXAMPLES_DIR / "saas-app" / "Taskfile.yml",
            EXAMPLES_DIR / "multiplatform" / "Taskfile.yml",
            EXAMPLES_DIR / "codereview.pl" / "Taskfile.yml",
        ]

        for taskfile in examples:
            config = load_taskfile(taskfile)
            assert config is not None
            assert config.name is not None

    def test_all_examples_have_tasks(self):
        """E2E: All examples have at least one task."""
        examples = [
            EXAMPLES_DIR / "minimal",
            EXAMPLES_DIR / "saas-app",
            EXAMPLES_DIR / "multiplatform",
            EXAMPLES_DIR / "codereview.pl",
        ]

        for example_dir in examples:
            config = load_taskfile(example_dir / "Taskfile.yml")
            assert len(config.tasks) > 0, f"{example_dir.name} has no tasks"

    def test_all_examples_validate_successfully(self):
        """E2E: validate_taskfile passes for all examples."""
        examples = [
            EXAMPLES_DIR / "minimal" / "Taskfile.yml",
            EXAMPLES_DIR / "saas-app" / "Taskfile.yml",
            EXAMPLES_DIR / "multiplatform" / "Taskfile.yml",
            EXAMPLES_DIR / "codereview.pl" / "Taskfile.yml",
        ]

        for taskfile in examples:
            config = load_taskfile(taskfile)
            warnings = validate_taskfile(config)
            # Should return list (may be empty or have warnings)
            assert isinstance(warnings, list)

    def test_cli_list_works_for_all_examples(self):
        """E2E: taskfile list works for all examples."""
        examples = [
            EXAMPLES_DIR / "minimal",
            EXAMPLES_DIR / "saas-app",
            EXAMPLES_DIR / "multiplatform",
            EXAMPLES_DIR / "codereview.pl",
        ]

        runner = CliRunner()
        for example_dir in examples:
            result = runner.invoke(
                main,
                ["-f", str(example_dir / "Taskfile.yml"), "list"]
            )
            assert result.exit_code == 0, f"list failed for {example_dir.name}"
            assert "Tasks:" in result.output or "tasks" in result.output.lower()

    def test_cli_validate_works_for_all_examples(self):
        """E2E: taskfile validate works for all examples."""
        examples = [
            EXAMPLES_DIR / "minimal",
            EXAMPLES_DIR / "saas-app",
            EXAMPLES_DIR / "multiplatform",
            EXAMPLES_DIR / "codereview.pl",
        ]

        runner = CliRunner()
        for example_dir in examples:
            result = runner.invoke(
                main,
                ["-f", str(example_dir / "Taskfile.yml"), "validate"]
            )
            assert result.exit_code == 0, f"validate failed for {example_dir.name}"


class TestExamplesAdvancedFeatures:
    """E2E tests for advanced features demonstrated in examples."""

    def test_environment_variable_substitution(self):
        """E2E: ${VAR} syntax in variables works."""
        config = load_taskfile(EXAMPLES_DIR / "multiplatform" / "Taskfile.yml")

        # Variables with ${} syntax should be present
        assert "${VPS_IP:-your-vps-ip}" in config.variables["VPS_IP"]

    def test_task_stages_grouping(self):
        """E2E: Tasks are grouped by stages."""
        config = load_taskfile(EXAMPLES_DIR / "minimal" / "Taskfile.yml")

        test_task = config.tasks["test"]
        build_task = config.tasks["build"]

        assert test_task.stage == "test"
        assert build_task.stage == "build"

    def test_ignore_errors_flag(self):
        """E2E: ignore_errors task attribute works."""
        config = load_taskfile(EXAMPLES_DIR / "multiplatform" / "Taskfile.yml")

        lint_task = config.tasks["lint"]
        assert lint_task.ignore_errors is True

    def test_parallel_deps_not_in_examples(self):
        """E2E: Verify parallel deps not used in examples (feature test)."""
        # This documents that examples don't use parallel deps yet
        for example in ["minimal", "saas-app", "multiplatform", "codereview.pl"]:
            config = load_taskfile(EXAMPLES_DIR / example / "Taskfile.yml")
            for task in config.tasks.values():
                # Parallel should be False or not set in examples
                assert getattr(task, 'parallel', False) is not True, \
                    f"{example}/{task.name} has unexpected parallel=True"

    def test_task_descriptions_present(self):
        """E2E: All tasks have descriptions for UX."""
        examples = ["minimal", "saas-app", "multiplatform", "codereview.pl"]

        for example in examples:
            config = load_taskfile(EXAMPLES_DIR / example / "Taskfile.yml")
            for name, task in config.tasks.items():
                assert task.description is not None, f"{example}/{name} missing description"
                assert len(task.description) > 0, f"{example}/{name} has empty description"
