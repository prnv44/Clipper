"""Offline tests for native shell completion generation and candidates."""
from __future__ import annotations

import pytest

from ziv import cli, completion, desktop


@pytest.mark.parametrize("shell", completion.SHELLS)
def test_completion_script_is_available_for_each_supported_shell(shell: str) -> None:
    script = completion.script(shell)

    assert script
    assert "ziv" in script
    assert "http" not in script


def test_completion_dispatch_prints_script_without_starting_workflows(monkeypatch, capsys) -> None:
    monkeypatch.setattr(completion, "script", lambda shell: f"synthetic {shell} script\n")

    assert cli.main(["completion", "bash"]) == 0
    assert capsys.readouterr().out == "synthetic bash script\n"


def test_completion_candidates_cover_commands_and_value_choices() -> None:
    assert "completion" in completion.candidates(["ziv", ""], 1)
    assert "status" in completion.candidates(["ziv", ""], 1)
    assert "preview" in completion.candidates(["ziv", ""], 1)
    assert "retry" in completion.candidates(["ziv", ""], 1)
    assert "open" in completion.candidates(["ziv", ""], 1)
    assert "--apply" in completion.candidates(["ziv", "cleanup", "--"], 2)
    assert "--yes" in completion.candidates(["ziv", "clean", "--"], 2)
    assert "--profile" in completion.candidates(["ziv", "make", "--"], 2)
    assert completion.candidates(["ziv", "make", "--auto-mode", ""], 3) == [
        "content", "duration",
    ]


def test_completion_rejects_unknown_shell_without_external_access(capsys) -> None:
    assert cli.main(["completion", "tcsh"]) == 1
    assert "Usage: ziv completion" in capsys.readouterr().err


def test_desktop_notification_falls_back_to_terminal(monkeypatch, capsys) -> None:
    monkeypatch.setattr(desktop, "_notification_command", lambda title, message: None)

    assert desktop.notify("Done", "3 clips", enabled=True) is False
    assert capsys.readouterr().out == "[ziv] Done: 3 clips\n"
