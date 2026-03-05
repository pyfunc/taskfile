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
