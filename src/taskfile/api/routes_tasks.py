"""Task list and detail endpoints."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from taskfile.api.models import TaskInfo
from taskfile.api.routes_helpers import _load_config


def register_task_routes(app: FastAPI) -> None:
    """Register task list and detail endpoints."""

    @app.get(
        "/tasks",
        response_model=list[TaskInfo],
        tags=["tasks"],
        summary="List all tasks",
    )
    def list_tasks(
        env: str | None = Query(None, description="Filter by environment"),
        platform: str | None = Query(None, description="Filter by platform"),
        tag: str | None = Query(None, description="Filter by tag"),
    ):
        """List all tasks with optional filtering by environment, platform, or tag."""
        config = _load_config(app.state.taskfile_path)
        tasks = []
        for t in config.tasks.values():
            if env and t.env_filter and env not in t.env_filter:
                continue
            if platform and t.platform_filter and platform not in t.platform_filter:
                continue
            if tag and (not t.tags or tag not in t.tags):
                continue
            tasks.append(
                TaskInfo(
                    name=t.name,
                    description=t.description,
                    commands=t.commands,
                    deps=t.deps,
                    env_filter=t.env_filter,
                    platform_filter=t.platform_filter,
                    tags=t.tags,
                    stage=t.stage,
                    retries=t.retries,
                    timeout=t.timeout,
                    has_condition=bool(t.condition),
                )
            )
        return tasks

    @app.get(
        "/tasks/{task_name}",
        response_model=TaskInfo,
        tags=["tasks"],
        summary="Get task details",
    )
    def get_task(task_name: str):
        """Get detailed information about a specific task."""
        config = _load_config(app.state.taskfile_path)
        if task_name not in config.tasks:
            raise HTTPException(
                status_code=404,
                detail=f"Task '{task_name}' not found. Available: {', '.join(sorted(config.tasks.keys()))}",
            )
        t = config.tasks[task_name]
        return TaskInfo(
            name=t.name,
            description=t.description,
            commands=t.commands,
            deps=t.deps,
            env_filter=t.env_filter,
            platform_filter=t.platform_filter,
            tags=t.tags,
            stage=t.stage,
            retries=t.retries,
            timeout=t.timeout,
            has_condition=bool(t.condition),
        )
