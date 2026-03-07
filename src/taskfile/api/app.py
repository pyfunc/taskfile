"""FastAPI application factory for the Taskfile REST API."""

from __future__ import annotations

import io
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from taskfile import __version__
from taskfile.api.models import (
    DoctorIssueInfo,
    DoctorRequest,
    DoctorResponse,
    EnvironmentGroupInfo,
    EnvironmentInfo,
    ErrorResponse,
    FunctionInfo,
    HealthResponse,
    PipelineStageInfo,
    PlatformInfo,
    RunResult,
    RunTaskRequest,
    TaskfileInfo,
    TaskInfo,
    TaskRunResult,
    TaskStatus,
    ValidateRequest,
    ValidationResult,
)
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    find_taskfile,
    load_taskfile,
    validate_taskfile,
)


def _load_config(taskfile_path: str | None = None):
    """Load Taskfile config, raising HTTPException on errors."""
    try:
        return load_taskfile(taskfile_path)
    except TaskfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TaskfileParseError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _config_to_info(config) -> TaskfileInfo:
    """Convert TaskfileConfig to TaskfileInfo response model."""
    return TaskfileInfo(
        version=config.version,
        name=config.name,
        description=config.description,
        default_env=config.default_env,
        default_platform=config.default_platform,
        variables=config.variables,
        environments=[
            EnvironmentInfo(
                name=env.name,
                ssh_host=env.ssh_host,
                ssh_user=env.ssh_user,
                ssh_port=env.ssh_port,
                container_runtime=env.container_runtime,
                compose_command=env.compose_command,
                service_manager=env.service_manager,
                env_file=env.env_file,
                is_remote=env.is_remote,
            )
            for env in config.environments.values()
        ],
        environment_groups=[
            EnvironmentGroupInfo(
                name=g.name,
                members=g.members,
                strategy=g.strategy,
                max_parallel=g.max_parallel,
                canary_count=g.canary_count,
            )
            for g in config.environment_groups.values()
        ],
        platforms=[
            PlatformInfo(
                name=p.name,
                description=p.description,
                build_cmd=p.build_cmd,
                deploy_cmd=p.deploy_cmd,
                variables=p.variables,
            )
            for p in config.platforms.values()
        ],
        tasks=[
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
            for t in config.tasks.values()
        ],
        functions=[
            FunctionInfo(
                name=f.name,
                lang=f.lang,
                description=f.description,
                has_code=bool(f.code),
                has_file=bool(f.file),
            )
            for f in config.functions.values()
        ],
        pipeline_stages=[
            PipelineStageInfo(
                name=s.name,
                tasks=s.tasks,
                env=s.env,
                when=s.when,
            )
            for s in config.pipeline.stages
        ],
    )


def _register_health_routes(app: FastAPI) -> None:
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


def _register_taskfile_routes(app: FastAPI) -> None:
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
        import json
        schema_path = Path(__file__).parent.parent.parent.parent / "docs" / "schema" / "taskfile.schema.json"
        if not schema_path.is_file():
            raise HTTPException(status_code=404, detail="Schema file not found")
        return json.loads(schema_path.read_text())


def _register_task_routes(app: FastAPI) -> None:
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
            tasks.append(TaskInfo(
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
            ))
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


def _register_run_routes(app: FastAPI) -> None:
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

                    task_results.append(TaskRunResult(
                        task=task_name,
                        status=TaskStatus.success if success else TaskStatus.failed,
                        duration_ms=duration_ms,
                        output=output_lines,
                        error=error_text if not success else None,
                    ))

                    if not success:
                        break

                except Exception as exc:
                    duration_ms = int((time.time() - task_start) * 1000)
                    task_results.append(TaskRunResult(
                        task=task_name,
                        status=TaskStatus.failed,
                        duration_ms=duration_ms,
                        error=str(exc),
                    ))
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


def _register_metadata_routes(app: FastAPI) -> None:
    """Register environments, groups, platforms, functions, pipeline endpoints."""

    @app.get(
        "/environments",
        response_model=list[EnvironmentInfo],
        tags=["environments"],
        summary="List environments",
    )
    def list_environments():
        """List all defined environments."""
        config = _load_config(app.state.taskfile_path)
        return [
            EnvironmentInfo(
                name=env.name,
                ssh_host=env.ssh_host,
                ssh_user=env.ssh_user,
                ssh_port=env.ssh_port,
                container_runtime=env.container_runtime,
                compose_command=env.compose_command,
                service_manager=env.service_manager,
                env_file=env.env_file,
                is_remote=env.is_remote,
            )
            for env in config.environments.values()
        ]

    @app.get(
        "/environments/{env_name}",
        response_model=EnvironmentInfo,
        tags=["environments"],
        summary="Get environment details",
    )
    def get_environment(env_name: str):
        """Get detailed information about a specific environment."""
        config = _load_config(app.state.taskfile_path)
        if env_name not in config.environments:
            raise HTTPException(
                status_code=404,
                detail=f"Environment '{env_name}' not found. Available: {', '.join(sorted(config.environments.keys()))}",
            )
        env = config.environments[env_name]
        return EnvironmentInfo(
            name=env.name,
            ssh_host=env.ssh_host,
            ssh_user=env.ssh_user,
            ssh_port=env.ssh_port,
            container_runtime=env.container_runtime,
            compose_command=env.compose_command,
            service_manager=env.service_manager,
            env_file=env.env_file,
            is_remote=env.is_remote,
        )

    @app.get(
        "/groups",
        response_model=list[EnvironmentGroupInfo],
        tags=["environments"],
        summary="List environment groups",
    )
    def list_groups():
        """List all environment groups (fleet definitions)."""
        config = _load_config(app.state.taskfile_path)
        return [
            EnvironmentGroupInfo(
                name=g.name,
                members=g.members,
                strategy=g.strategy,
                max_parallel=g.max_parallel,
                canary_count=g.canary_count,
            )
            for g in config.environment_groups.values()
        ]

    @app.get(
        "/platforms",
        response_model=list[PlatformInfo],
        tags=["platforms"],
        summary="List platforms",
    )
    def list_platforms():
        """List all defined platforms."""
        config = _load_config(app.state.taskfile_path)
        return [
            PlatformInfo(
                name=p.name,
                description=p.description,
                build_cmd=p.build_cmd,
                deploy_cmd=p.deploy_cmd,
                variables=p.variables,
            )
            for p in config.platforms.values()
        ]

    @app.get(
        "/functions",
        response_model=list[FunctionInfo],
        tags=["functions"],
        summary="List embedded functions",
    )
    def list_functions():
        """List all embedded functions defined in the Taskfile."""
        config = _load_config(app.state.taskfile_path)
        return [
            FunctionInfo(
                name=f.name,
                lang=f.lang,
                description=f.description,
                has_code=bool(f.code),
                has_file=bool(f.file),
            )
            for f in config.functions.values()
        ]

    @app.get(
        "/pipeline",
        response_model=list[PipelineStageInfo],
        tags=["pipeline"],
        summary="List pipeline stages",
    )
    def list_pipeline_stages():
        """List CI/CD pipeline stages."""
        config = _load_config(app.state.taskfile_path)
        return [
            PipelineStageInfo(
                name=s.name,
                tasks=s.tasks,
                env=s.env,
                when=s.when,
            )
            for s in config.pipeline.stages
        ]


def _register_doctor_routes(app: FastAPI) -> None:
    """Register /doctor diagnostics endpoint."""

    @app.get(
        "/doctor",
        response_model=DoctorResponse,
        tags=["diagnostics"],
        summary="Run doctor diagnostics (GET — read-only)",
    )
    def doctor_get(
        verbose: bool = Query(False, description="Run extra checks (task commands, SSH, remote health)"),
        category: str = Query("all", description="Filter: config, env, infra, runtime, or all"),
    ):
        """Run 5-layer diagnostics (read-only, no fixes applied).

        Same as `taskfile doctor --report` but over HTTP.
        """
        return _run_doctor(app, fix=False, verbose=verbose, category=category, llm=False)

    @app.post(
        "/doctor",
        response_model=DoctorResponse,
        tags=["diagnostics"],
        summary="Run doctor diagnostics with options",
    )
    def doctor_post(request: DoctorRequest):
        """Run 5-layer diagnostics with optional auto-fix and LLM assist.

        - **fix**: Apply Layer 4 algorithmic fixes
        - **verbose**: Extra checks (task commands, SSH connectivity, remote health)
        - **llm**: Ask AI for suggestions on unresolved issues (Layer 5)
        - **category**: Filter by issue category
        """
        return _run_doctor(
            app,
            fix=request.fix,
            verbose=request.verbose,
            category=request.category,
            llm=request.llm,
        )


def _run_doctor(
    app: FastAPI,
    *,
    fix: bool = False,
    verbose: bool = False,
    category: str = "all",
    llm: bool = False,
) -> DoctorResponse:
    """Shared doctor logic for GET and POST endpoints."""
    from taskfile.diagnostics import ProjectDiagnostics

    diagnostics = ProjectDiagnostics()

    diagnostics.run_all_checks(verbose=verbose)

    # Layer 4: Auto-fix
    fixed_count = 0
    if fix and diagnostics.issues:
        fixed_count = diagnostics.auto_fix()

    # Layer 5: LLM assist
    llm_suggestions: list[str] = []
    if llm and diagnostics._issues:
        try:
            llm_suggestions = diagnostics.llm_repair()
        except Exception:
            pass

    # Filter by category if requested
    CATEGORY_FILTER = {
        "config": {"config_error", "taskfile_bug"},
        "env": {"dependency_missing"},
        "infra": {"external_error"},
        "runtime": {"runtime_error"},
    }
    issues = diagnostics._issues
    if category != "all" and category in CATEGORY_FILTER:
        allowed = CATEGORY_FILTER[category]
        issues = [i for i in issues if i.category.value in allowed]

    # Build response
    issue_infos = []
    categories: dict[str, list[DoctorIssueInfo]] = {}
    for iss in issues:
        info = DoctorIssueInfo(
            category=iss.category.value,
            message=iss.message,
            severity=iss.severity,
            fix_strategy=iss.fix_strategy.value,
            auto_fixable=iss.auto_fixable,
            layer=iss.layer,
            fix_command=iss.fix_command,
            fix_description=iss.fix_description,
            teach=iss.teach,
            context={k: v for k, v in iss.context.items() if not k.startswith("_")} if iss.context else None,
        )
        issue_infos.append(info)
        categories.setdefault(iss.category.value, []).append(info)

    error_count = sum(1 for i in issues if i.severity == "error")
    warn_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")
    fixable = sum(1 for i in issues if i.auto_fixable)

    parts = []
    if error_count:
        parts.append(f"Errors: {error_count}")
    if warn_count:
        parts.append(f"Warnings: {warn_count}")
    if info_count:
        parts.append(f"Info: {info_count}")
    if fixed_count:
        parts.append(f"Fixed: {fixed_count}")
    summary = ", ".join(parts) if parts else "No issues found"

    return DoctorResponse(
        total_issues=len(issue_infos),
        errors=error_count,
        warnings=warn_count,
        info=info_count,
        auto_fixable=fixable,
        fixed_count=fixed_count,
        healthy=error_count == 0,
        issues=issue_infos,
        categories=categories,
        llm_suggestions=llm_suggestions,
        summary=summary,
    )


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
