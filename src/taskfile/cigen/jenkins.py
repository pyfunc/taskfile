from __future__ import annotations
from taskfile.cigen.base import CITarget, register_target, _sanitize_id, _yaml_dump

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
