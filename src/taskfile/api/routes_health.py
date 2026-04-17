"""Health check endpoint for the Taskfile REST API."""

from __future__ import annotations

from fastapi import FastAPI

from taskfile import __version__
from taskfile.api.models import HealthResponse
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    find_taskfile,
    load_taskfile,
)


def register_health_routes(app: FastAPI) -> None:
    """Register health check endpoint."""

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="Health check",
    )
    def health():
        """Check API health and Taskfile availability."""
        try:
            tf_path = find_taskfile(app.state.taskfile_path)
            config = load_taskfile(tf_path)
            return HealthResponse(
                status="ok",
                version=__version__,
                taskfile_found=True,
                taskfile_path=str(tf_path),
                task_count=len(config.tasks),
                env_count=len(config.environments),
            )
        except (TaskfileNotFoundError, TaskfileParseError):
            return HealthResponse(
                status="ok",
                version=__version__,
                taskfile_found=False,
            )
