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
