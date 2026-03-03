"""Local CI/CD pipeline runner — run your pipeline without any CI platform.

Replaces: act (GitHub), gitlab-runner exec (GitLab), etc.
Runs the same pipeline stages defined in Taskfile.yml, locally.
"""

from __future__ import annotations

import sys
import time
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from taskfile.models import PipelineConfig, PipelineStage, TaskfileConfig
from taskfile.runner import TaskfileRunner

console = Console()


class PipelineError(Exception):
    """Raised when a pipeline stage fails."""

    def __init__(self, stage_name: str, message: str):
        self.stage_name = stage_name
        super().__init__(f"Pipeline failed at stage '{stage_name}': {message}")


class PipelineRunner:
    """Runs CI/CD pipeline stages locally using TaskfileRunner.

    The pipeline is just an ordered list of stages, where each stage
    contains a list of tasks to run. This is the same structure that
    CI/CD platforms use — but runs directly on your machine.
    """

    def __init__(
        self,
        config: TaskfileConfig,
        env_name: str | None = None,
        var_overrides: dict[str, str] | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        self.config = config
        self.env_name = env_name
        self.var_overrides = var_overrides or {}
        self.dry_run = dry_run
        self.verbose = verbose
        self.pipeline = config.pipeline
        self.results: list[StageResult] = []

    def run(
        self,
        stage_filter: list[str] | None = None,
        skip_stages: list[str] | None = None,
        stop_at: str | None = None,
    ) -> bool:
        """Run pipeline stages in order.

        Args:
            stage_filter: Only run these stages (None = all non-manual)
            skip_stages: Skip these stages
            stop_at: Stop after this stage (inclusive)

        Returns:
            True if all stages passed.
        """
        if not self.pipeline.stages:
            console.print("[yellow]⚠ No pipeline stages defined in Taskfile.yml[/]")
            console.print("[dim]  Add a 'pipeline' section or use 'stage' field on tasks[/]")
            return True

        stages = self._resolve_stages(stage_filter, skip_stages, stop_at)

        if not stages:
            console.print("[yellow]No stages to run[/]")
            return True

        # Print pipeline overview
        self._print_pipeline_header(stages)

        total_start = time.time()
        success = True

        for i, stage in enumerate(stages):
            stage_start = time.time()
            prefix = f"[{i + 1}/{len(stages)}]"

            console.print(f"\n{'━' * 60}")
            stage_text = Text(f"{prefix} Stage: {stage.name}", style="bold blue")
            if stage.env:
                stage_text.append(f" ({stage.env})", style="cyan")
            console.print(stage_text)
            console.print(f"{'━' * 60}")

            # Determine environment for this stage
            stage_env = stage.env or self.env_name

            # Create a runner for this stage
            try:
                runner = TaskfileRunner(
                    config=self.config,
                    env_name=stage_env,
                    var_overrides=self.var_overrides,
                    dry_run=self.dry_run,
                    verbose=self.verbose,
                )

                stage_success = runner.run(stage.tasks)

                elapsed = time.time() - stage_start
                result = StageResult(
                    name=stage.name,
                    success=stage_success,
                    elapsed=elapsed,
                    tasks=stage.tasks,
                )
                self.results.append(result)

                if stage_success:
                    console.print(
                        f"\n  [green]✓ Stage '{stage.name}' passed[/] "
                        f"[dim]({elapsed:.1f}s)[/]"
                    )
                else:
                    console.print(
                        f"\n  [red]✗ Stage '{stage.name}' failed[/] "
                        f"[dim]({elapsed:.1f}s)[/]"
                    )
                    success = False
                    break

            except Exception as e:
                elapsed = time.time() - stage_start
                self.results.append(StageResult(
                    name=stage.name, success=False, elapsed=elapsed,
                    tasks=stage.tasks, error=str(e),
                ))
                console.print(f"\n  [red]✗ Stage '{stage.name}' error: {e}[/]")
                success = False
                break

        total_elapsed = time.time() - total_start
        self._print_summary(total_elapsed, success)
        return success

    def _resolve_stages(
        self,
        stage_filter: list[str] | None,
        skip_stages: list[str] | None,
        stop_at: str | None,
    ) -> list[PipelineStage]:
        """Resolve which stages to run."""
        stages = []
        skip = set(skip_stages or [])

        for stage in self.pipeline.stages:
            # Filter by explicit selection
            if stage_filter and stage.name not in stage_filter:
                continue

            # Skip explicitly excluded
            if stage.name in skip:
                console.print(f"  [dim]⊘ Skipping stage '{stage.name}' (excluded)[/]")
                continue

            # Skip manual stages unless explicitly requested
            if stage.when == "manual" and not stage_filter:
                console.print(
                    f"  [dim]⊘ Skipping stage '{stage.name}' (manual — "
                    f"use --stage {stage.name} to run)[/]"
                )
                continue

            stages.append(stage)

            if stop_at and stage.name == stop_at:
                break

        return stages

    def _print_pipeline_header(self, stages: list[PipelineStage]) -> None:
        """Print pipeline overview before running."""
        name = self.config.name or "Pipeline"
        stage_names = " → ".join(s.name for s in stages)

        panel_content = f"[bold]{name}[/]\n{stage_names}"
        if self.dry_run:
            panel_content += "\n[yellow](dry run)[/]"

        console.print(Panel(panel_content, border_style="blue", title="Pipeline"))

    def _print_summary(self, total_elapsed: float, success: bool) -> None:
        """Print final pipeline results summary."""
        console.print(f"\n{'═' * 60}")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Stage", style="cyan")
        table.add_column("Status")
        table.add_column("Time", justify="right")
        table.add_column("Tasks", style="dim")

        for result in self.results:
            status = "[green]✓ PASS[/]" if result.success else "[red]✗ FAIL[/]"
            tasks = ", ".join(result.tasks)
            table.add_row(result.name, status, f"{result.elapsed:.1f}s", tasks)

        console.print(table)

        status_text = "[bold green]PIPELINE PASSED[/]" if success else "[bold red]PIPELINE FAILED[/]"
        console.print(f"\n{status_text} [dim]({total_elapsed:.1f}s total)[/]")

    def list_stages(self) -> None:
        """Print available pipeline stages."""
        if not self.pipeline.stages:
            console.print("[yellow]No pipeline stages defined[/]")
            console.print("[dim]  Add a 'pipeline' section to Taskfile.yml[/]")
            return

        console.print(f"\n[bold]Pipeline Stages:[/]")
        for i, stage in enumerate(self.pipeline.stages):
            tasks = ", ".join(stage.tasks)
            when = f" [yellow]({stage.when})[/]" if stage.when != "auto" else ""
            env = f" [cyan][{stage.env}][/]" if stage.env else ""
            console.print(f"  {i + 1}. [green]{stage.name:15s}[/]{env}{when}  → {tasks}")

        console.print(f"\n[dim]Run all: taskfile ci run[/]")
        console.print(f"[dim]Run one: taskfile ci run --stage <name>[/]")


class StageResult:
    """Result of running a single pipeline stage."""

    def __init__(
        self,
        name: str,
        success: bool,
        elapsed: float,
        tasks: list[str],
        error: str | None = None,
    ):
        self.name = name
        self.success = success
        self.elapsed = elapsed
        self.tasks = tasks
        self.error = error
