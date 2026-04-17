"""Environments, groups, platforms, functions, and pipeline endpoints."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from taskfile.api.models import (
    EnvironmentGroupInfo,
    EnvironmentInfo,
    FunctionInfo,
    PipelineStageInfo,
    PlatformInfo,
)
from taskfile.api.routes_helpers import _load_config


def register_metadata_routes(app: FastAPI) -> None:
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
