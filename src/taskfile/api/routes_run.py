"""Task execution endpoint."""

from __future__ import annotations

import io
import time
from contextlib import redirect_stdout, redirect_stderr

from fastapi import FastAPI, HTTPException

from taskfile.api.models import (
    RunResult,
    RunTaskRequest,
    TaskRunResult,
    TaskStatus,
)
from taskfile.api.routes_helpers import _load_config


def register_run_routes(app: FastAPI) -> None:
    """Register task execution endpoint."""

    @app.post(
        "/run",
        response_model=RunResult,
        tags=["execution"],
        summary="Run tasks",
    )
    def run_tasks(request: RunTaskRequest):
        """Execute one or more tasks and return the result.

        Tasks are executed sequentially with dependency resolution.
        Use `dry_run: true` to preview commands without executing.
        """
        from taskfile.runner import TaskfileRunner

        config = _load_config(app.state.taskfile_path)

        unknown = [t for t in request.tasks if t not in config.tasks]
        if unknown:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown task(s): {', '.join(unknown)}. Available: {', '.join(sorted(config.tasks.keys()))}",
            )

        start_time = time.time()
        task_results = []

        try:
            runner = TaskfileRunner(
                config=config,
                env_name=request.env,
                platform_name=request.platform,
                var_overrides=request.variables,
                dry_run=request.dry_run,
                verbose=False,
            )

            for task_name in request.tasks:
                task_start = time.time()
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                try:
                    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                        success = runner.run([task_name])

                    duration_ms = int((time.time() - task_start) * 1000)
                    output_lines = [
                        line for line in stdout_capture.getvalue().splitlines() if line.strip()
                    ]
                    error_text = stderr_capture.getvalue().strip() or None

                    task_results.append(
                        TaskRunResult(
                            task=task_name,
                            status=TaskStatus.success if success else TaskStatus.failed,
                            duration_ms=duration_ms,
                            output=output_lines,
                            error=error_text if not success else None,
                        )
                    )

                    if not success:
                        break

                except Exception as exc:
                    duration_ms = int((time.time() - task_start) * 1000)
                    task_results.append(
                        TaskRunResult(
                            task=task_name,
                            status=TaskStatus.failed,
                            duration_ms=duration_ms,
                            error=str(exc),
                        )
                    )
                    break

        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Runner error: {exc}")

        total_ms = int((time.time() - start_time) * 1000)
        all_success = all(r.status == TaskStatus.success for r in task_results)

        return RunResult(
            success=all_success,
            tasks=task_results,
            total_duration_ms=total_ms,
            env=request.env,
            dry_run=request.dry_run,
        )
