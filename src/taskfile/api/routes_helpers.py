"""Shared helpers for API route modules."""

from __future__ import annotations

from fastapi import HTTPException

from taskfile.api.models import (
    EnvironmentGroupInfo,
    EnvironmentInfo,
    FunctionInfo,
    PipelineStageInfo,
    PlatformInfo,
    TaskfileInfo,
    TaskInfo,
)
from taskfile.parser import (
    TaskfileNotFoundError,
    TaskfileParseError,
    load_taskfile,
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
