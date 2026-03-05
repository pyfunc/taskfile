"""Tests for auth CLI helpers."""

import pytest
from pathlib import Path

from taskfile.cli.auth import _read_env_file, _write_env_var, _ensure_gitignore, REGISTRIES


class TestReadEnvFile:
    def test_read_existing(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n# comment\n\nKEY3=\n")
        result = _read_env_file(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2", "KEY3": ""}

    def test_read_missing(self, tmp_path):
        result = _read_env_file(tmp_path / "nonexistent")
        assert result == {}

    def test_read_empty(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        result = _read_env_file(env_file)
        assert result == {}


class TestWriteEnvVar:
    def test_write_new_file(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_var(env_file, "TOKEN", "abc123")
        assert env_file.is_file()
        content = env_file.read_text()
        assert "TOKEN=abc123" in content

    def test_write_upsert(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TOKEN=old\nOTHER=keep\n")
        _write_env_var(env_file, "TOKEN", "new")
        result = _read_env_file(env_file)
        assert result["TOKEN"] == "new"
        assert result["OTHER"] == "keep"

    def test_write_append(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=yes\n")
        _write_env_var(env_file, "NEW", "added")
        result = _read_env_file(env_file)
        assert result["EXISTING"] == "yes"
        assert result["NEW"] == "added"


class TestEnsureGitignore:
    def test_creates_gitignore(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _ensure_gitignore()
        gi = tmp_path / ".gitignore"
        assert gi.is_file()
        assert ".env" in gi.read_text()

    def test_appends_to_existing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        gi = tmp_path / ".gitignore"
        gi.write_text("*.pyc\n__pycache__/\n")
        _ensure_gitignore()
        content = gi.read_text()
        assert ".env" in content
        assert "*.pyc" in content

    def test_no_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        gi = tmp_path / ".gitignore"
        gi.write_text("*.pyc\n.env\n")
        _ensure_gitignore()
        content = gi.read_text()
        assert content.count(".env") == 1


class TestRegistries:
    def test_registries_have_required_fields(self):
        for reg in REGISTRIES:
            assert "name" in reg
            assert "env_key" in reg
            assert "url" in reg
            assert "steps" in reg
            assert len(reg["steps"]) > 0

    def test_env_keys_unique(self):
        keys = [r["env_key"] for r in REGISTRIES]
        assert len(keys) == len(set(keys))
