from __future__ import annotations
from taskfile.cigen.base import CITarget, register_target, _sanitize_id, _yaml_dump

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
