"""Public dispatcher contracts for setup and shell completion.

These tests deliberately use no shell, subprocess, network, credentials,
cookies, or files outside pytest's temporary directory.
"""
from __future__ import annotations

from ziv import cli


def test_no_arguments_run_the_default_links_flow(monkeypatch) -> None:
    received: list[tuple[str, ...]] = []

    def fake_links():
        received.append(())
        return 19

    monkeypatch.setattr(cli, "_run_links_file", fake_links)

    assert cli.main([]) == 19
    assert received == [()]


def test_setup_command_dispatches_to_the_offline_handler(monkeypatch) -> None:
    from ziv.setup import cli as setup_cli

    received: list[list[str]] = []

    def fake_setup(args, **kwargs):
        received.append(list(args))
        return 17

    monkeypatch.setattr(setup_cli, "main", fake_setup)

    assert cli.main(["setup", "--non-interactive"]) == 17
    assert received == [["--non-interactive"]]


def test_completion_command_dispatches_to_the_shell_handler(monkeypatch) -> None:
    received: list[list[str]] = []

    def fake_completion(args):
        received.append(list(args))
        return 23

    monkeypatch.setattr(cli, "_completion", fake_completion)

    assert cli.main(["completion", "bash"]) == 23
    assert received == [["bash"]]
