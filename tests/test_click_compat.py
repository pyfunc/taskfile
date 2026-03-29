"""Tests for click compatibility helpers."""

from __future__ import annotations

import builtins

import pytest

from taskfile.cli.click_compat import BadParameter, prompt


@pytest.fixture(autouse=True)
def _mute_click_echo(monkeypatch):
    monkeypatch.setattr("taskfile.cli.click_compat.click.echo", lambda *args, **kwargs: None)


class TestPrompt:
    def test_returns_input(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda: "hello")

        result = prompt("Name")

        assert result == "hello"

    def test_uses_default_when_input_is_empty(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda: "")

        result = prompt("Name", default="world")

        assert result == "world"

    def test_applies_default_before_type_conversion(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda: "")

        result = prompt("Age", default="7", type=int)

        assert result == 7

    def test_converts_type(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda: "42")

        result = prompt("Age", type=int)

        assert result == 42

    def test_rejects_invalid_type(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda: "abc")

        with pytest.raises(BadParameter, match="Invalid value"):
            prompt("Age", type=int)

    def test_confirms_value(self, monkeypatch):
        responses = iter(["secret", "secret"])
        monkeypatch.setattr(builtins, "input", lambda: next(responses))

        result = prompt("Token", confirmation_prompt=True)

        assert result == "secret"

    def test_rejects_mismatched_confirmation(self, monkeypatch):
        responses = iter(["secret", "other"])
        monkeypatch.setattr(builtins, "input", lambda: next(responses))

        with pytest.raises(BadParameter, match="Confirmed value does not match"):
            prompt("Token", confirmation_prompt=True)
