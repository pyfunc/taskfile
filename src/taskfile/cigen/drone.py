from __future__ import annotations
from taskfile.cigen.base import CITarget, register_target, _sanitize_id, _yaml_dump

# ─── Drone CI ─────────────────────────────────────────────

@register_target("drone")
class DroneCITarget(CITarget):
    name = "drone"
    output_path = ".drone.yml"
    description = "Drone CI"

    def _tag_var(self) -> str:
        return "${DRONE_COMMIT_SHA:0:8}"

    def _build_base_doc(self) -> dict:
        """Build the base Drone pipeline document."""
        p = self.pipeline
        return {
            "kind": "pipeline",
            "type": "docker",
            "name": self.config.name or "default",
            "trigger": {"branch": p.branches or ["main"]},
            "steps": [],
        }

    def _build_step(self, stage, p) -> dict:
        """Build a single Drone step for a pipeline stage."""
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

        return step

    def _add_global_volumes(self, doc: dict, p) -> None:
        """Add global volumes if any stage needs Docker-in-Docker."""
        if any(s.docker_in_docker or p.docker_in_docker for s in p.stages):
            doc["volumes"] = [{"name": "docker", "host": {"path": "/var/run/docker.sock"}}]

    def generate(self) -> str:
        """Generate Drone CI configuration."""
        p = self.pipeline
        doc = self._build_base_doc()

        for stage in p.stages:
            step = self._build_step(stage, p)
            doc["steps"].append(step)

        self._add_global_volumes(doc, p)

        return _yaml_dump(doc)
