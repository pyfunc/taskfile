"""
taskfile — Universal Taskfile runner with multi-environment deploy support.

CI/CD agnostic: run the same tasks locally, from GitLab CI, GitHub Actions,
Gitea, Jenkins, or any other pipeline.

Features:
    - Multi-environment deploy (local/staging/prod)
    - CI/CD config generator (GitHub, GitLab, Gitea, Drone, Jenkins, Makefile)
    - Local pipeline runner (replaces act/gitlab-runner exec)
    - Docker Compose → Podman Quadlet conversion
    - @remote SSH command execution
"""

__version__ = "0.3.65"
__author__ = "Softreck"

from taskfile.runner import TaskfileRunner
from taskfile.models import Task, Environment, TaskfileConfig, PipelineConfig, PipelineStage
from taskfile.compose import ComposeFile
from taskfile.quadlet import compose_to_quadlet, generate_container_unit
from taskfile.cigen import generate_ci, generate_all_ci, preview_ci
from taskfile.cirunner import PipelineRunner

__all__ = [
    "TaskfileRunner",
    "Task",
    "Environment",
    "TaskfileConfig",
    "PipelineConfig",
    "PipelineStage",
    "ComposeFile",
    "compose_to_quadlet",
    "generate_container_unit",
    "generate_ci",
    "generate_all_ci",
    "preview_ci",
    "PipelineRunner",
]
