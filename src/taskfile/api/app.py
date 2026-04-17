"""FastAPI application factory for the Taskfile REST API.

Route implementations are split into submodules:
- routes_health.py    — /health
- routes_taskfile.py  — /taskfile, /validate, /variables, /schema
- routes_tasks.py     — /tasks, /tasks/{task_name}
- routes_run.py       — /run
- routes_metadata.py  — /environments, /groups, /platforms, /functions, /pipeline
- routes_doctor.py    — /doctor (GET + POST)
- routes_helpers.py   — shared _load_config, _config_to_info
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taskfile import __version__
from taskfile.api.models import ErrorResponse
from taskfile.api.routes_health import register_health_routes as _register_health_routes
from taskfile.api.routes_taskfile import register_taskfile_routes as _register_taskfile_routes
from taskfile.api.routes_tasks import register_task_routes as _register_task_routes
from taskfile.api.routes_run import register_run_routes as _register_run_routes
from taskfile.api.routes_metadata import register_metadata_routes as _register_metadata_routes
from taskfile.api.routes_doctor import register_doctor_routes as _register_doctor_routes

# Backward-compat re-exports for any code that imported helpers from app.py
from taskfile.api.routes_helpers import _load_config, _config_to_info  # noqa: F401


def create_app(taskfile_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Taskfile API",
        description=(
            "REST API for executing and managing Taskfile tasks.\n\n"
            "Provides endpoints to:\n"
            "- **List** tasks, environments, platforms, and functions\n"
            "- **Run** tasks with environment/platform/variable overrides\n"
            "- **Validate** Taskfile configuration\n"
            "- **Diagnose** project health (`/doctor`)\n"
            "- **Inspect** full Taskfile metadata\n\n"
            "Start the server:\n"
            "```bash\n"
            "taskfile api serve\n"
            "# or\n"
            "uvicorn taskfile.api:app --reload --port 8000\n"
            "```\n\n"
            "Interactive docs: [Swagger UI](/docs) | [ReDoc](/redoc)"
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        responses={
            404: {"model": ErrorResponse, "description": "Taskfile not found"},
            422: {"model": ErrorResponse, "description": "Taskfile parse error"},
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.taskfile_path = taskfile_path

    _register_health_routes(app)
    _register_taskfile_routes(app)
    _register_task_routes(app)
    _register_run_routes(app)
    _register_metadata_routes(app)
    _register_doctor_routes(app)

    return app
