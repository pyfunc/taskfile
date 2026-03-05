"""Taskfile REST API — FastAPI service for executing tasks over HTTP.

Start with:
    taskfile api serve
    # or directly:
    uvicorn taskfile.api:app --reload --port 8000
"""

from taskfile.api.app import create_app

app = create_app()

__all__ = ["app", "create_app"]
