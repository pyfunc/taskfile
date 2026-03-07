"""Data models for Taskfile configuration.

Split into submodules for maintainability:
    environment.py — Environment, Platform, EnvironmentGroup
    task.py        — Task, Function, _normalize_commands
    pipeline.py    — PipelineStage, PipelineConfig
    config.py      — TaskfileConfig, ComposeConfig

All public symbols are re-exported here for backward compatibility.
Existing `from taskfile.models import X` imports continue to work.
"""

from taskfile.models.environment import Environment, Platform, EnvironmentGroup
from taskfile.models.task import Task, Function, _normalize_commands
from taskfile.models.pipeline import PipelineStage, PipelineConfig
from taskfile.models.config import TaskfileConfig, ComposeConfig

__all__ = [
    "Environment",
    "Platform",
    "EnvironmentGroup",
    "Task",
    "Function",
    "_normalize_commands",
    "PipelineStage",
    "PipelineConfig",
    "TaskfileConfig",
    "ComposeConfig",
]
