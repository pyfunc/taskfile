"""Pydantic models for the Taskfile REST API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────

class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class DeployStrategy(str, Enum):
    rolling = "rolling"
    canary = "canary"
    parallel = "parallel"


# ─── Request models ──────────────────────────────────

class RunTaskRequest(BaseModel):
    """Request to run one or more tasks."""
    tasks: list[str] = Field(..., min_length=1, description="Task names to execute")
    env: str = Field("local", description="Target environment")
    platform: str | None = Field(None, description="Target platform")
    variables: dict[str, str] = Field(default_factory=dict, description="Variable overrides (KEY=VALUE)")
    dry_run: bool = Field(False, description="Show commands without executing")
    tags: list[str] | None = Field(None, description="Filter tasks by tags")

    model_config = {"json_schema_extra": {
        "examples": [
            {"tasks": ["build", "deploy"], "env": "prod", "variables": {"TAG": "v1.2.3"}},
            {"tasks": ["test"], "dry_run": True},
        ]
    }}


class ValidateRequest(BaseModel):
    """Request to validate a Taskfile."""
    path: str | None = Field(None, description="Path to Taskfile.yml (auto-detect if null)")


# ─── Response models ─────────────────────────────────

class TaskInfo(BaseModel):
    """Single task metadata."""
    name: str
    description: str = ""
    commands: list[str] = []
    deps: list[str] = []
    env_filter: list[str] | None = None
    platform_filter: list[str] | None = None
    tags: list[str] = []
    stage: str | None = None
    retries: int = 0
    timeout: int = 0
    has_condition: bool = False


class EnvironmentInfo(BaseModel):
    """Single environment metadata."""
    name: str
    ssh_host: str | None = None
    ssh_user: str = "deploy"
    ssh_port: int = 22
    container_runtime: str = "docker"
    compose_command: str = "docker compose"
    service_manager: str = "compose"
    env_file: str | None = None
    is_remote: bool = False


class EnvironmentGroupInfo(BaseModel):
    """Environment group metadata."""
    name: str
    members: list[str] = []
    strategy: str = "parallel"
    max_parallel: int = 5
    canary_count: int = 1


class PlatformInfo(BaseModel):
    """Platform metadata."""
    name: str
    description: str = ""
    build_cmd: str | None = None
    deploy_cmd: str | None = None
    variables: dict[str, str] = {}


class FunctionInfo(BaseModel):
    """Embedded function metadata."""
    name: str
    lang: str = "shell"
    description: str = ""
    has_code: bool = False
    has_file: bool = False


class PipelineStageInfo(BaseModel):
    """Pipeline stage metadata."""
    name: str
    tasks: list[str] = []
    env: str | None = None
    when: str = "auto"


class TaskfileInfo(BaseModel):
    """Full Taskfile configuration metadata."""
    version: str = "1"
    name: str = ""
    description: str = ""
    default_env: str = "local"
    default_platform: str | None = None
    variables: dict[str, str] = {}
    environments: list[EnvironmentInfo] = []
    environment_groups: list[EnvironmentGroupInfo] = []
    platforms: list[PlatformInfo] = []
    tasks: list[TaskInfo] = []
    functions: list[FunctionInfo] = []
    pipeline_stages: list[PipelineStageInfo] = []


class ValidationResult(BaseModel):
    """Taskfile validation result."""
    valid: bool
    warnings: list[str] = []
    task_count: int = 0
    env_count: int = 0


class CommandOutput(BaseModel):
    """Output line from a running task."""
    timestamp: datetime
    task: str
    stream: str = "stdout"  # stdout | stderr
    line: str


class TaskRunResult(BaseModel):
    """Result of a single task execution."""
    task: str
    status: TaskStatus
    duration_ms: int = 0
    output: list[str] = []
    error: str | None = None


class RunResult(BaseModel):
    """Result of a task run request."""
    success: bool
    tasks: list[TaskRunResult] = []
    total_duration_ms: int = 0
    env: str = "local"
    dry_run: bool = False


class HealthResponse(BaseModel):
    """API health check response."""
    status: str = "ok"
    version: str
    taskfile_found: bool
    taskfile_path: str | None = None
    task_count: int = 0
    env_count: int = 0


class DoctorIssueInfo(BaseModel):
    """Single diagnostic issue from doctor."""
    category: str
    message: str
    severity: str = "warning"
    fix_strategy: str = "manual"
    auto_fixable: bool = False
    layer: int = 3
    fix_command: str | None = None
    fix_description: str | None = None
    teach: str | None = None
    context: dict[str, Any] | None = None


class DoctorRequest(BaseModel):
    """Request options for the doctor endpoint."""
    fix: bool = Field(False, description="Auto-fix issues where possible (Layer 4)")
    verbose: bool = Field(False, description="Run extra checks (task commands, SSH connectivity, remote health)")
    category: str = Field("all", description="Filter by category: config, env, infra, runtime, or all")
    examples: bool = Field(False, description="Validate examples/ directories")
    llm: bool = Field(False, description="Ask AI for suggestions on unresolved issues (Layer 5)")

    model_config = {"json_schema_extra": {
        "examples": [
            {"fix": False, "verbose": False, "category": "all"},
            {"fix": True, "llm": True},
        ]
    }}


class DoctorResponse(BaseModel):
    """Full doctor diagnostics result."""
    total_issues: int = 0
    errors: int = 0
    warnings: int = 0
    info: int = 0
    auto_fixable: int = 0
    fixed_count: int = 0
    healthy: bool = True
    issues: list[DoctorIssueInfo] = []
    categories: dict[str, list[DoctorIssueInfo]] = {}
    llm_suggestions: list[str] = []
    summary: str = "No issues found"


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str | None = None
