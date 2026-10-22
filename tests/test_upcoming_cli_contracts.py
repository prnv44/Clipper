"""Public dispatcher contracts for setup and shell completion.

These tests deliberately use no shell, subprocess, network, credentials,
cookies, or files outside pytest's temporary directory.
"""
from __future__ import annotations

from pathlib import Path

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


def test_open_command_uses_output_directory_and_reports_success(monkeypatch, tmp_path, capsys) -> None:
    output = tmp_path / "output"
    output.mkdir()
    opened: list[Path] = []

    monkeypatch.setattr(cli, "OUTPUT_DIR", output)
    monkeypatch.setattr("ziv.desktop.open_path", lambda path: opened.append(path) or True)

    assert cli.main(["open"]) == 0
    assert opened == [output.resolve()]
    assert f"Opened: {output.resolve()}" in capsys.readouterr().out


def test_cleanup_defaults_to_preview_and_requires_apply(monkeypatch, tmp_path, capsys) -> None:
    from ziv.core import queue

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    clip.with_suffix(".ass").write_bytes(b"ass")
    state_path = tmp_path / "state" / "queue.json"
    monkeypatch.setattr(queue, "QUEUE_FILE", state_path)
    state = queue.enqueue_clips([clip])
    queue.mark_posted(clip, state, "confirmed")

    assert cli.main(["cleanup"]) == 0
    preview = capsys.readouterr().out
    assert "Preview only" in preview
    assert clip.exists() and clip.with_suffix(".ass").exists()

    assert cli.main(["cleanup", "--apply"]) == 0
    assert "Removed 2 artifact(s)" in capsys.readouterr().out
    assert not clip.exists() and not clip.with_suffix(".ass").exists()


def test_links_run_notifies_only_through_the_optional_boundary(monkeypatch, tmp_path) -> None:
    links = tmp_path / "links.txt"
    links.write_text("local.mp4\n", encoding="utf-8")
    stats = iter([(1, 0, 0), (0, 1, 2)])
    notifications: list[tuple[str, str]] = []

    monkeypatch.setattr(cli, "LINKS_FILE", links)
    monkeypatch.setattr(cli, "_preflight", lambda **kwargs: 0)
    monkeypatch.setattr(cli, "_pipeline", lambda args: 0)
    monkeypatch.setattr(cli, "_link_file_stats", lambda: next(stats))
    monkeypatch.setattr(
        "ziv.desktop.notify",
        lambda title, message: notifications.append((title, message)) or True,
    )

    assert cli._process_links_file() == 0
    assert notifications == [("Ziv run complete", "2 clip(s) created; 0 link(s) pending")]


def test_preview_is_read_only_and_reports_disk_estimate(monkeypatch, tmp_path, capsys) -> None:
    links = tmp_path / "links.txt"
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    links.write_text(f"{source}\nhttps://example.test/video\n", encoding="utf-8")
    monkeypatch.setattr(cli, "LINKS_FILE", links)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    assert cli.main(["preview"]) == 0
    output = capsys.readouterr().out
    assert "pending links: 2" in output
    assert "downloads required: 1" in output
    assert "No files were downloaded" in output
    assert not (tmp_path / ".ziv-state").exists()


def test_retry_runs_only_recorded_source_failures(monkeypatch, tmp_path, capsys) -> None:
    from ziv.core.run_state import record_failure

    links = tmp_path / "links.txt"
    links.write_text("video.mp4\n", encoding="utf-8")
    monkeypatch.setattr(cli, "LINKS_FILE", links)
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    record_failure(1, "video.mp4", phase="render", error="ffmpeg failed", links_path=links)
    received: list[list[str]] = []
    monkeypatch.setattr(cli, "_preflight", lambda **kwargs: 0)
    monkeypatch.setattr(cli, "_pipeline", lambda args: received.append(list(args)) or 0)

    assert cli.main(["retry"]) == 2
    assert received == [["--links", "--no-post", "--retry-failed"]]
    assert "0 recovered; 1 still failed" in capsys.readouterr().out
