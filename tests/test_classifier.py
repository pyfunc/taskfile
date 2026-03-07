"""Tests for runner/classifier.py — command classification and glob expansion gating.

Covers:
- All CommandType classifications
- Shell constructs (for, while, if, case, subshells, brace groups)
- @-prefixed commands (@fn, @python, @remote, @local, @push, @pull)
- Multiline commands
- Plain commands (glob-safe)
- should_expand_globs() gate
- Edge cases: nested constructs, semicolons in Python, compound chains
"""

import pytest

from taskfile.runner.classifier import (
    CommandType,
    classify_command,
    should_expand_globs,
    has_glob_pattern,
)


# ═══════════════════════════════════════════════════════════════════════
# 1. Shell Constructs — must NOT go through shlex.split
# ═══════════════════════════════════════════════════════════════════════


class TestShellConstructs:
    """Commands that shlex.split would mangle."""

    @pytest.mark.parametrize("cmd", [
        "for f in *.txt; do echo $f; done",
        "for f in deploy/*.container; do echo $f; done",
        "for i in 1 2 3; do sleep $i; done",
        "for((i=0;i<10;i++)); do echo $i; done",
    ])
    def test_for_loops(self, cmd):
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    @pytest.mark.parametrize("cmd", [
        "while true; do sleep 1; done",
        "while read line; do echo $line; done < file.txt",
        "while(true); do echo loop; done",
    ])
    def test_while_loops(self, cmd):
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    @pytest.mark.parametrize("cmd", [
        "if [ -f file.txt ]; then echo exists; fi",
        "if test -d /tmp; then ls /tmp; fi",
        "if[[ -z $VAR ]]; then exit 1; fi",
        "if(test -f x); then echo y; fi",
    ])
    def test_if_statements(self, cmd):
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    @pytest.mark.parametrize("cmd", [
        "case $1 in start) echo starting;; stop) echo stopping;; esac",
    ])
    def test_case_statements(self, cmd):
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    @pytest.mark.parametrize("cmd", [
        "until ping -c1 google.com; do sleep 5; done",
    ])
    def test_until_loops(self, cmd):
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    @pytest.mark.parametrize("cmd", [
        "cd dir && for f in *.txt; do echo $f; done",
        "export VAR=1; for i in 1 2; do echo $i; done",
        "echo start && while true; do sleep 1; done",
    ])
    def test_construct_after_separator(self, cmd):
        """Shell construct appearing after && or ; should still be detected."""
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    @pytest.mark.parametrize("cmd", [
        "(cd /tmp && ls)",
        "( echo a; echo b )",
    ])
    def test_subshells(self, cmd):
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    @pytest.mark.parametrize("cmd", [
        "{ echo a; echo b; }",
    ])
    def test_brace_groups(self, cmd):
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT

    def test_semicolons_with_shell_keywords(self):
        """Semicolons + do/done/then/fi keywords = shell construct."""
        cmd = "test -f x; if true; then echo y; fi"
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT


# ═══════════════════════════════════════════════════════════════════════
# 2. @-Prefixed Commands
# ═══════════════════════════════════════════════════════════════════════


class TestPrefixedCommands:

    @pytest.mark.parametrize("cmd,expected", [
        ("@fn notify 'Deployed ${APP}'", CommandType.FN_CALL),
        ("@fn build_image web latest", CommandType.FN_CALL),
    ])
    def test_fn_calls(self, cmd, expected):
        assert classify_command(cmd) == expected

    @pytest.mark.parametrize("cmd,expected", [
        ("@python import os; print(os.getcwd())", CommandType.PYTHON_INLINE),
        ("@python print('hello; world')", CommandType.PYTHON_INLINE),
        ("@python x = [1,2,3]; print(sum(x))", CommandType.PYTHON_INLINE),
    ])
    def test_python_inline(self, cmd, expected):
        assert classify_command(cmd) == expected

    @pytest.mark.parametrize("cmd,expected", [
        ("@remote systemctl --user restart app", CommandType.REMOTE_CMD),
        ("@ssh ls -la /home/deploy", CommandType.REMOTE_CMD),
    ])
    def test_remote_commands(self, cmd, expected):
        assert classify_command(cmd) == expected

    @pytest.mark.parametrize("cmd,expected", [
        ("@local docker build -t app .", CommandType.LOCAL_CMD),
    ])
    def test_local_commands(self, cmd, expected):
        assert classify_command(cmd) == expected

    @pytest.mark.parametrize("cmd,expected", [
        ("@push deploy/quadlet/*.container remote:/path", CommandType.PUSH_CMD),
    ])
    def test_push_commands(self, cmd, expected):
        assert classify_command(cmd) == expected

    @pytest.mark.parametrize("cmd,expected", [
        ("@pull remote:/var/log/app.log ./logs/", CommandType.PULL_CMD),
    ])
    def test_pull_commands(self, cmd, expected):
        assert classify_command(cmd) == expected


# ═══════════════════════════════════════════════════════════════════════
# 3. Multiline Commands
# ═══════════════════════════════════════════════════════════════════════


class TestMultilineCommands:

    def test_multiline_script(self):
        cmd = "echo line1\necho line2\necho line3"
        assert classify_command(cmd) == CommandType.MULTILINE

    def test_heredoc_style(self):
        cmd = "cat <<EOF\nhello world\nEOF"
        assert classify_command(cmd) == CommandType.MULTILINE


# ═══════════════════════════════════════════════════════════════════════
# 4. Plain Commands — safe for glob expansion
# ═══════════════════════════════════════════════════════════════════════


class TestPlainCommands:

    @pytest.mark.parametrize("cmd", [
        "echo hello",
        "docker build -t app .",
        "scp deploy/quadlet/*.container user@host:/path",
        "rsync -avz deploy/ user@host:/deploy/",
        "ls -la",
        "cat file.txt",
        "echo ${APP}:${TAG}",
        "systemctl --user restart app",
        "podman pull ghcr.io/org/app:latest",
        "curl -sf https://example.com/health",
        "npm run build && npm run test",
        "cd /tmp && ls *.txt",
    ])
    def test_plain_commands(self, cmd):
        assert classify_command(cmd) == CommandType.PLAIN_CMD

    def test_pipe_without_constructs(self):
        """Simple pipes are PLAIN_CMD — shlex handles | fine."""
        assert classify_command("ls | grep txt") == CommandType.PLAIN_CMD

    def test_redirect_without_constructs(self):
        assert classify_command("echo hello > output.txt") == CommandType.PLAIN_CMD


# ═══════════════════════════════════════════════════════════════════════
# 5. should_expand_globs() Gate
# ═══════════════════════════════════════════════════════════════════════


class TestShouldExpandGlobs:

    def test_plain_cmd_allows_expansion(self):
        assert should_expand_globs("scp deploy/*.container host:/path") is True

    def test_for_loop_blocks_expansion(self):
        assert should_expand_globs("for f in *.txt; do echo $f; done") is False

    def test_fn_blocks_expansion(self):
        assert should_expand_globs("@fn notify 'hello'") is False

    def test_python_blocks_expansion(self):
        assert should_expand_globs("@python import os; print(os.getcwd())") is False

    def test_multiline_blocks_expansion(self):
        assert should_expand_globs("echo a\necho b") is False

    def test_remote_blocks_expansion(self):
        assert should_expand_globs("@remote ls *.txt") is False

    def test_subshell_blocks_expansion(self):
        assert should_expand_globs("(cd /tmp && ls)") is False


# ═══════════════════════════════════════════════════════════════════════
# 6. has_glob_pattern()
# ═══════════════════════════════════════════════════════════════════════


class TestHasGlobPattern:

    def test_star(self):
        assert has_glob_pattern("deploy/*.container") is True

    def test_question_mark(self):
        assert has_glob_pattern("file?.txt") is True

    def test_bracket(self):
        assert has_glob_pattern("file[0-9].txt") is True

    def test_no_glob(self):
        assert has_glob_pattern("echo hello") is False

    def test_empty(self):
        assert has_glob_pattern("") is False


# ═══════════════════════════════════════════════════════════════════════
# 7. Edge Cases — regression tests for known bugs
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_for_with_glob_inside_loop(self):
        """Bug 1.1: for f in *.txt; do echo $f; done — was mangled by shlex."""
        cmd = "for f in deploy/*.container; do echo deploying $f; done"
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT
        assert should_expand_globs(cmd) is False

    def test_python_with_semicolons(self):
        """Bug 1.1: @python import os; print(os.getcwd()) — shlex split on ;."""
        cmd = "@python import os; print(os.getcwd())"
        assert classify_command(cmd) == CommandType.PYTHON_INLINE
        assert should_expand_globs(cmd) is False

    def test_fn_with_quoted_args(self):
        """Bug 1.1: @fn notify 'Deployed ${APP}' — quotes mangled."""
        cmd = '@fn notify "Deployed ${APP}"'
        assert classify_command(cmd) == CommandType.FN_CALL
        assert should_expand_globs(cmd) is False

    def test_nested_subshell_with_glob(self):
        """cd dir && ls *.txt — subshell with glob should be shell construct if parens."""
        cmd = "cd dir && ls *.txt"
        # This is actually a plain cmd (no shell construct keywords)
        assert classify_command(cmd) == CommandType.PLAIN_CMD

    def test_if_with_glob_test(self):
        """if [ -f *.pid ]; then kill $(cat *.pid); fi"""
        cmd = "if [ -f *.pid ]; then kill $(cat *.pid); fi"
        assert classify_command(cmd) == CommandType.SHELL_CONSTRUCT
        assert should_expand_globs(cmd) is False

    def test_whitespace_preserved(self):
        """Leading/trailing whitespace should not affect classification."""
        assert classify_command("  for f in *.txt; do echo $f; done  ") == CommandType.SHELL_CONSTRUCT
        assert classify_command("  @fn notify hello  ") == CommandType.FN_CALL
        assert classify_command("  echo hello  ") == CommandType.PLAIN_CMD

    def test_empty_command(self):
        assert classify_command("") == CommandType.PLAIN_CMD
        assert classify_command("   ") == CommandType.PLAIN_CMD
