"""Small, optional desktop integrations with safe terminal behavior."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TextIO


def _enabled_from_environment() -> bool:
    value = os.environ.get("ZIV_DESKTOP_NOTIFICATIONS")
    if value is None:
        value = os.environ.get("DESKTOP_NOTIFICATIONS", "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _applescript_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _notification_command(title: str, message: str) -> list[str] | None:
    if sys.platform == "darwin":
        opener = shutil.which("osascript")
        if opener is None:
            return None
        script = (
            f'display notification "{_applescript_text(message)}" '
            f'with title "{_applescript_text(title)}"'
        )
        return [opener, "-e", script]
    if os.name != "nt":
        sender = shutil.which("notify-send")
        if sender is not None:
            return [sender, title, message]
    return None


def notify(
    title: str,
    message: str,
    *,
    enabled: bool | None = None,
    fallback: bool = True,
    stream: TextIO | None = None,
) -> bool:
    """Try a native notification without ever making the workflow fail.

    Notifications are opt-in through ``DESKTOP_NOTIFICATIONS=true`` (or the
    more explicit ``ZIV_DESKTOP_NOTIFICATIONS=true``). When enabled but no
    desktop notifier is available, the message is printed to the terminal.
    """
    if enabled is None:
        enabled = _enabled_from_environment()
    if not enabled:
        return False

    try:
        command = _notification_command(title, message)
        if command is None:
            raise FileNotFoundError("no supported desktop notification command")
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        if fallback:
            print(f"[ziv] {title}: {message}", file=stream or sys.stdout)
        return False
    return True


def open_path(path: Path) -> bool:
    """Open a file or directory with the host desktop's native opener."""
    path = Path(path)
    if os.name == "nt":
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            return False
        try:
            startfile(str(path))
        except OSError:
            return False
        return True

    if sys.platform == "darwin":
        opener = shutil.which("open")
        command = [opener, str(path)] if opener else None
    else:
        opener = shutil.which("xdg-open") or shutil.which("gio")
        command = ([opener, str(path)] if opener and opener.endswith("xdg-open")
                   else [opener, "open", str(path)] if opener else None)
    if command is None:
        return False
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


__all__ = ["notify", "open_path"]
