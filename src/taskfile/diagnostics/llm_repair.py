"""Layer 5: LLM repair — escalate unresolved issues to AI via litellm.

Optional dependency: `pip install taskfile[llm]` to enable.
Falls back gracefully when litellm is not installed.
"""

from __future__ import annotations

import json

from taskfile.diagnostics.models import (
    Issue,
    IssueCategory,
    FixStrategy,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)
from taskfile.diagnostics.fixop_adapter import HAS_FIXOP as _HAS_FIXOP

try:
    from fixop.classify import classify_error as _fixop_classify
except ImportError:
    pass


def is_available() -> bool:
    """Check if litellm is installed."""
    try:
        import litellm  # noqa: F401
        return True
    except ImportError:
        return False


def ask_llm_for_fix(issue: Issue, project_context: dict | None = None) -> str | None:
    """Ask LLM for a fix suggestion via litellm.

    Returns suggestion string or None if litellm unavailable or call fails.
    """
    try:
        import litellm
    except ImportError:
        return None

    ctx = project_context or {}
    prompt = f"""You are diagnosing a taskfile project issue.

Issue category: {issue.category.value}
Issue message: {issue.message}
Context: {json.dumps(issue.context or {}, indent=2, default=str)}

Project info:
- Name: {ctx.get('name', 'unknown')}
- Version: {ctx.get('version', '1')}
- Environments: {ctx.get('environments', [])}
- Tasks count: {len(ctx.get('tasks', []))}
- Platform: {ctx.get('platform', 'linux')}

Provide a concise fix (max 3 steps). If it's a command, prefix with $.
If it requires manual action, explain what to do.
If it might be a taskfile bug, say so explicitly."""

    model = ctx.get("llm_model", "gpt-4o-mini")

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def classify_runtime_error(
    exit_code: int,
    stderr: str,
    cmd: str,
) -> Issue:
    """After a task command fails — classify whether it's a taskfile bug or app issue.

    Called by runner/commands.py when a command returns non-zero.
    Delegates to fixop.classify when available for better dispatch-table classification.
    """
    if _HAS_FIXOP:
        from taskfile.diagnostics.fixop_adapter import adapt_issue
        fi = _fixop_classify(exit_code, stderr, cmd)
        issue = adapt_issue(fi)
        # Override: unfixable runtime errors escalate to LLM, not MANUAL
        if not fi.fix_command:
            issue.fix_strategy = FixStrategy.LLM
        issue.context = {"exit_code": exit_code, "cmd": cmd, "stderr": stderr[:500]}
        return issue

    # Fallback when fixop is not installed
    return _classify_runtime_error_legacy(exit_code, stderr, cmd)


def _classify_runtime_error_legacy(
    exit_code: int,
    stderr: str,
    cmd: str,
) -> Issue:
    """Legacy classification — used when fixop is not available."""
    stderr_lower = stderr.lower()

    if "command not found" in stderr_lower:
        binary = _extract_missing_binary(stderr)
        return Issue(
            category=IssueCategory.DEPENDENCY_MISSING,
            message=f"Command '{binary}' not found",
            fix_strategy=FixStrategy.LLM,
            severity=SEVERITY_ERROR,
            context={"binary": binary, "stderr": stderr[:200], "cmd": cmd},
            layer=3,
        )

    if "permission denied" in stderr_lower:
        return Issue(
            category=IssueCategory.CONFIG_ERROR,
            message=f"Permission denied running: {cmd[:80]}",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_ERROR,
            fix_command=f"chmod +x {cmd.split()[0]}" if not cmd.startswith("@") else None,
            context={"cmd": cmd, "stderr": stderr[:200]},
            layer=3,
        )

    if "connection refused" in stderr_lower or "no route to host" in stderr_lower:
        return Issue(
            category=IssueCategory.EXTERNAL_ERROR,
            message=f"Network error: {stderr[:100]}",
            fix_strategy=FixStrategy.LLM,
            severity=SEVERITY_ERROR,
            context={"cmd": cmd, "stderr": stderr[:300]},
            layer=3,
        )

    if exit_code == 137:  # SIGKILL / OOM
        return Issue(
            category=IssueCategory.EXTERNAL_ERROR,
            message=f"Process killed (OOM?): {cmd[:80]}",
            fix_strategy=FixStrategy.LLM,
            severity=SEVERITY_ERROR,
            fix_description="Check system resources — process was killed (possibly out of memory)",
            context={"exit_code": exit_code, "cmd": cmd},
            layer=3,
        )

    if exit_code == 124:  # timeout
        return Issue(
            category=IssueCategory.EXTERNAL_ERROR,
            message=f"Command timed out: {cmd[:80]}",
            fix_strategy=FixStrategy.MANUAL,
            severity=SEVERITY_ERROR,
            fix_description="Increase timeout or check network connectivity",
            context={"exit_code": exit_code, "cmd": cmd},
            layer=3,
        )

    if exit_code == 126:  # not executable
        return Issue(
            category=IssueCategory.CONFIG_ERROR,
            message=f"Not executable: {cmd[:80]}",
            fix_strategy=FixStrategy.CONFIRM,
            severity=SEVERITY_ERROR,
            fix_command=f"chmod +x {cmd.split()[0]}" if " " in cmd else None,
            context={"exit_code": exit_code, "cmd": cmd},
            layer=3,
        )

    if exit_code == 127:  # command not found (no stderr parse needed)
        binary = cmd.split()[0] if cmd else "unknown"
        return Issue(
            category=IssueCategory.DEPENDENCY_MISSING,
            message=f"Command not found: {binary}",
            fix_strategy=FixStrategy.LLM,
            severity=SEVERITY_ERROR,
            context={"binary": binary, "cmd": cmd},
            layer=3,
        )

    # Default: runtime error in the software taskfile runs
    return Issue(
        category=IssueCategory.RUNTIME_ERROR,
        message=f"Task failed (exit {exit_code}): {stderr[:100] if stderr else cmd[:80]}",
        fix_strategy=FixStrategy.LLM,
        severity=SEVERITY_ERROR,
        context={"exit_code": exit_code, "cmd": cmd, "stderr": stderr[:500]},
        layer=3,
    )


def _extract_missing_binary(stderr: str) -> str:
    """Extract binary name from 'command not found' stderr."""
    for line in stderr.splitlines():
        if "command not found" in line.lower():
            # "bash: foo: command not found" or "foo: command not found"
            parts = line.split(":")
            if len(parts) >= 2:
                return parts[-2].strip()
    return "unknown"
