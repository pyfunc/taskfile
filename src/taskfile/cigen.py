"""CI/CD config generator — generates platform-specific CI/CD files from Taskfile.yml.

Supported targets: github, gitlab, gitea, drone, jenkins
All generated configs are thin wrappers that call `taskfile run`.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console

from taskfile.models import PipelineConfig, PipelineStage, TaskfileConfig

console = Console()

# ─── Target registry ──────────────────────────────────────

TARGETS: dict[str, type["CITarget"]] = {}


def register_target(name: str):
    """Decorator to register a CI/CD target generator."""
    def decorator(cls):
        TARGETS[name] = cls
        return cls
    return decorator


class CITarget:
    """Base class for CI/CD target generators."""

    name: str = ""
    output_path: str = ""
    description: str = ""

    def __init__(self, config: TaskfileConfig):
        self.config = config
        self.pipeline = config.pipeline

    def generate(self) -> str:
        """Generate the CI/CD config content. Override in subclasses."""
        raise NotImplementedError

    def write(self, project_dir: str | Path = ".") -> Path:
        """Write the generated config to the appropriate file."""
        outpath = Path(project_dir) / self.output_path
        outpath.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate()
        outpath.write_text(content)
        return outpath

    def _tag_var(self) -> str:
        """Platform-specific variable for commit SHA / tag."""
        return "latest"

    def _stage_env_flag(self, stage: PipelineStage) -> str:
        """Build --env flag for a stage."""
        env = stage.env or self.config.default_env
        return f"--env {env}" if env else ""

    def _stage_tasks_cmd(self, stage: PipelineStage) -> str:
        """Build the taskfile run command for a stage."""
        tasks = " ".join(stage.tasks)
        env_flag = self._stage_env_flag(stage)
        tag = self._tag_var()
        return f"taskfile {env_flag} run {tasks} --var TAG={tag}".strip()


# ─── GitHub Actions ───────────────────────────────────────

@register_target("github")
class GitHubActionsTarget(CITarget):
    name = "github"
    output_path = ".github/workflows/taskfile.yml"
    description = "GitHub Actions"

    def _tag_var(self) -> str:
        return "${{ github.sha }}"

    def generate(self) -> str:
        p = self.pipeline
        branches = p.branches or ["main"]

        workflow: dict = {
            "name": self.config.name or "Taskfile Pipeline",
            "on": {
                "push": {"branches": branches},
                "workflow_dispatch": {},
            },
            "jobs": {},
        }

        prev_job: str | None = None

        for stage in p.stages:
            job_id = _sanitize_id(stage.name)
            runner = stage.runner or p.runner_image or "ubuntu-latest"
            needs_dind = stage.docker_in_docker or p.docker_in_docker

            steps: list[dict] = [
                {"uses": "actions/checkout@v4"},
                {"uses": "actions/setup-python@v5", "with": {"python-version": p.python_version}},
                {"run": p.install_cmd},
            ]

            # SSH key setup for deploy stages
            if stage.env and stage.env != "local":
                steps.append({
                    "name": "Setup SSH key",
                    "run": (
                        "mkdir -p ~/.ssh\n"
                        'echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_ed25519\n'
                        "chmod 600 ~/.ssh/id_ed25519"
                    ),
                })

            # Docker login for build stages
            if needs_dind:
                steps.append({
                    "name": "Login to Container Registry",
                    "run": (
                        'echo "${{ secrets.REGISTRY_TOKEN }}" | '
                        "docker login ghcr.io -u ${{ github.actor }} --password-stdin"
                    ),
                })

            # The actual taskfile command
            steps.append({
                "name": f"Run: {stage.name}",
                "run": self._stage_tasks_cmd(stage),
            })

            job: dict = {
                "runs-on": runner,
                "steps": steps,
            }

            if prev_job:
                job["needs"] = prev_job

            if stage.when == "manual":
                job["if"] = "github.event_name == 'workflow_dispatch'"
            elif stage.when.startswith("branch:"):
                branch = stage.when.split(":", 1)[1]
                job["if"] = f"github.ref == 'refs/heads/{branch}'"
            elif stage.when == "tag":
                job["if"] = "startsWith(github.ref, 'refs/tags/')"

            # Artifacts
            arts = stage.artifacts or p.artifacts
            if arts:
                steps.append({
                    "uses": "actions/upload-artifact@v4",
                    "with": {
                        "name": f"{stage.name}-artifacts",
                        "path": "\n".join(arts),
                    },
                })

            workflow["jobs"][job_id] = job
            prev_job = job_id

        return _yaml_dump(workflow)


# ─── GitLab CI ────────────────────────────────────────────

@register_target("gitlab")
class GitLabCITarget(CITarget):
    name = "gitlab"
    output_path = ".gitlab-ci.yml"
    description = "GitLab CI"

    def _tag_var(self) -> str:
        return "$CI_COMMIT_SHORT_SHA"

    def generate(self) -> str:
        p = self.pipeline

        doc: dict = {
            "stages": [s.name for s in p.stages],
        }

        # Default image
        image = f"python:{p.python_version}-slim"
        doc["default"] = {"image": image}

        # Cache
        caches = p.cache
        if caches:
            doc["default"]["cache"] = {
                "key": "$CI_COMMIT_REF_SLUG",
                "paths": caches,
            }

        for stage in p.stages:
            job_id = _sanitize_id(stage.name)
            job: dict = {
                "stage": stage.name,
                "script": [
                    p.install_cmd,
                    self._stage_tasks_cmd(stage),
                ],
            }

            needs_dind = stage.docker_in_docker or p.docker_in_docker
            if needs_dind:
                job["image"] = "docker:latest"
                job["services"] = ["docker:dind"]
                job["variables"] = {"DOCKER_TLS_CERTDIR": "/certs"}
                job["before_script"] = [
                    "apk add --no-cache python3 py3-pip",
                    p.install_cmd,
                ]
                # Remove install from main script since it's in before_script
                job["script"] = [self._stage_tasks_cmd(stage)]

            if stage.when == "manual":
                job["when"] = "manual"
            elif stage.when == "tag":
                job["rules"] = [{"if": "$CI_COMMIT_TAG"}]

            # Restrict to branches
            branches = p.branches
            if branches and stage.when == "auto":
                job["only"] = branches

            # SSH setup for remote stages
            if stage.env and stage.env != "local":
                before = job.get("before_script", [])
                before.extend([
                    'mkdir -p ~/.ssh',
                    'echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519',
                    'chmod 600 ~/.ssh/id_ed25519',
                ])
                job["before_script"] = before

            # Artifacts
            arts = stage.artifacts or p.artifacts
            if arts:
                job["artifacts"] = {"paths": arts}

            doc[job_id] = job

        return _yaml_dump(doc)


# ─── Gitea Actions ────────────────────────────────────────

@register_target("gitea")
class GiteaActionsTarget(CITarget):
    name = "gitea"
    output_path = ".gitea/workflows/taskfile.yml"
    description = "Gitea Actions"

    def _tag_var(self) -> str:
        return "${{ github.sha }}"  # Gitea uses same syntax as GitHub

    def generate(self) -> str:
        """Gitea Actions are mostly GitHub Actions compatible."""
        p = self.pipeline
        branches = p.branches or ["main"]

        workflow: dict = {
            "name": self.config.name or "Taskfile Pipeline",
            "on": {
                "push": {"branches": branches},
            },
            "jobs": {},
        }

        prev_job: str | None = None

        for stage in p.stages:
            job_id = _sanitize_id(stage.name)
            runner = stage.runner or p.runner_image or "ubuntu-latest"

            steps: list[dict] = [
                {"uses": "actions/checkout@v4"},
                {"run": f"pip install --break-system-packages taskfile || {p.install_cmd}"},
                {"name": f"Run: {stage.name}", "run": self._stage_tasks_cmd(stage)},
            ]

            job: dict = {"runs-on": runner, "steps": steps}
            if prev_job:
                job["needs"] = prev_job

            if stage.when == "manual":
                # Gitea doesn't fully support workflow_dispatch, skip manual stages
                job["if"] = "false  # manual trigger not supported in Gitea"

            workflow["jobs"][job_id] = job
            prev_job = job_id

        return _yaml_dump(workflow)


# ─── Drone CI ─────────────────────────────────────────────

@register_target("drone")
class DroneCITarget(CITarget):
    name = "drone"
    output_path = ".drone.yml"
    description = "Drone CI"

    def _tag_var(self) -> str:
        return "${DRONE_COMMIT_SHA:0:8}"

    def generate(self) -> str:
        p = self.pipeline

        doc: dict = {
            "kind": "pipeline",
            "type": "docker",
            "name": self.config.name or "default",
            "trigger": {"branch": p.branches or ["main"]},
            "steps": [],
        }

        for stage in p.stages:
            step: dict = {
                "name": stage.name,
                "image": f"python:{p.python_version}-slim",
                "commands": [
                    p.install_cmd,
                    self._stage_tasks_cmd(stage),
                ],
            }

            if stage.when == "manual":
                step["when"] = {"event": ["promote"]}

            needs_dind = stage.docker_in_docker or p.docker_in_docker
            if needs_dind:
                step["image"] = "docker"
                step["volumes"] = [{"name": "docker", "path": "/var/run/docker.sock"}]

            doc["steps"].append(step)

        if any(s.docker_in_docker or p.docker_in_docker for s in p.stages):
            doc["volumes"] = [{"name": "docker", "host": {"path": "/var/run/docker.sock"}}]

        return _yaml_dump(doc)


# ─── Jenkins ──────────────────────────────────────────────

@register_target("jenkins")
class JenkinsTarget(CITarget):
    name = "jenkins"
    output_path = "Jenkinsfile"
    description = "Jenkins Pipeline"

    def _tag_var(self) -> str:
        return "${GIT_COMMIT[0..7]}"

    def generate(self) -> str:
        p = self.pipeline
        lines = [
            "// Auto-generated from Taskfile.yml — do not edit manually",
            "// Regenerate with: taskfile ci generate --target jenkins",
            "pipeline {",
            f"    agent {{ docker {{ image 'python:{p.python_version}-slim' }} }}",
            "",
            "    environment {",
            f"        TAG = \"${{GIT_COMMIT.take(8)}}\"",
            "    }",
            "",
            "    stages {",
        ]

        for stage in p.stages:
            env_flag = self._stage_env_flag(stage)
            tasks = " ".join(stage.tasks)
            lines.extend([
                f"        stage('{stage.name}') {{",
                "            steps {",
                f"                sh '{p.install_cmd}'",
                f"                sh 'taskfile {env_flag} run {tasks} --var TAG=${{TAG}}'",
                "            }",
                "        }",
            ])

        lines.extend([
            "    }",
            "",
            "    post {",
            "        failure {",
            "            echo 'Pipeline failed!'",
            "        }",
            "    }",
            "}",
            "",
        ])

        return "\n".join(lines)


# ─── Makefile (compatibility wrapper) ─────────────────────

@register_target("makefile")
class MakefileTarget(CITarget):
    name = "makefile"
    output_path = "Makefile"
    description = "GNU Makefile"

    def generate(self) -> str:
        lines = [
            "# Auto-generated from Taskfile.yml — do not edit manually",
            "# Regenerate with: taskfile ci generate --target makefile",
            "",
            "ENV ?= local",
            "TAG ?= latest",
            "",
            ".PHONY: help",
            "help: ## Show available targets",
            '\t@grep -E \'^[a-zA-Z_-]+:.*?## .*$$\' $(MAKEFILE_LIST) | '
            "sort | awk 'BEGIN {FS = \":.*?## \"}; {printf \"  \\033[36m%-20s\\033[0m %s\\n\", $$1, $$2}'",
            "",
        ]

        # Generate targets for each task
        for task_name, task in sorted(self.config.tasks.items()):
            desc = task.description or task_name
            target = task_name.replace(":", "-")
            lines.append(f".PHONY: {target}")
            lines.append(f"{target}: ## {desc}")
            lines.append(f"\ttaskfile --env $(ENV) run {task_name} --var TAG=$(TAG)")
            lines.append("")

        # Pipeline stages as composite targets
        if self.pipeline.stages:
            lines.append("# ─── Pipeline stages ─────────────────")
            for stage in self.pipeline.stages:
                tasks_str = " ".join(stage.tasks)
                env_flag = f"--env {stage.env}" if stage.env else "--env $(ENV)"
                lines.append(f".PHONY: stage-{stage.name}")
                lines.append(f"stage-{stage.name}: ## Pipeline stage: {stage.name}")
                lines.append(f"\ttaskfile {env_flag} run {tasks_str} --var TAG=$(TAG)")
                lines.append("")

            # Full pipeline
            stage_targets = " ".join(f"stage-{s.name}" for s in self.pipeline.stages)
            lines.append(f".PHONY: pipeline")
            lines.append(f"pipeline: {stage_targets} ## Run full pipeline")
            lines.append("")

        return "\n".join(lines)


# ─── Helpers ──────────────────────────────────────────────

def _sanitize_id(name: str) -> str:
    """Make a name safe for use as YAML key / job ID."""
    return name.replace(" ", "-").replace("/", "-").lower()


def _yaml_dump(data: dict) -> str:
    """Dump dict to YAML with a generation header."""
    header = (
        "# Auto-generated from Taskfile.yml — do not edit manually\n"
        "# Regenerate with: taskfile ci generate\n\n"
    )
    return header + yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ─── Public API ───────────────────────────────────────────

def generate_ci(
    config: TaskfileConfig,
    target: str,
    project_dir: str | Path = ".",
) -> Path:
    """Generate CI/CD config for a specific target platform."""
    if target not in TARGETS:
        available = ", ".join(sorted(TARGETS.keys()))
        raise ValueError(f"Unknown CI target: '{target}'. Available: {available}")

    generator = TARGETS[target](config)
    outpath = generator.write(project_dir)
    console.print(f"  [green]✓[/] {generator.description}: {outpath}")
    return outpath


def generate_all_ci(
    config: TaskfileConfig,
    project_dir: str | Path = ".",
    targets: list[str] | None = None,
) -> list[Path]:
    """Generate CI/CD configs for multiple targets."""
    target_list = targets or list(TARGETS.keys())
    generated = []
    for target in target_list:
        path = generate_ci(config, target, project_dir)
        generated.append(path)
    return generated


def list_targets() -> list[tuple[str, str, str]]:
    """Return list of (name, output_path, description) for all registered targets."""
    result = []
    for name, cls in sorted(TARGETS.items()):
        result.append((name, cls.output_path, cls.description))
    return result


def preview_ci(config: TaskfileConfig, target: str) -> str:
    """Generate CI/CD config content without writing to disk."""
    if target not in TARGETS:
        available = ", ".join(sorted(TARGETS.keys()))
        raise ValueError(f"Unknown CI target: '{target}'. Available: {available}")
    return TARGETS[target](config).generate()
