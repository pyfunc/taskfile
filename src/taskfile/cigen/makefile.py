from __future__ import annotations
from taskfile.cigen.base import CITarget, register_target, _sanitize_id, _yaml_dump

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
