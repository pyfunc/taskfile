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

    def _build_base_doc(self) -> dict:
        """Build the base GitLab CI document with stages, image, and cache."""
        p = self.pipeline
        doc: dict = {"stages": [s.name for s in p.stages]}

        image = f"python:{p.python_version}-slim"
        doc["default"] = {"image": image}

        caches = p.cache
        if caches:
            doc["default"]["cache"] = {
                "key": "$CI_COMMIT_REF_SLUG",
                "paths": caches,
            }

        return doc

    def _build_job(self, stage) -> dict:
        """Build the base job configuration for a stage."""
        p = self.pipeline
        return {
            "stage": stage.name,
            "script": [
                p.install_cmd,
                self._stage_tasks_cmd(stage),
            ],
        }

    def _apply_dind(self, job: dict, stage, p) -> None:
        """Apply Docker-in-Docker configuration if needed."""
        needs_dind = stage.docker_in_docker or p.docker_in_docker
        if not needs_dind:
            return

        job["image"] = "docker:latest"
        job["services"] = ["docker:dind"]
        job["variables"] = {"DOCKER_TLS_CERTDIR": "/certs"}
        job["before_script"] = [
            "apk add --no-cache python3 py3-pip",
            p.install_cmd,
        ]
        # Remove install from main script since it's in before_script
        job["script"] = [self._stage_tasks_cmd(stage)]

    def _apply_when_rules(self, job: dict, stage, p) -> None:
        """Apply when conditions, tag rules, and branch restrictions."""
        if stage.when == "manual":
            job["when"] = "manual"
        elif stage.when == "tag":
            job["rules"] = [{"if": "$CI_COMMIT_TAG"}]

        branches = p.branches
        if branches and stage.when == "auto":
            job["only"] = branches

    def _apply_ssh_setup(self, job: dict, stage) -> None:
        """Apply SSH key setup for remote stages."""
        if not (stage.env and stage.env != "local"):
            return

        before = job.get("before_script", [])
        before.extend(
            [
                "mkdir -p ~/.ssh",
                'echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519',
                "chmod 600 ~/.ssh/id_ed25519",
            ]
        )
        job["before_script"] = before

    def _apply_artifacts(self, job: dict, stage, p) -> None:
        """Apply artifact configuration."""
        arts = stage.artifacts or p.artifacts
        if arts:
            job["artifacts"] = {"paths": arts}

    def generate(self) -> str:
        """Generate GitLab CI configuration."""
        p = self.pipeline
        doc = self._build_base_doc()

        for stage in p.stages:
            job_id = _sanitize_id(stage.name)
            job = self._build_job(stage)

            self._apply_dind(job, stage, p)
            self._apply_when_rules(job, stage, p)
            self._apply_ssh_setup(job, stage)
            self._apply_artifacts(job, stage, p)

            doc[job_id] = job

        return _yaml_dump(doc)
