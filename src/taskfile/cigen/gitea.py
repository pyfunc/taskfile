from __future__ import annotations
from taskfile.cigen.base import CITarget, register_target, _sanitize_id, _yaml_dump

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
