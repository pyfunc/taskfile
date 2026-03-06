"""Comprehensive E2E tests for Taskfile DSL command execution.

Tests all command types and combinations:
- Basic commands (echo, exit codes)
- @local / @remote prefixes (env-aware routing)
- @fn / @python inline execution
- Glob expansion in commands
- script: external script execution
- Variable expansion (${VAR}, {{VAR}})
- Dependencies (sequential, parallel)
- Conditions (condition:)
- Environment filters (env:)
- Platform filters (platform:)
- Error handling (ignore_errors, retries, timeout)
- register: (capture stdout)
- tags: (selective execution)
- working_dir (dir:)
- silent mode
- YAML command normalization (dict-as-cmd edge case)
"""

import os
import textwrap
import pytest
import yaml
from pathlib import Path

from taskfile.models import TaskfileConfig, Task, Environment
from taskfile.parser import load_taskfile
from taskfile.runner import TaskfileRunner
from taskfile.runner.commands import _expand_globs_in_command, run_command, execute_commands
from taskfile.runner.ssh import (
    is_local_command, is_remote_command,
    strip_local_prefix, strip_remote_prefix,
    wrap_ssh,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_runner(tasks_data: dict, env_name="local", **kwargs):
    """Create a TaskfileRunner from minimal task dict."""
    data = {
        "variables": {"APP": "testapp", "TAG": "v1", "PORT": "8080"},
        "environments": {
            "local": {"container_runtime": "docker"},
            "prod": {
                "ssh_host": "prod.example.com",
                "ssh_user": "deploy",
                "ssh_port": 22,
                "container_runtime": "podman",
            },
            "staging": {
                "ssh_host": "staging.example.com",
                "ssh_user": "deploy",
                "container_runtime": "docker",
            },
        },
        "tasks": tasks_data,
    }
    config = TaskfileConfig.from_dict(data)
    return TaskfileRunner(config=config, env_name=env_name, **kwargs)


def _make_runner_with_functions(tasks_data: dict, functions_data: dict, **kwargs):
    """Create a TaskfileRunner with functions section."""
    data = {
        "variables": {"APP": "testapp"},
        "environments": {"local": {}},
        "functions": functions_data,
        "tasks": tasks_data,
    }
    config = TaskfileConfig.from_dict(data)
    return TaskfileRunner(config=config, **kwargs)


# ═══════════════════════════════════════════════════════════════════════
# 1. Basic Command Execution
# ═══════════════════════════════════════════════════════════════════════

class TestBasicCommands:
    """Test basic command execution (echo, exit codes, multiple commands)."""

    def test_echo_command(self):
        runner = _make_runner({"hello": {"cmds": ["echo hello world"]}})
        assert runner.run_task("hello") is True

    def test_multiple_commands(self):
        runner = _make_runner({
            "multi": {"cmds": ["echo first", "echo second", "echo third"]},
        })
        assert runner.run_task("multi") is True

    def test_exit_0_success(self):
        runner = _make_runner({"ok": {"cmds": ["true"]}})
        assert runner.run_task("ok") is True

    def test_exit_1_failure(self):
        runner = _make_runner({"fail": {"cmds": ["false"]}})
        assert runner.run_task("fail") is False

    def test_exit_nonzero_failure(self):
        runner = _make_runner({"fail": {"cmds": ["exit 42"]}})
        assert runner.run_task("fail") is False

    def test_second_command_fails(self):
        """First command succeeds, second fails → task fails."""
        runner = _make_runner({
            "partial": {"cmds": ["echo ok", "exit 1", "echo never"]},
        })
        assert runner.run_task("partial") is False

    def test_empty_commands(self):
        """Task with no commands should succeed (no-op)."""
        runner = _make_runner({"noop": {"desc": "empty task"}})
        assert runner.run_task("noop") is True

    def test_command_with_pipe(self):
        runner = _make_runner({
            "pipe": {"cmds": ["echo hello | cat"]},
        })
        assert runner.run_task("pipe") is True

    def test_command_with_subshell(self):
        runner = _make_runner({
            "sub": {"cmds": ["echo $(date +%Y)"]},
        })
        assert runner.run_task("sub") is True

    def test_unknown_task(self):
        runner = _make_runner({"hello": {"cmds": ["echo hello"]}})
        assert runner.run_task("nonexistent") is False


# ═══════════════════════════════════════════════════════════════════════
# 2. Variable Expansion
# ═══════════════════════════════════════════════════════════════════════

class TestVariableExpansion:
    """Test ${VAR} and {{VAR}} expansion in commands."""

    def test_dollar_brace_expansion(self):
        runner = _make_runner({"t": {"cmds": ["echo ${APP}"]}})
        assert runner.expand_variables("${APP}") == "testapp"

    def test_mustache_expansion(self):
        runner = _make_runner({"t": {"cmds": ["echo {{APP}}"]}})
        assert runner.expand_variables("{{APP}}") == "testapp"

    def test_multiple_variables(self):
        runner = _make_runner({"t": {"cmds": ["echo test"]}})
        result = runner.expand_variables("${APP}:${TAG} on port ${PORT}")
        assert result == "testapp:v1 on port 8080"

    def test_undefined_variable_passthrough(self):
        """Undefined variables should be left as-is (shell handles them)."""
        runner = _make_runner({"t": {"cmds": ["echo test"]}})
        result = runner.expand_variables("${UNDEFINED_VAR}")
        assert "UNDEFINED_VAR" in result

    def test_variable_in_command_execution(self):
        runner = _make_runner({
            "show": {"cmds": ["echo ${APP}:${TAG}"]},
        })
        assert runner.run_task("show") is True

    def test_env_overrides_global(self):
        """Environment variables override global ones."""
        data = {
            "variables": {"APP": "global-app"},
            "environments": {
                "prod": {"variables": {"APP": "prod-app"}},
            },
            "tasks": {"t": {"cmds": ["echo test"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config, env_name="prod")
        assert runner.variables["APP"] == "prod-app"

    def test_cli_overrides_all(self):
        """CLI --var overrides override everything."""
        runner = _make_runner(
            {"t": {"cmds": ["echo test"]}},
            var_overrides={"APP": "cli-app"},
        )
        assert runner.variables["APP"] == "cli-app"

    def test_builtin_env_variable(self):
        """ENV built-in variable is set to current env name."""
        runner = _make_runner({"t": {"cmds": ["echo test"]}}, env_name="prod")
        assert runner.variables["ENV"] == "prod"

    def test_builtin_runtime_variable(self):
        runner = _make_runner({"t": {"cmds": ["echo test"]}}, env_name="prod")
        assert runner.variables["RUNTIME"] == "podman"

    def test_builtin_compose_variable(self):
        runner = _make_runner({"t": {"cmds": ["echo test"]}}, env_name="local")
        assert runner.variables["COMPOSE"] == "docker compose"


# ═══════════════════════════════════════════════════════════════════════
# 3. @local / @remote Prefix Routing
# ═══════════════════════════════════════════════════════════════════════

class TestLocalRemoteRouting:
    """Test @local/@remote command routing based on environment."""

    def test_is_local_command(self):
        assert is_local_command("@local echo hello") is True
        assert is_local_command("echo hello") is False
        assert is_local_command("@remote echo hello") is False

    def test_is_remote_command(self):
        assert is_remote_command("@remote echo hello") is True
        assert is_remote_command("@ssh echo hello") is True
        assert is_remote_command("echo hello") is False
        assert is_remote_command("@local echo hello") is False

    def test_strip_local_prefix(self):
        assert strip_local_prefix("@local echo hello") == "echo hello"
        assert strip_local_prefix("echo hello") == "echo hello"

    def test_strip_remote_prefix(self):
        assert strip_remote_prefix("@remote echo hello") == "echo hello"
        assert strip_remote_prefix("@ssh echo hello") == "echo hello"

    def test_local_cmd_runs_on_local_env(self):
        """@local commands run when env is local (no SSH)."""
        runner = _make_runner({
            "t": {"cmds": ["@local echo local-only"]},
        }, env_name="local")
        assert runner.run_task("t") is True

    def test_local_cmd_skipped_on_remote_env(self):
        """@local commands are skipped when env has SSH (remote)."""
        runner = _make_runner({
            "t": {"cmds": ["@local echo should-skip"]},
        }, env_name="prod", dry_run=True)
        assert runner.run_task("t") is True

    def test_remote_cmd_skipped_on_local_env(self):
        """@remote commands are skipped when env is local."""
        runner = _make_runner({
            "t": {"cmds": ["@remote echo should-skip"]},
        }, env_name="local")
        assert runner.run_task("t") is True

    def test_remote_cmd_dryrun_on_prod(self):
        """@remote commands execute (dry-run) when env has SSH."""
        runner = _make_runner({
            "t": {"cmds": ["@remote echo hello-prod"]},
        }, env_name="prod", dry_run=True)
        assert runner.run_task("t") is True

    def test_mixed_local_remote_commands(self):
        """Task with both @local and @remote commands."""
        runner = _make_runner({
            "deploy": {
                "cmds": [
                    "@local echo building...",
                    "@local echo build-step-2",
                    "@remote systemctl restart app",
                ],
            },
        }, env_name="local")
        # On local: @local runs, @remote skips
        assert runner.run_task("deploy") is True

    def test_wrap_ssh_basic(self):
        """SSH wrapping produces correct command."""
        env = Environment(
            name="prod", ssh_host="example.com", ssh_user="deploy", ssh_port=22,
        )
        result = wrap_ssh("@remote echo hello", env)
        assert "ssh" in result
        assert "deploy@example.com" in result
        assert "echo hello" in result

    def test_wrap_ssh_custom_port(self):
        env = Environment(
            name="prod", ssh_host="example.com", ssh_user="root", ssh_port=2222,
        )
        result = wrap_ssh("@remote ls", env)
        assert "-p 2222" in result

    def test_wrap_ssh_with_key(self):
        env = Environment(
            name="prod", ssh_host="example.com", ssh_user="deploy",
            ssh_key="~/.ssh/deploy_key",
        )
        result = wrap_ssh("@remote ls", env)
        assert "-i" in result
        assert "deploy_key" in result

    def test_wrap_ssh_escapes_quotes(self):
        env = Environment(name="prod", ssh_host="x.com", ssh_user="u")
        result = wrap_ssh("@remote echo 'hello world'", env)
        # Single quotes in the remote command should be escaped
        assert "hello world" in result


# ═══════════════════════════════════════════════════════════════════════
# 4. Glob Expansion
# ═══════════════════════════════════════════════════════════════════════

class TestGlobExpansion:
    """Test local glob expansion in commands."""

    def test_expand_no_globs(self):
        result = _expand_globs_in_command("echo hello world")
        assert "echo" in result
        assert "hello" in result

    def test_expand_glob_with_matches(self, tmp_path):
        """Globs are expanded to matching files."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.log").write_text("c")

        result = _expand_globs_in_command("cat *.txt", cwd=str(tmp_path))
        assert "a.txt" in result
        assert "b.txt" in result
        assert "c.log" not in result

    def test_expand_glob_no_matches(self, tmp_path):
        """Non-matching globs are preserved as-is."""
        result = _expand_globs_in_command("cat *.xyz", cwd=str(tmp_path))
        assert "*.xyz" in result

    def test_expand_glob_nested_path(self, tmp_path):
        """Nested path globs like deploy/quadlet/*.container work."""
        sub = tmp_path / "deploy" / "quadlet"
        sub.mkdir(parents=True)
        (sub / "web.container").write_text("w")
        (sub / "landing.container").write_text("l")
        (sub / "proxy.network").write_text("n")

        result = _expand_globs_in_command(
            "scp deploy/quadlet/*.container user@host:/path/",
            cwd=str(tmp_path),
        )
        assert "web.container" in result
        assert "landing.container" in result
        assert "proxy.network" not in result

    def test_expand_glob_preserves_options(self):
        """Options (-flags) are not treated as globs."""
        result = _expand_globs_in_command("ls -la --all *.txt", cwd="/tmp")
        assert "-la" in result
        assert "--all" in result

    def test_expand_glob_preserves_variables(self):
        """$VAR references are not treated as globs."""
        result = _expand_globs_in_command("echo $HOME ${APP}")
        assert "$HOME" in result
        assert "${APP}" in result

    def test_expand_glob_multiple_patterns(self, tmp_path):
        """Multiple glob patterns in one command."""
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.sh").write_text("")

        result = _expand_globs_in_command("cat *.py *.sh", cwd=str(tmp_path))
        assert "a.py" in result
        assert "b.py" in result
        assert "c.sh" in result

    def test_expand_glob_question_mark(self, tmp_path):
        """? glob pattern matches single character."""
        (tmp_path / "a1.txt").write_text("")
        (tmp_path / "a2.txt").write_text("")
        (tmp_path / "abc.txt").write_text("")

        result = _expand_globs_in_command("cat a?.txt", cwd=str(tmp_path))
        assert "a1.txt" in result
        assert "a2.txt" in result
        # abc.txt should NOT match a?.txt (? = single char)
        assert "abc.txt" not in result

    def test_expand_glob_unbalanced_quotes(self):
        """Unbalanced quotes should not crash — returns original."""
        result = _expand_globs_in_command("echo 'unbalanced")
        assert "unbalanced" in result

    def test_expand_preserves_redirects(self):
        """Shell redirects like 2>/dev/null must not be quoted."""
        result = _expand_globs_in_command("podman tag img:latest img:prev 2>/dev/null || true")
        assert "2>/dev/null" in result
        # Must NOT be quoted (would break podman)
        assert "'2>/dev/null'" not in result

    def test_expand_preserves_redirect_2_ampersand_1(self):
        """2>&1 redirect must not be quoted."""
        result = _expand_globs_in_command("cmd arg 2>&1")
        assert "2>&1" in result
        assert "'2>&1'" not in result

    def test_glob_in_remote_scp_command(self, tmp_path):
        """Real-world: scp with globs in @remote context."""
        sub = tmp_path / "deploy" / "quadlet"
        sub.mkdir(parents=True)
        (sub / "web.container").write_text("")
        (sub / "landing.container").write_text("")
        (sub / "proxy.network").write_text("")

        result = _expand_globs_in_command(
            "scp deploy/quadlet/*.container deploy/quadlet/*.network user@host:/etc/",
            cwd=str(tmp_path),
        )
        assert "web.container" in result
        assert "landing.container" in result
        assert "proxy.network" in result
        assert "*.container" not in result  # glob was expanded


# ═══════════════════════════════════════════════════════════════════════
# 5. @fn / @python Execution
# ═══════════════════════════════════════════════════════════════════════

class TestFunctionExecution:
    """Test @fn and @python command prefixes."""

    def test_fn_shell_inline(self):
        """@fn calls shell function with inline code."""
        runner = _make_runner_with_functions(
            tasks_data={"t": {"cmds": ["@fn greet"]}},
            functions_data={"greet": {"lang": "shell", "code": "echo hello"}},
        )
        assert runner.run_task("t") is True

    def test_fn_unknown_function(self):
        """@fn with unknown function name fails."""
        runner = _make_runner_with_functions(
            tasks_data={"t": {"cmds": ["@fn nonexistent"]}},
            functions_data={"greet": {"lang": "shell", "code": "echo hello"}},
        )
        assert runner.run_task("t") is False

    def test_fn_python_inline(self):
        """@fn calls python function with inline code."""
        runner = _make_runner_with_functions(
            tasks_data={"t": {"cmds": ["@fn calc"]}},
            functions_data={"calc": {"lang": "python", "code": "print(2+2)"}},
        )
        assert runner.run_task("t") is True

    def test_fn_with_args(self):
        """@fn passes arguments to function."""
        runner = _make_runner_with_functions(
            tasks_data={"t": {"cmds": ["@fn greet world"]}},
            functions_data={"greet": {"lang": "shell", "code": 'echo "Hello $FN_ARGS"'}},
        )
        assert runner.run_task("t") is True

    def test_python_prefix(self):
        """@python runs inline Python code."""
        runner = _make_runner({"t": {"cmds": ["@python print('hello from python')"]}})
        assert runner.run_task("t") is True

    def test_python_prefix_with_import(self):
        runner = _make_runner({
            "t": {"cmds": ["@python import sys; print(sys.version_info.major)"]},
        })
        assert runner.run_task("t") is True

    def test_python_prefix_failure(self):
        """@python with syntax error fails."""
        runner = _make_runner({
            "t": {"cmds": ["@python this is not valid python!!!"]},
        })
        assert runner.run_task("t") is False

    def test_fn_dry_run(self):
        """@fn in dry-run mode doesn't execute."""
        runner = _make_runner_with_functions(
            tasks_data={"t": {"cmds": ["@fn greet"]}},
            functions_data={"greet": {"lang": "shell", "code": "echo hello"}},
            dry_run=True,
        )
        assert runner.run_task("t") is True

    def test_fn_shorthand_string(self):
        """Function defined as string shorthand (inline code)."""
        data = {
            "variables": {},
            "environments": {"local": {}},
            "functions": {"hello": "echo shorthand"},
            "tasks": {"t": {"cmds": ["@fn hello"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config)
        assert runner.run_task("t") is True


# ═══════════════════════════════════════════════════════════════════════
# 6. script: External Script Execution
# ═══════════════════════════════════════════════════════════════════════

class TestScriptExecution:
    """Test script: field for external script files."""

    def test_script_runs_successfully(self, tmp_path):
        """script: references an existing shell script."""
        script = tmp_path / "scripts" / "hello.sh"
        script.parent.mkdir()
        script.write_text("#!/bin/bash\necho hello from script\n")
        script.chmod(0o755)

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"script": "scripts/hello.sh"}},
        }))
        config = load_taskfile(taskfile)
        runner = TaskfileRunner(config=config)
        assert runner.run_task("hello") is True

    def test_script_not_found(self, tmp_path):
        """script: with missing file fails gracefully."""
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"script": "scripts/nonexistent.sh"}},
        }))
        config = load_taskfile(taskfile)
        runner = TaskfileRunner(config=config)
        assert runner.run_task("hello") is False

    def test_script_with_exit_code(self, tmp_path):
        """script: that exits non-zero fails the task."""
        script = tmp_path / "fail.sh"
        script.write_text("#!/bin/bash\nexit 42\n")
        script.chmod(0o755)

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"fail": {"script": "fail.sh"}},
        }))
        config = load_taskfile(taskfile)
        runner = TaskfileRunner(config=config)
        assert runner.run_task("fail") is False

    def test_script_plus_commands(self, tmp_path):
        """script: runs first, then inline commands."""
        script = tmp_path / "setup.sh"
        script.write_text("#!/bin/bash\necho setup done\n")
        script.chmod(0o755)

        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"both": {
                "script": "setup.sh",
                "cmds": ["echo inline done"],
            }},
        }))
        config = load_taskfile(taskfile)
        runner = TaskfileRunner(config=config)
        assert runner.run_task("both") is True

    def test_script_dry_run(self, tmp_path):
        """script: in dry-run mode doesn't execute."""
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(yaml.dump({
            "version": "1",
            "tasks": {"hello": {"script": "nonexistent.sh"}},
        }))
        config = load_taskfile(taskfile)
        runner = TaskfileRunner(config=config, dry_run=True)
        assert runner.run_task("hello") is True


# ═══════════════════════════════════════════════════════════════════════
# 7. Dependencies
# ═══════════════════════════════════════════════════════════════════════

class TestDependencies:
    """Test task dependency chains (deps:)."""

    def test_single_dependency(self):
        runner = _make_runner({
            "build": {"cmds": ["echo build"]},
            "deploy": {"cmds": ["echo deploy"], "deps": ["build"]},
        })
        assert runner.run_task("deploy") is True
        assert "build" in runner._executed
        assert "deploy" in runner._executed

    def test_chain_dependency(self):
        runner = _make_runner({
            "lint": {"cmds": ["echo lint"]},
            "test": {"cmds": ["echo test"], "deps": ["lint"]},
            "build": {"cmds": ["echo build"], "deps": ["test"]},
            "deploy": {"cmds": ["echo deploy"], "deps": ["build"]},
        })
        assert runner.run_task("deploy") is True
        assert "lint" in runner._executed
        assert "test" in runner._executed
        assert "build" in runner._executed
        assert "deploy" in runner._executed

    def test_failed_dependency_stops_task(self):
        runner = _make_runner({
            "fail-dep": {"cmds": ["exit 1"]},
            "main": {"cmds": ["echo should-not-run"], "deps": ["fail-dep"]},
        })
        assert runner.run_task("main") is False

    def test_multiple_deps(self):
        runner = _make_runner({
            "dep1": {"cmds": ["echo dep1"]},
            "dep2": {"cmds": ["echo dep2"]},
            "main": {"cmds": ["echo main"], "deps": ["dep1", "dep2"]},
        })
        assert runner.run_task("main") is True
        assert "dep1" in runner._executed
        assert "dep2" in runner._executed

    def test_dep_runs_only_once(self):
        """Dependencies are not re-executed if already done."""
        runner = _make_runner({
            "shared": {"cmds": ["echo shared"]},
            "a": {"cmds": ["echo a"], "deps": ["shared"]},
            "b": {"cmds": ["echo b"], "deps": ["shared"]},
            "main": {"cmds": ["echo main"], "deps": ["a", "b"]},
        })
        assert runner.run_task("main") is True
        assert "shared" in runner._executed

    def test_parallel_deps(self):
        runner = _make_runner({
            "dep1": {"cmds": ["echo dep1"]},
            "dep2": {"cmds": ["echo dep2"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["dep1", "dep2"],
                "parallel": True,
            },
        })
        assert runner.run_task("main") is True
        assert "dep1" in runner._executed
        assert "dep2" in runner._executed

    def test_parallel_deps_failure(self):
        runner = _make_runner({
            "ok": {"cmds": ["echo ok"]},
            "fail": {"cmds": ["exit 1"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["ok", "fail"],
                "parallel": True,
            },
        })
        assert runner.run_task("main") is False

    def test_parallel_deps_ignore_errors(self):
        runner = _make_runner({
            "ok": {"cmds": ["echo ok"]},
            "fail": {"cmds": ["exit 1"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["ok", "fail"],
                "parallel": True,
                "ignore_errors": True,
            },
        })
        assert runner.run_task("main") is True


# ═══════════════════════════════════════════════════════════════════════
# 8. Conditions
# ═══════════════════════════════════════════════════════════════════════

class TestConditions:
    """Test condition: field (skip task if condition fails)."""

    def test_condition_true_runs_task(self):
        runner = _make_runner({
            "t": {"cmds": ["echo ok"], "condition": "true"},
        })
        assert runner.run_task("t") is True

    def test_condition_false_skips_task(self):
        runner = _make_runner({
            "t": {"cmds": ["echo should-not-run"], "condition": "false"},
        })
        # Skipped = success (True)
        assert runner.run_task("t") is True
        assert "t" in runner._executed  # marked as executed (skipped)

    def test_condition_command_check(self):
        """condition: uses shell command exit code."""
        runner = _make_runner({
            "t": {"cmds": ["echo exists"], "condition": "test -d /tmp"},
        })
        assert runner.run_task("t") is True

    def test_condition_with_variable(self):
        """condition: supports variable expansion."""
        runner = _make_runner({
            "t": {"cmds": ["echo ok"], "condition": "test ${APP} = testapp"},
        })
        assert runner.run_task("t") is True

    def test_condition_failure_command(self):
        runner = _make_runner({
            "t": {"cmds": ["echo ok"], "condition": "test -f /nonexistent/file"},
        })
        assert runner.run_task("t") is True  # skipped = success


# ═══════════════════════════════════════════════════════════════════════
# 9. Environment Filters
# ═══════════════════════════════════════════════════════════════════════

class TestEnvironmentFilters:
    """Test env: filter on tasks."""

    def test_env_filter_match(self):
        """Task runs when current env matches filter."""
        runner = _make_runner({
            "deploy": {"cmds": ["echo deploy"], "env": ["prod"]},
        }, env_name="prod", dry_run=True)
        assert runner.run_task("deploy") is True

    def test_env_filter_no_match(self):
        """Task is skipped when current env doesn't match filter."""
        runner = _make_runner({
            "deploy": {"cmds": ["echo deploy"], "env": ["prod"]},
        }, env_name="local")
        # Skipped = success
        assert runner.run_task("deploy") is True

    def test_env_filter_multiple(self):
        """Task runs if any env in filter matches."""
        runner = _make_runner({
            "deploy": {"cmds": ["echo deploy"], "env": ["staging", "prod"]},
        }, env_name="staging", dry_run=True)
        assert runner.run_task("deploy") is True

    def test_no_env_filter_runs_everywhere(self):
        """Task without env filter runs on any environment."""
        runner = _make_runner({
            "t": {"cmds": ["echo universal"]},
        }, env_name="prod", dry_run=True)
        assert runner.run_task("t") is True


# ═══════════════════════════════════════════════════════════════════════
# 10. Platform Filters
# ═══════════════════════════════════════════════════════════════════════

class TestPlatformFilters:
    """Test platform: filter on tasks."""

    def test_platform_filter_match(self):
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {"web": {"variables": {"PORT": "3000"}}},
            "tasks": {"t": {"cmds": ["echo web"], "platform": ["web"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config, platform_name="web")
        assert runner.run_task("t") is True

    def test_platform_filter_no_match(self):
        data = {
            "variables": {},
            "environments": {"local": {}},
            "platforms": {
                "web": {},
                "desktop": {},
            },
            "tasks": {"t": {"cmds": ["echo web-only"], "platform": ["web"]}},
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config, platform_name="desktop")
        # Skipped = success
        assert runner.run_task("t") is True


# ═══════════════════════════════════════════════════════════════════════
# 11. Error Handling
# ═══════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Test ignore_errors, retries, timeout."""

    def test_ignore_errors(self):
        runner = _make_runner({
            "t": {"cmds": ["exit 1"], "ignore_errors": True},
        })
        assert runner.run_task("t") is True

    def test_ignore_errors_alias(self):
        """continue_on_error is alias for ignore_errors."""
        data = {
            "variables": {},
            "environments": {"local": {}},
            "tasks": {"t": {"cmds": ["exit 1"], "continue_on_error": True}},
        }
        config = TaskfileConfig.from_dict(data)
        task = config.tasks["t"]
        assert task.ignore_errors is True

    def test_retries_on_failure(self):
        """Task with retries retries the failing command."""
        runner = _make_runner({
            "t": {"cmds": ["exit 1"], "retries": 2, "retry_delay": 0},
        })
        # Still fails after retries
        assert runner.run_task("t") is False

    def test_retries_zero_no_retry(self):
        runner = _make_runner({
            "t": {"cmds": ["exit 1"], "retries": 0},
        })
        assert runner.run_task("t") is False

    def test_timeout_field_parsed(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo ok"], "timeout": 60}},
        })
        assert data.tasks["t"].timeout == 60

    def test_timeout_zero_means_no_timeout(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo ok"]}},
        })
        assert data.tasks["t"].timeout == 0


# ═══════════════════════════════════════════════════════════════════════
# 12. register: (Capture stdout)
# ═══════════════════════════════════════════════════════════════════════

class TestRegister:
    """Test register: captures command stdout into a variable."""

    def test_register_parsed(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo v1.0.0"], "register": "VERSION"}},
        })
        assert data.tasks["t"].register == "VERSION"

    def test_register_captures_output(self):
        runner = _make_runner({
            "capture": {"cmds": ["echo captured-value"], "register": "RESULT"},
        })
        assert runner.run_task("capture") is True
        assert runner.variables.get("RESULT") == "captured-value"

    def test_register_trims_whitespace(self):
        runner = _make_runner({
            "t": {"cmds": ["echo '  hello  '"], "register": "OUT"},
        })
        runner.run_task("t")
        assert runner.variables.get("OUT") is not None
        # register strips trailing whitespace
        assert runner.variables["OUT"].strip() == "hello"


# ═══════════════════════════════════════════════════════════════════════
# 13. tags: (Selective execution)
# ═══════════════════════════════════════════════════════════════════════

class TestTags:
    """Test tags: field on tasks."""

    def test_tags_parsed_list(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo"], "tags": ["ci", "deploy"]}},
        })
        assert data.tasks["t"].tags == ["ci", "deploy"]

    def test_tags_parsed_string(self):
        """Tags as comma-separated string."""
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo"], "tags": "ci, deploy, release"}},
        })
        assert "ci" in data.tasks["t"].tags
        assert "deploy" in data.tasks["t"].tags
        assert "release" in data.tasks["t"].tags

    def test_tags_empty_default(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo"]}},
        })
        assert data.tasks["t"].tags == []


# ═══════════════════════════════════════════════════════════════════════
# 14. working_dir (dir:)
# ═══════════════════════════════════════════════════════════════════════

class TestWorkingDir:
    """Test dir: field changes working directory."""

    def test_working_dir_parsed(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["ls"], "dir": "/tmp"}},
        })
        assert data.tasks["t"].working_dir == "/tmp"

    def test_working_dir_execution(self, tmp_path):
        """Commands run in specified working directory."""
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "marker.txt").write_text("found")

        runner = _make_runner({
            "t": {"cmds": ["test -f marker.txt"], "dir": str(sub)},
        })
        assert runner.run_task("t") is True


# ═══════════════════════════════════════════════════════════════════════
# 15. silent mode
# ═══════════════════════════════════════════════════════════════════════

class TestSilentMode:
    """Test silent: suppresses output."""

    def test_silent_parsed(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo secret"], "silent": True}},
        })
        assert data.tasks["t"].silent is True

    def test_silent_task_runs(self):
        runner = _make_runner({
            "t": {"cmds": ["echo secret"], "silent": True},
        })
        assert runner.run_task("t") is True


# ═══════════════════════════════════════════════════════════════════════
# 16. YAML Command Normalization
# ═══════════════════════════════════════════════════════════════════════

class TestCommandNormalization:
    """Test _normalize_commands handles YAML edge cases."""

    def test_string_commands(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo hello", "echo world"]}},
        })
        assert data.tasks["t"].commands == ["echo hello", "echo world"]

    def test_dict_commands_reconstructed(self):
        """YAML can misparse 'echo key: value' as dict — should be reconstructed."""
        from taskfile.models import _normalize_commands
        cmds = _normalize_commands([{"echo key": "value"}])
        assert cmds == ["echo key: value"]

    def test_shorthand_task_list(self):
        """Task defined as just a list of commands."""
        data = TaskfileConfig.from_dict({
            "tasks": {"t": ["echo one", "echo two"]},
        })
        assert data.tasks["t"].commands == ["echo one", "echo two"]

    def test_numeric_command_coerced(self):
        """Non-string commands are coerced to string."""
        from taskfile.models import _normalize_commands
        cmds = _normalize_commands([42, True, "echo ok"])
        assert "42" in cmds
        assert "True" in cmds
        assert "echo ok" in cmds


# ═══════════════════════════════════════════════════════════════════════
# 17. Dry-run Mode
# ═══════════════════════════════════════════════════════════════════════

class TestDryRun:
    """Test dry-run mode doesn't execute commands."""

    def test_dry_run_success(self):
        runner = _make_runner({"t": {"cmds": ["exit 1"]}}, dry_run=True)
        # dry-run doesn't execute, so shouldn't fail
        assert runner.run_task("t") is True

    def test_dry_run_with_deps(self):
        runner = _make_runner({
            "dep": {"cmds": ["echo dep"]},
            "main": {"cmds": ["echo main"], "deps": ["dep"]},
        }, dry_run=True)
        assert runner.run_task("main") is True

    def test_dry_run_remote(self):
        runner = _make_runner({
            "t": {"cmds": ["@remote systemctl restart app"]},
        }, env_name="prod", dry_run=True)
        assert runner.run_task("t") is True


# ═══════════════════════════════════════════════════════════════════════
# 18. Complex Real-World Scenarios
# ═══════════════════════════════════════════════════════════════════════

class TestRealWorldScenarios:
    """E2E tests simulating real deployment workflows."""

    def test_build_deploy_workflow(self):
        """Full build → deploy chain with env routing."""
        runner = _make_runner({
            "build": {
                "cmds": ["echo building ${APP}:${TAG}"],
            },
            "deploy": {
                "cmds": [
                    "@local echo deploying locally",
                    "@remote echo deploying remotely",
                ],
                "deps": ["build"],
            },
        }, env_name="local")
        assert runner.run_task("deploy") is True
        assert "build" in runner._executed

    def test_multi_env_task_structure(self):
        """Tasks with environment filters for different stages."""
        runner = _make_runner({
            "dev": {"cmds": ["echo dev"], "env": ["local"]},
            "deploy-staging": {"cmds": ["echo staging"], "env": ["staging"]},
            "deploy-prod": {"cmds": ["echo prod"], "env": ["prod"]},
            "build": {"cmds": ["echo build"]},
        }, env_name="local")
        # dev runs on local
        assert runner.run_task("dev") is True
        # staging task skipped on local
        assert runner.run_task("deploy-staging") is True
        assert "deploy-staging" in runner._executed  # marked as executed (skipped)

    def test_taskfile_from_yaml(self, tmp_path):
        """Parse a real Taskfile.yml and run dry-run."""
        taskfile = tmp_path / "Taskfile.yml"
        taskfile.write_text(textwrap.dedent("""\
            version: "1"
            name: test-project
            variables:
              APP: myapp
              TAG: latest

            environments:
              local:
                container_runtime: docker
              prod:
                ssh_host: example.com
                ssh_user: deploy
                container_runtime: podman

            tasks:
              test:
                desc: Run tests
                cmds:
                  - echo running tests

              build:
                desc: Build images
                deps: [test]
                cmds:
                  - echo building ${APP}:${TAG}

              deploy:
                desc: Deploy to environment
                env: [local, prod]
                deps: [build]
                cmds:
                  - "@local echo deploying locally"
                  - "@remote echo deploying remotely"
        """))
        config = load_taskfile(taskfile)
        runner = TaskfileRunner(config=config, dry_run=True)
        assert runner.run_task("deploy") is True

    def test_condition_with_deps(self):
        """Condition on task with dependencies."""
        runner = _make_runner({
            "dep": {"cmds": ["echo dep"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["dep"],
                "condition": "true",
            },
        })
        assert runner.run_task("main") is True
        assert "dep" in runner._executed

    def test_condition_false_skips_deps_too(self):
        """When condition is false, task (and its deps) are skipped."""
        runner = _make_runner({
            "dep": {"cmds": ["echo dep"]},
            "main": {
                "cmds": ["echo main"],
                "deps": ["dep"],
                "condition": "false",
            },
        })
        assert runner.run_task("main") is True
        # main was skipped due to condition
        assert "main" in runner._executed

    def test_register_used_in_next_command(self):
        """Register captures output that could be used later."""
        runner = _make_runner({
            "version": {"cmds": ["echo 2.0.1"], "register": "VER"},
            "tag": {"cmds": ["echo tagging ${VER}"], "deps": ["version"]},
        })
        assert runner.run_task("tag") is True
        assert runner.variables.get("VER") == "2.0.1"

    def test_mixed_prefixes_in_one_task(self):
        """Task using @local, @remote, @fn, and regular commands."""
        data = {
            "variables": {"APP": "myapp"},
            "environments": {"local": {}},
            "functions": {"notify": {"code": "echo notified"}},
            "tasks": {
                "full": {
                    "cmds": [
                        "echo step1",
                        "@local echo local-step",
                        "@fn notify",
                        "@python print('python-step')",
                    ],
                },
            },
        }
        config = TaskfileConfig.from_dict(data)
        runner = TaskfileRunner(config=config)
        assert runner.run_task("full") is True


# ═══════════════════════════════════════════════════════════════════════
# 19. Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_task_name_with_hyphens(self):
        runner = _make_runner({"my-complex-task": {"cmds": ["echo ok"]}})
        assert runner.run_task("my-complex-task") is True

    def test_task_name_with_dots(self):
        runner = _make_runner({"deploy.prod": {"cmds": ["echo ok"]}})
        assert runner.run_task("deploy.prod") is True

    def test_empty_variables(self):
        data = TaskfileConfig.from_dict({
            "variables": {},
            "tasks": {"t": {"cmds": ["echo ok"]}},
        })
        assert len(data.variables) == 0

    def test_no_environments_creates_local(self):
        data = TaskfileConfig.from_dict({
            "tasks": {"t": {"cmds": ["echo ok"]}},
        })
        assert "local" in data.environments

    def test_command_with_special_chars(self):
        runner = _make_runner({
            "t": {"cmds": ["echo 'hello & world | test > /dev/null 2>&1'"]},
        })
        assert runner.run_task("t") is True

    def test_very_long_command(self):
        long_cmd = "echo " + "x" * 500
        runner = _make_runner({"t": {"cmds": [long_cmd]}})
        assert runner.run_task("t") is True

    def test_desc_aliases(self):
        """Both 'desc' and 'description' work."""
        data1 = TaskfileConfig.from_dict({
            "tasks": {"t": {"desc": "short form", "cmds": ["echo"]}},
        })
        data2 = TaskfileConfig.from_dict({
            "tasks": {"t": {"description": "long form", "cmds": ["echo"]}},
        })
        assert data1.tasks["t"].description == "short form"
        assert data2.tasks["t"].description == "long form"

    def test_env_ssh_target_property(self):
        env = Environment(name="prod", ssh_host="example.com", ssh_user="deploy")
        assert env.ssh_target == "deploy@example.com"
        assert env.is_remote is True

    def test_env_local_no_ssh(self):
        env = Environment(name="local")
        assert env.ssh_target is None
        assert env.is_remote is False

    def test_task_should_run_on_any_when_no_filter(self):
        task = Task(name="t")
        assert task.should_run_on("local") is True
        assert task.should_run_on("prod") is True
        assert task.should_run_on("anything") is True

    def test_task_should_run_on_with_filter(self):
        task = Task(name="t", env_filter=["prod", "staging"])
        assert task.should_run_on("prod") is True
        assert task.should_run_on("staging") is True
        assert task.should_run_on("local") is False
