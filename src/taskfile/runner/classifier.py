"""Command classifier — categorize commands before processing.

Principle: Classify before process. Each command type gets its own
processing pipeline, avoiding shlex.split on shell constructs.

Command types:
    SHELL_CONSTRUCT  — for/while/if/case, subshells, pipes with semicolons
    FN_CALL          — @fn function_name args
    PYTHON_INLINE    — @python code
    REMOTE_CMD       — @remote/@ssh commands
    LOCAL_CMD        — @local commands
    PUSH_CMD         — @push file transfers
    PULL_CMD         — @pull file transfers
    MULTILINE        — commands containing newlines (heredocs, scripts)
    PLAIN_CMD        — simple commands safe for glob expansion
"""

from __future__ import annotations

import re
from enum import Enum


class CommandType(str, Enum):
    """Classification of a command string for routing to the correct pipeline."""

    SHELL_CONSTRUCT = "shell_construct"
    FN_CALL = "fn_call"
    PYTHON_INLINE = "python_inline"
    REMOTE_CMD = "remote_cmd"
    LOCAL_CMD = "local_cmd"
    PUSH_CMD = "push_cmd"
    PULL_CMD = "pull_cmd"
    MULTILINE = "multiline"
    PLAIN_CMD = "plain_cmd"


# Shell construct keywords that start compound statements.
# These must NOT be passed through shlex.split as it mangles semicolons/structure.
_SHELL_CONSTRUCT_PREFIXES = (
    "for ",
    "for(",
    "while ",
    "while(",
    "if ",
    "if[",
    "if(",
    "case ",
    "until ",
    "select ",
    "{ ",
    "(",
)

# Patterns indicating shell constructs even mid-command
# e.g., "VAR=x; for f in *.txt; do ..." or "cd dir && for ..."
_SHELL_CONSTRUCT_RE = re.compile(
    r"(?:^|[;&|]\s*)"  # start of string or after ; & |
    r"(?:for|while|if|case|until|select)\s",
    re.MULTILINE,
)

# Subshell / brace group patterns: $(...), (...), { ...; }
_SUBSHELL_RE = re.compile(r"(?:\$\(|^\(|;\s*\{)")

# Commands with inline semicolons that aren't just command separators
# but part of shell syntax (for...do...done, if...then...fi)
_SHELL_KEYWORDS_RE = re.compile(r"\b(?:do|done|then|else|elif|fi|esac|in)\b")


# Dispatch table for @-prefixed commands — O(n) scan but tiny n.
_PREFIX_DISPATCH: tuple[tuple[str, CommandType], ...] = (
    ("@fn ", CommandType.FN_CALL),
    ("@python ", CommandType.PYTHON_INLINE),
    ("@remote ", CommandType.REMOTE_CMD),
    ("@ssh ", CommandType.REMOTE_CMD),
    ("@local ", CommandType.LOCAL_CMD),
    ("@push ", CommandType.PUSH_CMD),
    ("@pull ", CommandType.PULL_CMD),
)


def classify_command(cmd: str) -> CommandType:
    """Classify a command string to determine its processing pipeline.

    This is the central routing decision — called before any parsing.
    The classification uses simple, fast heuristics (no shlex needed).

    Args:
        cmd: Raw command string (after variable expansion)

    Returns:
        CommandType indicating which pipeline should handle this command
    """
    stripped = cmd.strip()

    if "\n" in stripped:
        return CommandType.MULTILINE

    for prefix, ctype in _PREFIX_DISPATCH:
        if stripped.startswith(prefix):
            return ctype

    if _is_shell_construct(stripped):
        return CommandType.SHELL_CONSTRUCT

    return CommandType.PLAIN_CMD


def _is_shell_construct(stripped: str) -> bool:
    """Detect shell compound statements that shlex.split would mangle."""
    lower = stripped.lower()
    for prefix in _SHELL_CONSTRUCT_PREFIXES:
        if lower.startswith(prefix):
            return True
    if _SHELL_CONSTRUCT_RE.search(stripped):
        return True
    if _SUBSHELL_RE.search(stripped):
        return True
    if ";" in stripped and _SHELL_KEYWORDS_RE.search(stripped):
        return True
    return False


def should_expand_globs(cmd: str) -> bool:
    """Determine if a command is safe for glob expansion via shlex.split.

    Only PLAIN_CMD types should have their glob patterns expanded.
    All other types risk mangling by shlex.split.

    Args:
        cmd: Raw command string

    Returns:
        True if glob expansion is safe for this command
    """
    return classify_command(cmd) == CommandType.PLAIN_CMD


def has_glob_pattern(cmd: str) -> bool:
    """Quick check if a command string contains any glob characters.

    Args:
        cmd: Command string to check

    Returns:
        True if the command contains *, ?, or [ characters
    """
    return bool("*" in cmd or "?" in cmd or "[" in cmd)
