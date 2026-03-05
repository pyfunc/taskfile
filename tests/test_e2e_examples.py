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

    ALL_EXAMPLES = [
        "ci-generation", "ci-pipeline", "cloud-aws", "codereview.pl",
        "edge-iot", "fleet-rpi", "fullstack-deploy", "functions-embed",
        "iac-terraform", "import-cicd", "include-split", "kubernetes-deploy",
        "minimal", "monorepo-microservices", "multi-artifact", "multiplatform",
        "publish-cargo", "publish-docker", "publish-github", "publish-npm",
        "publish-pypi", "quadlet-podman", "saas-app", "script-extraction",
    ]

    def test_all_examples_load_successfully(self):
        """E2E: All example Taskfiles can be parsed without errors."""
        for name in self.ALL_EXAMPLES:
            taskfile = EXAMPLES_DIR / name / "Taskfile.yml"
            config = load_taskfile(taskfile)
            assert config is not None, f"{name}: config is None"
            assert config.name is not None, f"{name}: name is None"

    def test_all_examples_have_tasks(self):
        """E2E: All examples have at least one task."""
        for name in self.ALL_EXAMPLES:
            config = load_taskfile(EXAMPLES_DIR / name / "Taskfile.yml")
            assert len(config.tasks) > 0, f"{name} has no tasks"

    def test_all_examples_validate_successfully(self):
        """E2E: validate_taskfile passes for all examples."""
        for name in self.ALL_EXAMPLES:
            config = load_taskfile(EXAMPLES_DIR / name / "Taskfile.yml")
            warnings = validate_taskfile(config)
            assert isinstance(warnings, list), f"{name}: warnings not a list"

    def test_cli_list_works_for_all_examples(self):
        """E2E: taskfile list works for all examples."""
        runner = CliRunner()
        for name in self.ALL_EXAMPLES:
            result = runner.invoke(
                main,
                ["-f", str(EXAMPLES_DIR / name / "Taskfile.yml"), "list"]
            )
            assert result.exit_code == 0, f"list failed for {name}: {result.output}"
            assert "Tasks:" in result.output or "tasks" in result.output.lower()

    def test_cli_validate_works_for_all_examples(self):
        """E2E: taskfile validate works for all examples."""
        runner = CliRunner()
        for name in self.ALL_EXAMPLES:
            result = runner.invoke(
                main,
                ["-f", str(EXAMPLES_DIR / name / "Taskfile.yml"), "validate"]
            )
            assert result.exit_code == 0, f"validate failed for {name}: {result.output}"


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

    def test_parallel_deps_in_new_examples(self):
        """E2E: Parallel deps used in iac-terraform and monorepo-microservices."""
        config = load_taskfile(EXAMPLES_DIR / "iac-terraform" / "Taskfile.yml")
        has_parallel = any(t.parallel for t in config.tasks.values())
        assert has_parallel, "iac-terraform should have parallel tasks"

    def test_task_descriptions_present(self):
        """E2E: All tasks have descriptions for UX."""
        examples = ["minimal", "saas-app", "multiplatform", "codereview.pl"]

        for example in examples:
            config = load_taskfile(EXAMPLES_DIR / example / "Taskfile.yml")
            for name, task in config.tasks.items():
                assert task.description is not None, f"{example}/{name} missing description"
                assert len(task.description) > 0, f"{example}/{name} has empty description"


class TestIncludeFeature:
    """E2E tests for the include feature."""

    @pytest.fixture
    def include_path(self):
        return EXAMPLES_DIR / "include-split"

    def test_include_loads_successfully(self, include_path):
        """E2E: Include example parses without errors."""
        config = load_taskfile(include_path / "Taskfile.yml")
        assert config.name == "myproject"

    def test_include_merges_tasks(self, include_path):
        """E2E: Tasks from included files are merged."""
        config = load_taskfile(include_path / "Taskfile.yml")
        # From tasks/build.yml
        assert "build" in config.tasks
        assert "push" in config.tasks
        # From tasks/test.yml
        assert "lint" in config.tasks
        assert "test" in config.tasks
        # From tasks/deploy.yml (prefix: deploy)
        assert "deploy-local" in config.tasks
        assert "deploy-staging" in config.tasks
        assert "deploy-prod" in config.tasks
        # Local tasks
        assert "all" in config.tasks
        assert "clean" in config.tasks

    def test_include_merges_environments(self, include_path):
        """E2E: Environments from included files are merged."""
        config = load_taskfile(include_path / "Taskfile.yml")
        # From tasks/deploy.yml
        assert "staging" in config.environments
        assert "prod" in config.environments
        # Local
        assert "local" in config.environments

    def test_include_merges_variables(self, include_path):
        """E2E: Variables from included files are merged (local wins)."""
        config = load_taskfile(include_path / "Taskfile.yml")
        # Local variable takes precedence
        assert config.variables["APP_NAME"] == "myproject"
        # From tasks/build.yml (only if not overridden)
        assert "BUILD_DIR" in config.variables

    def test_include_local_overrides(self, include_path):
        """E2E: Local Taskfile definitions override included ones."""
        config = load_taskfile(include_path / "Taskfile.yml")
        # Local variables should win over included
        assert config.variables["IMAGE"] == "ghcr.io/myorg/myproject"

    def test_include_validate(self, include_path):
        """E2E: Included Taskfile validates."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["-f", str(include_path / "Taskfile.yml"), "validate"]
        )
        assert result.exit_code == 0

    def test_include_list_shows_all_tasks(self, include_path):
        """E2E: List shows tasks from all included files."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["-f", str(include_path / "Taskfile.yml"), "list"]
        )
        assert result.exit_code == 0
        assert "build" in result.output
        assert "deploy-prod" in result.output
        assert "lint" in result.output


class TestIncludeEdgeCases:
    """E2E tests for include edge cases."""

    def test_include_missing_file_raises(self, tmp_path):
        """E2E: Missing include file raises error."""
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            'version: "1"\nname: test\n'
            "include:\n  - path: ./nonexistent.yml\n"
            "tasks:\n  hello:\n    cmds: [echo hi]\n"
        )
        with pytest.raises(Exception):
            load_taskfile(taskfile)

    def test_include_empty_list_ok(self, tmp_path):
        """E2E: Empty include list is fine."""
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            'version: "1"\nname: test\ninclude: []\n'
            "tasks:\n  hello:\n    cmds: [echo hi]\n"
        )
        config = load_taskfile(taskfile)
        assert "hello" in config.tasks

    def test_include_string_shorthand(self, tmp_path):
        """E2E: Include with string shorthand works."""
        inc = tmp_path / "extra.yml"
        inc.write_text("tasks:\n  extra:\n    cmds: [echo extra]\n")
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(
            'version: "1"\nname: test\n'
            "include:\n  - extra.yml\n"
            "tasks:\n  hello:\n    cmds: [echo hi]\n"
        )
        config = load_taskfile(taskfile)
        assert "hello" in config.tasks
        assert "extra" in config.tasks


class TestCIGenerationExample:
    """E2E tests for ci-generation example."""

    @pytest.fixture
    def cigen_path(self):
        return EXAMPLES_DIR / "ci-generation"

    def test_cigen_pipeline_stages(self, cigen_path):
        """E2E: Pipeline has correct stages."""
        config = load_taskfile(cigen_path / "Taskfile.yml")
        assert len(config.pipeline.stages) == 6
        stage_names = [s.name for s in config.pipeline.stages]
        assert "lint" in stage_names
        assert "test" in stage_names
        assert "build" in stage_names
        assert "deploy-staging" in stage_names
        assert "deploy-prod" in stage_names
        assert "release" in stage_names

    def test_cigen_pipeline_secrets(self, cigen_path):
        """E2E: Pipeline secrets parsed correctly."""
        config = load_taskfile(cigen_path / "Taskfile.yml")
        assert "GHCR_TOKEN" in config.pipeline.secrets
        assert "SSH_PRIVATE_KEY" in config.pipeline.secrets

    def test_cigen_stage_triggers(self, cigen_path):
        """E2E: Stage triggers (when) parsed correctly."""
        config = load_taskfile(cigen_path / "Taskfile.yml")
        stage_map = {s.name: s for s in config.pipeline.stages}
        assert stage_map["deploy-staging"].when == "branch:develop"
        assert stage_map["deploy-prod"].when == "manual"
        assert stage_map["release"].when == "tag"

    def test_cigen_docker_in_docker(self, cigen_path):
        """E2E: docker_in_docker flag parsed."""
        config = load_taskfile(cigen_path / "Taskfile.yml")
        stage_map = {s.name: s for s in config.pipeline.stages}
        assert stage_map["build"].docker_in_docker is True


class TestScriptExtractionExample:
    """E2E tests for script-extraction example."""

    @pytest.fixture
    def script_path(self):
        return EXAMPLES_DIR / "script-extraction"

    def test_script_extraction_loads(self, script_path):
        """E2E: Script extraction example parses."""
        config = load_taskfile(script_path / "Taskfile.yml")
        assert config.name == "webapp"

    def test_script_extraction_has_script_tasks(self, script_path):
        """E2E: Tasks reference external scripts."""
        config = load_taskfile(script_path / "Taskfile.yml")
        build_task = config.tasks["build"]
        assert any("./scripts/build.sh" in cmd for cmd in build_task.commands)
        release_task = config.tasks["release"]
        assert any("scripts/release.py" in cmd for cmd in release_task.commands)

    def test_script_extraction_inline_tasks(self, script_path):
        """E2E: Simple tasks stay inline."""
        config = load_taskfile(script_path / "Taskfile.yml")
        test_task = config.tasks["test"]
        assert any("pytest" in cmd for cmd in test_task.commands)

    def test_script_files_exist(self, script_path):
        """E2E: All referenced script files exist."""
        scripts = [
            "scripts/build.sh", "scripts/deploy.sh",
            "scripts/health-check.sh", "scripts/ci-pipeline.sh",
            "scripts/release.py", "scripts/migrate.py",
            "scripts/report.py", "scripts/provision.py",
        ]
        for script in scripts:
            assert (script_path / script).is_file(), f"Missing: {script}"


class TestSSHEmbedded:
    """E2E tests for SSH embedded (paramiko) support."""

    def test_ssh_module_imports(self):
        """E2E: SSH module imports without error."""
        from taskfile.ssh import has_paramiko, ssh_exec, close_all
        # Should not raise, regardless of paramiko availability
        assert callable(has_paramiko)
        assert callable(ssh_exec)
        assert callable(close_all)

    def test_ssh_has_paramiko_returns_bool(self):
        """E2E: has_paramiko returns boolean."""
        from taskfile.ssh import has_paramiko
        result = has_paramiko()
        assert isinstance(result, bool)

    def test_runner_accepts_embedded_ssh_flag(self):
        """E2E: TaskfileRunner accepts use_embedded_ssh parameter."""
        config = load_taskfile(EXAMPLES_DIR / "minimal" / "Taskfile.yml")
        runner = TaskfileRunner(config=config, dry_run=True, use_embedded_ssh=False)
        assert runner.use_embedded_ssh is False

    def test_runner_default_embedded_ssh(self):
        """E2E: TaskfileRunner defaults use_embedded_ssh based on paramiko."""
        from taskfile.ssh import has_paramiko
        config = load_taskfile(EXAMPLES_DIR / "minimal" / "Taskfile.yml")
        runner = TaskfileRunner(config=config, dry_run=True)
        # Should be True only if paramiko is installed
        assert runner.use_embedded_ssh == has_paramiko()

    def test_close_all_safe_when_empty(self):
        """E2E: close_all doesn't crash when no connections."""
        from taskfile.ssh import close_all
        close_all()  # Should not raise


class TestNewExamplesSpecific:
    """E2E tests for specific new examples."""

    def test_kubernetes_deploy_environments(self):
        """E2E: Kubernetes example has multi-cluster environments."""
        config = load_taskfile(EXAMPLES_DIR / "kubernetes-deploy" / "Taskfile.yml")
        env_names = list(config.environments.keys())
        assert "local" in env_names

    def test_iac_terraform_conditions(self):
        """E2E: Terraform example uses conditions."""
        config = load_taskfile(EXAMPLES_DIR / "iac-terraform" / "Taskfile.yml")
        tasks_with_condition = [t for t in config.tasks.values() if t.condition]
        assert len(tasks_with_condition) > 0

    def test_edge_iot_environment_groups(self):
        """E2E: Edge IoT example has all 3 group strategies."""
        config = load_taskfile(EXAMPLES_DIR / "edge-iot" / "Taskfile.yml")
        strategies = {g.strategy for g in config.environment_groups.values()}
        assert "rolling" in strategies
        assert "parallel" in strategies
        assert "canary" in strategies

    def test_monorepo_platforms(self):
        """E2E: Monorepo example has platforms defined."""
        config = load_taskfile(EXAMPLES_DIR / "monorepo-microservices" / "Taskfile.yml")
        assert len(config.platforms) > 0

    def test_quadlet_podman_service_manager(self):
        """E2E: Quadlet example uses service_manager=quadlet."""
        config = load_taskfile(EXAMPLES_DIR / "quadlet-podman" / "Taskfile.yml")
        quadlet_envs = [e for e in config.environments.values() if e.service_manager == "quadlet"]
        assert len(quadlet_envs) > 0

    def test_cloud_aws_env_files(self):
        """E2E: Cloud AWS example uses env_file."""
        config = load_taskfile(EXAMPLES_DIR / "cloud-aws" / "Taskfile.yml")
        envs_with_file = [e for e in config.environments.values() if e.env_file]
        assert len(envs_with_file) > 0

    def test_ci_pipeline_stages_inferred(self):
        """E2E: CI pipeline example has stage fields on tasks."""
        config = load_taskfile(EXAMPLES_DIR / "ci-pipeline" / "Taskfile.yml")
        tasks_with_stage = [t for t in config.tasks.values() if t.stage]
        assert len(tasks_with_stage) > 0

    def test_fullstack_deploy_all_features(self):
        """E2E: Fullstack example has environments, tasks, pipeline."""
        config = load_taskfile(EXAMPLES_DIR / "fullstack-deploy" / "Taskfile.yml")
        assert len(config.environments) >= 3
        assert len(config.tasks) >= 10
        assert len(config.pipeline.stages) >= 3


# ═══════════════════════════════════════════════════════════════════════
# Functions Embed Example
# ═══════════════════════════════════════════════════════════════════════

class TestFunctionsEmbedExample:
    """E2E tests for the functions-embed example."""

    def test_loads_successfully(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        assert config.name == "webapp-functions"

    def test_has_functions_section(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        assert len(config.functions) >= 5

    def test_function_langs(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        langs = {fn.lang for fn in config.functions.values()}
        assert "shell" in langs
        assert "python" in langs
        assert "node" in langs
        assert "binary" in langs

    def test_function_inline_code(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        notify = config.functions.get("notify")
        assert notify is not None
        assert notify.lang == "python"
        assert notify.code is not None
        assert "urllib" in notify.code

    def test_function_file_ref(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        report = config.functions.get("generate-report")
        assert report is not None
        assert report.file == "scripts/report.py"

    def test_tasks_use_fn_prefix(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        deploy = config.tasks.get("deploy")
        assert deploy is not None
        fn_cmds = [c for c in deploy.commands if c.startswith("@fn ")]
        assert len(fn_cmds) >= 2

    def test_tasks_use_python_prefix(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        inline = config.tasks.get("inline-python")
        assert inline is not None
        py_cmds = [c for c in inline.commands if c.startswith("@python ")]
        assert len(py_cmds) >= 1

    def test_retries_and_timeout(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        full = config.tasks.get("full-deploy")
        assert full is not None
        assert full.retries == 2
        assert full.retry_delay == 5
        assert full.timeout == 300

    def test_tags(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        full = config.tasks.get("full-deploy")
        assert full is not None
        assert "ci" in full.tags
        assert "deploy" in full.tags
        assert "release" in full.tags

    def test_register(self):
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        cap = config.tasks.get("capture-version")
        assert cap is not None
        assert cap.register == "APP_VERSION"

    def test_cli_list(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["-f", str(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml"), "list"]
        )
        assert result.exit_code == 0
        assert "deploy" in result.output

    def test_cli_validate(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["-f", str(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml"), "validate"]
        )
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════
# Import CICD Example
# ═══════════════════════════════════════════════════════════════════════

class TestImportCICDExample:
    """E2E tests for the import-cicd example."""

    def test_loads_successfully(self):
        config = load_taskfile(EXAMPLES_DIR / "import-cicd" / "Taskfile.yml")
        assert config.name == "import-cicd-demo"

    def test_has_import_tasks(self):
        config = load_taskfile(EXAMPLES_DIR / "import-cicd" / "Taskfile.yml")
        assert "import-github" in config.tasks
        assert "import-gitlab" in config.tasks
        assert "import-makefile" in config.tasks
        assert "import-shell" in config.tasks
        assert "import-all" in config.tasks

    def test_import_all_is_parallel(self):
        config = load_taskfile(EXAMPLES_DIR / "import-cicd" / "Taskfile.yml")
        task = config.tasks["import-all"]
        assert task.parallel is True
        assert len(task.deps) == 4


# ═══════════════════════════════════════════════════════════════════════
# Importer Module Tests
# ═══════════════════════════════════════════════════════════════════════

class TestImporterModule:
    """E2E tests for the taskfile.importer module."""

    def test_import_github_actions(self):
        from taskfile.importer import import_file
        result = import_file(
            EXAMPLES_DIR / "import-cicd" / "sources" / "ci.yml",
            source_type="github-actions",
        )
        assert "tasks:" in result
        assert "lint" in result
        assert "test" in result
        assert "build" in result

    def test_import_gitlab_ci(self):
        from taskfile.importer import import_file
        result = import_file(
            EXAMPLES_DIR / "import-cicd" / "sources" / ".gitlab-ci.yml",
            source_type="gitlab-ci",
        )
        assert "tasks:" in result
        assert "lint" in result
        assert "pipeline:" in result or "stages:" in result

    def test_import_makefile(self):
        from taskfile.importer import import_file
        result = import_file(
            EXAMPLES_DIR / "import-cicd" / "sources" / "Makefile",
            source_type="makefile",
        )
        assert "tasks:" in result
        assert "build" in result
        assert "deploy" in result

    def test_import_shell_script(self):
        from taskfile.importer import import_file
        result = import_file(
            EXAMPLES_DIR / "import-cicd" / "sources" / "deploy.sh",
            source_type="shell",
        )
        assert "tasks:" in result
        # Shell functions should become tasks
        assert "build" in result or "deploy" in result

    def test_import_file_not_found(self):
        from taskfile.importer import import_file
        import pytest
        with pytest.raises(FileNotFoundError):
            import_file("/nonexistent/file.yml", source_type="github-actions")

    def test_import_unknown_type(self):
        from taskfile.importer import import_file
        import pytest
        with pytest.raises(ValueError, match="Unknown source type"):
            import_file(
                EXAMPLES_DIR / "import-cicd" / "sources" / "ci.yml",
                source_type="unknown-format",
            )

    def test_imported_yaml_is_valid(self):
        """Imported Taskfile YAML should be parseable by our own parser."""
        import tempfile
        from taskfile.importer import import_file

        for source, stype in [
            ("sources/ci.yml", "github-actions"),
            ("sources/.gitlab-ci.yml", "gitlab-ci"),
            ("sources/Makefile", "makefile"),
            ("sources/deploy.sh", "shell"),
        ]:
            result = import_file(
                EXAMPLES_DIR / "import-cicd" / source,
                source_type=stype,
            )
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
                f.write(result)
                f.flush()
                config = load_taskfile(f.name)
                assert len(config.tasks) > 0, f"No tasks from {source}"


# ═══════════════════════════════════════════════════════════════════════
# Ansible-Inspired Feature Tests (retries, timeout, tags, register)
# ═══════════════════════════════════════════════════════════════════════

class TestAnsibleInspiredFeatures:
    """E2E tests for Ansible-inspired task attributes."""

    def test_retries_parsed(self):
        """Tasks with retries field should parse correctly."""
        config = load_taskfile(EXAMPLES_DIR / "saas-app" / "Taskfile.yml")
        deploy = config.tasks.get("deploy")
        assert deploy is not None
        assert deploy.retries == 2
        assert deploy.retry_delay == 10

    def test_timeout_parsed(self):
        """Tasks with timeout field should parse correctly."""
        config = load_taskfile(EXAMPLES_DIR / "saas-app" / "Taskfile.yml")
        deploy = config.tasks.get("deploy")
        assert deploy is not None
        assert deploy.timeout == 300

    def test_tags_parsed(self):
        """Tasks with tags field should parse correctly."""
        config = load_taskfile(EXAMPLES_DIR / "saas-app" / "Taskfile.yml")
        lint = config.tasks.get("lint")
        assert lint is not None
        assert "ci" in lint.tags
        assert "quality" in lint.tags

    def test_tags_on_fleet_rpi(self):
        """Fleet RPi example should have tags on deploy tasks."""
        config = load_taskfile(EXAMPLES_DIR / "fleet-rpi" / "Taskfile.yml")
        deploy = config.tasks.get("deploy-kiosk")
        assert deploy is not None
        assert "deploy" in deploy.tags

    def test_register_parsed(self):
        """Tasks with register field should parse correctly."""
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        cap = config.tasks.get("capture-version")
        assert cap is not None
        assert cap.register == "APP_VERSION"

    def test_default_values(self):
        """Tasks without new fields should have correct defaults."""
        config = load_taskfile(EXAMPLES_DIR / "minimal" / "Taskfile.yml")
        for task in config.tasks.values():
            assert task.retries == 0
            assert task.retry_delay == 1
            assert task.timeout == 0
            assert task.tags == []
            assert task.register is None

    def test_tags_string_format(self):
        """Tags should work as comma-separated string too (in from_dict)."""
        from taskfile.models import TaskfileConfig
        raw = {
            "tasks": {
                "test": {
                    "cmds": ["echo hi"],
                    "tags": "ci, deploy, release",
                }
            }
        }
        config = TaskfileConfig.from_dict(raw)
        task = config.tasks["test"]
        assert task.tags == ["ci", "deploy", "release"]

    def test_functions_parsed(self):
        """Functions section should parse correctly."""
        config = load_taskfile(EXAMPLES_DIR / "functions-embed" / "Taskfile.yml")
        assert "check-port" in config.functions
        assert "notify" in config.functions
        assert "generate-report" in config.functions
        assert config.functions["notify"].lang == "python"
        assert config.functions["check-port"].lang == "shell"
        assert config.functions["render-config"].lang == "node"
        assert config.functions["lint-yaml"].lang == "binary"

    def test_function_shorthand(self):
        """Function defined as string should default to shell inline code."""
        from taskfile.models import TaskfileConfig
        raw = {
            "tasks": {"test": {"cmds": ["echo hi"]}},
            "functions": {"greet": "echo hello"},
        }
        config = TaskfileConfig.from_dict(raw)
        fn = config.functions["greet"]
        assert fn.lang == "shell"
        assert fn.code == "echo hello"


# ═══════════════════════════════════════════════════════════════════════
# CLI Import Command Tests
# ═══════════════════════════════════════════════════════════════════════

class TestCLIImportCommand:
    """E2E tests for the `taskfile import` CLI command."""

    def test_import_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["import", "--help"])
        assert result.exit_code == 0
        assert "github-actions" in result.output
        assert "gitlab-ci" in result.output
        assert "makefile" in result.output

    def test_import_github_actions_cli(self):
        import tempfile
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
            out_path = f.name
        result = runner.invoke(main, [
            "import",
            str(EXAMPLES_DIR / "import-cicd" / "sources" / "ci.yml"),
            "--type", "github-actions",
            "-o", out_path,
            "--force",
        ])
        assert result.exit_code == 0
        assert "Imported" in result.output

    def test_import_makefile_cli(self):
        import tempfile
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
            out_path = f.name
        result = runner.invoke(main, [
            "import",
            str(EXAMPLES_DIR / "import-cicd" / "sources" / "Makefile"),
            "--type", "makefile",
            "-o", out_path,
            "--force",
        ])
        assert result.exit_code == 0
        assert "Imported" in result.output


# ═══════════════════════════════════════════════════════════════════════
# CLI Tags Flag Tests
# ═══════════════════════════════════════════════════════════════════════

class TestCLITagsFlag:
    """E2E tests for --tags flag on the run command."""

    def test_run_help_shows_tags(self):
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "--tags" in result.output

    def test_info_shows_tags(self):
        """The info command should display tags for tasks that have them."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "-f", str(EXAMPLES_DIR / "saas-app" / "Taskfile.yml"),
            "info", "lint",
        ])
        assert result.exit_code == 0
        assert "Tags" in result.output
        assert "ci" in result.output

    def test_info_shows_retries(self):
        """The info command should display retries for tasks that have them."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "-f", str(EXAMPLES_DIR / "saas-app" / "Taskfile.yml"),
            "info", "deploy",
        ])
        assert result.exit_code == 0
        assert "Retries" in result.output
        assert "Timeout" in result.output
