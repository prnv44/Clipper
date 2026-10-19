"""Offline launcher and help expectations for Ziv."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "ziv", *args],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_ziv_module_help_is_available_without_a_terminal() -> None:
    result = _run_module("--help")

    assert result.returncode == 0, result.stderr
    help_text = result.stdout.lower()
    assert "usage: ziv" in help_text
    assert "--source" in help_text
    assert "--links" in help_text
    assert "--check-youtube" in help_text


def test_ziv_help_alias_is_available_without_a_terminal() -> None:
    result = _run_module("help")

    assert result.returncode == 0, result.stderr
    assert "usage: ziv" in result.stdout.lower()


def test_launcher_passes_normal_cli_help() -> None:
    result = subprocess.run(
        [str(ROOT / "ziv.sh"), "--help"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    help_text = result.stdout.lower()
    assert "usage:" in help_text
    assert "--links" in help_text
    assert "--source" in help_text


def test_windows_launchers_forward_to_the_project_environment() -> None:
    launcher = (ROOT / "ziv.ps1").read_text(encoding="utf-8")
    updater = (ROOT / "update.ps1").read_text(encoding="utf-8")

    assert '.venv\\Scripts\\python.exe' in launcher
    assert '& $Python -m ziv @ZivArgs' in launcher
    assert '@("pull", "--ff-only", "origin"' in updater
    assert '"lock", "--upgrade"' in updater
    assert '"sync", "--all-extras"' in updater
    assert '"-e", ".[all,dev]"' in updater


def test_no_arguments_use_normal_cli_error_instead_of_opening_a_tui() -> None:
    result = _run_module()
    assert result.returncode == 1
    assert "video file/folder" in result.stderr.lower()
