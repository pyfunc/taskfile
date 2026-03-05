"""Core task runner package — executes tasks with variable substitution, SSH, dependencies.

This package was split from runner.py for maintainability.
All public symbols are re-exported here for backward compatibility.
"""

from taskfile.runner.core import TaskfileRunner, TaskRunError
from taskfile.runner.resolver import TaskResolver

__all__ = ["TaskfileRunner", "TaskRunError", "TaskResolver"]
