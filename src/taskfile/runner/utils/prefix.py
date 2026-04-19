"""Command prefix detection and stripping utilities."""

from __future__ import annotations


def has_prefix(cmd: str, prefix: str) -> bool:
    """Check if command starts with given prefix (followed by space)."""
    return cmd.strip().startswith(f"{prefix} ")


def strip_prefix(cmd: str, prefix: str) -> str:
    """Remove prefix and following space from command if present."""
    stripped = cmd.strip()
    prefix_with_space = f"{prefix} "
    if stripped.startswith(prefix_with_space):
        return stripped[len(prefix_with_space) :]
    return stripped


def has_any_prefix(cmd: str, prefixes: list[str]) -> bool:
    """Check if command starts with any of the given prefixes."""
    stripped = cmd.strip()
    for prefix in prefixes:
        if stripped.startswith(f"{prefix} "):
            return True
    return False


def strip_any_prefix(cmd: str, prefixes: list[str]) -> str:
    """Remove the first matching prefix from command."""
    stripped = cmd.strip()
    for prefix in prefixes:
        prefix_with_space = f"{prefix} "
        if stripped.startswith(prefix_with_space):
            return stripped[len(prefix_with_space) :]
    return stripped
