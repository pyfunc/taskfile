from __future__ import annotations
from taskfile.cigen.base import CITarget, register_target, _sanitize_id, _yaml_dump

# ─── GitHub Actions ───────────────────────────────────────


@register_target("github")
class GitHubActionsTarget(CITarget):
    name = "github"
    output_path = ".github/workflows/taskfile.yml"
    description = "GitHub Actions"

    def _tag_var(self) -> str:
        if self._has_tag_stages():
            return "${{ github.ref_name }}"
        return "${{ github.sha }}"

    def _build_steps(self, stage) -> list[dict]:
        p = self.pipeline
        needs_dind = stage.docker_in_docker or p.docker_in_docker
        steps: list[dict] = [
            {"uses": "actions/checkout@v4"},
            {"uses": "actions/setup-python@v5", "with": {"python-version": p.python_version}},
            {"run": p.install_cmd},
        ]

        if stage.env and stage.env != "local":
            steps.append(
                {
                    "name": "Setup SSH key",
                    "run": (
                        "mkdir -p ~/.ssh\n"
                        'echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_ed25519\n'
                        "chmod 600 ~/.ssh/id_ed25519"
                    ),
                }
            )

        if needs_dind:
            steps.append(
                {
                    "name": "Login to Container Registry",
                    "run": (
                        'echo "${{ secrets.REGISTRY_TOKEN }}" | '
                        "docker login ghcr.io -u ${{ github.actor }} --password-stdin"
                    ),
                }
            )

        steps.append(
            {
                "name": f"Run: {stage.name}",
                "run": self._stage_tasks_cmd(stage),
            }
        )

        arts = stage.artifacts or p.artifacts
        if arts:
            steps.append(
                {
                    "uses": "actions/upload-artifact@v4",
                    "with": {
                        "name": f"{stage.name}-artifacts",
                        "path": "\n".join(arts),
                    },
                }
            )

        return steps

    def _apply_conditions(self, job: dict, stage) -> None:
        if stage.when == "manual":
            job["if"] = "github.event_name == 'workflow_dispatch'"
        elif stage.when.startswith("branch:"):
            branch = stage.when.split(":", 1)[1]
            job["if"] = f"github.ref == 'refs/heads/{branch}'"
        elif stage.when == "tag":
            job["if"] = "startsWith(github.ref, 'refs/tags/')"

    def _has_tag_stages(self) -> bool:
        """Check if any stage is triggered by tags."""
        return any(s.when == "tag" for s in self.pipeline.stages)

    def _build_on_triggers(self, branches: list[str]) -> dict:
        """Build the 'on' triggers section."""
        triggers: dict = {
            "push": {"branches": branches},
            "workflow_dispatch": {},
        }
        if self._has_tag_stages():
            triggers["push"]["tags"] = ["v*"]
        return triggers

    def generate(self) -> str:
        p = self.pipeline
        branches = p.branches or ["main"]

        workflow: dict = {
            "name": self.config.name or "Taskfile Pipeline",
            "on": self._build_on_triggers(branches),
            "jobs": {},
        }

        prev_job: str | None = None

        for stage in p.stages:
            job_id = _sanitize_id(stage.name)
            runner = stage.runner or p.runner_image or "ubuntu-latest"

            steps = self._build_steps(stage)

            job: dict = {
                "runs-on": runner,
                "steps": steps,
            }

            if prev_job:
                job["needs"] = prev_job

            self._apply_conditions(job, stage)
            self._apply_secrets_env(job, p)

            workflow["jobs"][job_id] = job
            prev_job = job_id

        return _yaml_dump(workflow)

    def _apply_secrets_env(self, job: dict, pipeline) -> None:
        """Add secrets as environment variables to the job."""
        if not pipeline.secrets:
            return
        env = {}
        for secret in pipeline.secrets:
            env[secret] = "${{ secrets." + secret + " }}"
        if env:
            job["env"] = env
