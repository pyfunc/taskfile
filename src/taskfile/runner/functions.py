"""Function execution for task runner — @fn and @python command handlers."""

from __future__ import annotations

import os
import subprocess
import sys

from rich.console import Console

from taskfile.models import Task

console = Console()


def run_function(runner, cmd: str, task: Task) -> int:
    """Execute an embedded function defined in the functions section.

    Syntax: @fn <function_name> [args...]
    Functions are defined in the `functions` section of Taskfile.yml.
    """
    parts = cmd.strip()[4:].split(None, 1)  # strip "@fn "
    fn_name = parts[0] if parts else ""
    fn_args = parts[1] if len(parts) > 1 else ""

    fn = runner.config.functions.get(fn_name)
    if fn is None:
        console.print(f"  [red]✗ Unknown function: {fn_name}[/]")
        available = ", ".join(sorted(runner.config.functions.keys()))
        if available:
            console.print(f"  [dim]Available functions: {available}[/]")
        return 1

    if not task.silent:
        console.print(f"  [cyan]→ @fn {fn_name}[/] {fn_args}")

    if runner.dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return 0

    env = {**os.environ, **runner.variables, "FN_ARGS": fn_args}

    if fn.lang == "python":
        return _exec_function_python(fn, fn_args, env, task)
    elif fn.lang == "node":
        return _exec_function_node(fn, fn_args, env, task)
    elif fn.lang == "binary":
        return _exec_function_binary(fn, fn_args, env, task)
    else:
        # Default: shell
        return _exec_function_shell(fn, fn_args, env, task)


def _exec_function_shell(fn, fn_args: str, env: dict, task: Task) -> int:
    """Execute a shell function (inline code or file)."""
    if fn.file:
        actual_cmd = f"bash {fn.file} {fn_args}".strip()
    elif fn.code:
        actual_cmd = fn.code
    else:
        return 0
    result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
    return result.returncode


def _python_cmd() -> str:
    """Return the best available Python command (sys.executable or python3 fallback)."""
    return sys.executable or "python3"


def _exec_function_python(fn, fn_args: str, env: dict, task: Task) -> int:
    """Execute a Python function (inline code or file)."""
    py = _python_cmd()
    if fn.file:
        entry = f" -c \"import runpy; runpy.run_path('{fn.file}')\"" if not fn.function else f" {fn.file}"
        if fn.function:
            actual_cmd = f"{py} -c \"import importlib.util, sys; spec=importlib.util.spec_from_file_location('m','{fn.file}'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.{fn.function}({repr(fn_args)})\""
        else:
            actual_cmd = f"{py} {fn.file} {fn_args}".strip()
    elif fn.code:
        # Write inline code to temp and execute
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(fn.code)
            tmp_path = tmp.name
        actual_cmd = f"{py} {tmp_path} {fn_args}".strip()
    else:
        return 0
    try:
        result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
        return result.returncode
    finally:
        if fn.code and 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _exec_function_node(fn, fn_args: str, env: dict, task: Task) -> int:
    """Execute a Node.js function (inline code or file)."""
    if fn.file:
        actual_cmd = f"node {fn.file} {fn_args}".strip()
    elif fn.code:
        actual_cmd = f"node -e {repr(fn.code)}"
    else:
        return 0
    result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
    return result.returncode


def _exec_function_binary(fn, fn_args: str, env: dict, task: Task) -> int:
    """Execute a binary/executable function."""
    if fn.file:
        actual_cmd = f"{fn.file} {fn_args}".strip()
    else:
        return 0
    result = subprocess.run(actual_cmd, shell=True, env=env, cwd=task.working_dir, text=True)
    return result.returncode


def run_inline_python(runner, cmd: str, task: Task) -> int:
    """Execute inline Python code.

    Syntax: @python <python_expression_or_statement>
    Variables are available as env vars and via os.environ.
    """
    code = cmd.strip()[8:]  # strip "@python "
    if not task.silent:
        console.print(f"  [cyan]→ @python[/] {code[:80]}{'...' if len(code) > 80 else ''}")
    if runner.dry_run:
        console.print("  [dim](dry run — skipped)[/]")
        return 0
    env = {**os.environ, **runner.variables}
    py = _python_cmd()
    result = subprocess.run(
        f"{py} -c {repr(code)}",
        shell=True, env=env, cwd=task.working_dir, text=True,
    )
    return result.returncode
