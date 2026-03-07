"""Task and Function data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Function:
    """Embedded function callable from tasks via @fn prefix."""

    name: str
    lang: str = "shell"  # shell | python | node | binary
    code: str | None = None  # inline code
    file: str | None = None  # external file path
    function: str | None = None  # specific function to call (Python)
    description: str = ""


@dataclass
class Task:
    """Single task definition."""

    name: str
    description: str = ""
    commands: list[str] = field(default_factory=list)
    script: str | None = None  # external script file path (alternative to inline cmds)
    deps: list[str] = field(default_factory=list)
    env_filter: list[str] | None = None
    platform_filter: list[str] | None = None
    working_dir: str | None = None
    silent: bool = False
    ignore_errors: bool = False
    condition: str | None = None
    stage: str | None = None  # pipeline stage this task belongs to
    parallel: bool = False  # run deps in parallel (concurrent execution)
    retries: int = 0  # retry count on failure (Ansible-inspired)
    retry_delay: int = 1  # seconds between retries
    timeout: int = 0  # command timeout in seconds (0 = no timeout)
    tags: list[str] = field(default_factory=list)  # tags for selective execution
    register: str | None = None  # capture stdout into this variable name

    def should_run_on(self, env_name: str) -> bool:
        if self.env_filter is None:
            return True
        return env_name in self.env_filter

    def should_run_on_platform(self, platform_name: str | None) -> bool:
        if self.platform_filter is None:
            return True
        if platform_name is None:
            return True
        return platform_name in self.platform_filter


def _normalize_commands(cmds: list) -> list[str]:
    """Normalize commands list — YAML can misparse 'echo key: value' as dicts."""
    result = []
    for item in cmds:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # YAML misparse: {'echo "  App': 'http://...'} → reconstruct
            for k, v in item.items():
                result.append(f"{k}: {v}" if v else str(k))
        else:
            result.append(str(item))
    return result
