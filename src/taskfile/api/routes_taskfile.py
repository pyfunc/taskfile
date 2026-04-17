"""Taskfile info, validate, variables, and schema endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from taskfile.api.models import (
    TaskfileInfo,
    ValidateRequest,
    ValidationResult,
)
from taskfile.api.routes_helpers import _load_config, _config_to_info
from taskfile.parser import validate_taskfile


def register_taskfile_routes(app: FastAPI) -> None:
    """Register taskfile info, validate, variables, and schema endpoints."""

    @app.get(
        "/taskfile",
        response_model=TaskfileInfo,
        tags=["taskfile"],
        summary="Get full Taskfile configuration",
    )
    def get_taskfile(
        path: str | None = Query(None, description="Path to Taskfile.yml"),
    ):
        """Return the full parsed Taskfile configuration as JSON."""
        config = _load_config(path or app.state.taskfile_path)
        return _config_to_info(config)

    @app.post(
        "/validate",
        response_model=ValidationResult,
        tags=["taskfile"],
        summary="Validate Taskfile",
    )
    def validate_taskfile_endpoint(request: ValidateRequest):
        """Validate a Taskfile and return warnings."""
        config = _load_config(request.path or app.state.taskfile_path)
        warnings = validate_taskfile(config)
        return ValidationResult(
            valid=True,
            warnings=warnings,
            task_count=len(config.tasks),
            env_count=len(config.environments),
        )

    @app.get(
        "/variables",
        response_model=dict[str, str],
        tags=["taskfile"],
        summary="List global variables",
    )
    def list_variables():
        """List all global variables defined in the Taskfile."""
        config = _load_config(app.state.taskfile_path)
        return config.variables

    @app.get(
        "/schema",
        tags=["taskfile"],
        summary="Get Taskfile JSON Schema",
    )
    def get_schema():
        """Return the JSON Schema for Taskfile.yml format."""
        schema_path = Path(__file__).parent.parent.parent.parent / "docs" / "schema" / "taskfile.schema.json"
        if not schema_path.is_file():
            raise HTTPException(status_code=404, detail="Schema file not found")
        return json.loads(schema_path.read_text())
