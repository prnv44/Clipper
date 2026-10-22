"""Offline dependency diagnostics and platform-specific install guidance."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import platform as platform_module
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlatformInfo:
    """The detected host family and commands that may be shown as hints."""

    family: str
    label: str
    hints: tuple[str, ...]


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if not separator:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def detect_platform() -> PlatformInfo:
    """Detect supported host families without invoking a package manager."""

    system = platform_module.system()
    if system == "Darwin":
        return PlatformInfo(
            "macos",
            f"macOS {platform_module.mac_ver()[0] or 'unknown version'}",
            (
                "brew install ffmpeg python",
                "uv sync --locked --extra all",
            ),
        )

    if system != "Linux":
        return PlatformInfo(
            "unknown",
            system or "Unknown operating system",
            (
                "Install FFmpeg (including ffprobe) with your operating system's package manager.",
                "uv sync --locked --extra all",
            ),
        )

    release = _os_release()
    distro_id = release.get("ID", "").lower()
    id_like = set(release.get("ID_LIKE", "").lower().split())
    pretty = release.get("PRETTY_NAME") or distro_id or "Linux"
    if distro_id in {"debian", "ubuntu", "linuxmint", "pop"} or "debian" in id_like:
        return PlatformInfo(
            "debian",
            pretty,
            (
                "sudo apt install ffmpeg python3 python3-venv",
                "uv sync --locked --extra all",
            ),
        )
    if distro_id in {"arch", "manjaro", "endeavouros"} or "arch" in id_like:
        return PlatformInfo(
            "arch",
            pretty,
            (
                "sudo pacman -S ffmpeg python python-pip",
                "uv sync --locked --extra all",
            ),
        )
    if distro_id in {"fedora", "rhel", "rocky", "almalinux"} or "fedora" in id_like:
        return PlatformInfo(
            "fedora",
            pretty,
            (
                "sudo dnf install ffmpeg python3 python3-pip",
                "uv sync --locked --extra all",
            ),
        )
    if distro_id in {"opensuse", "opensuse-leap", "opensuse-tumbleweed", "sles"} \
            or "suse" in id_like:
        return PlatformInfo(
            "opensuse",
            pretty,
            (
                "sudo zypper install ffmpeg python311 python311-pip",
                "uv sync --locked --extra all",
            ),
        )
    return PlatformInfo(
        "unknown",
        pretty,
        (
            "Install FFmpeg (including ffprobe) with your operating system's package manager.",
            "uv sync --locked --extra all",
        ),
    )


def _module_check(name: str, distribution: str, *, required: bool) -> Check:
    try:
        available = importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        available = False
    if not available:
        suffix = "required" if required else "optional"
        return Check(name, False, f"not importable ({suffix})", required)
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        version = "installed"
    return Check(name, True, version, required)


def dependency_checks() -> list[Check]:
    """Collect local checks only; no network or package-manager command runs."""

    python_ok = sys.version_info >= (3, 10)
    python_version = platform_module.python_version()
    checks = [
        Check(
            "Python >= 3.10",
            python_ok,
            python_version if python_ok else f"{python_version} (too old)",
        ),
    ]
    for executable in ("ffmpeg", "ffprobe"):
        path = shutil.which(executable)
        checks.append(Check(executable, path is not None, path or "not found"))
    checks.extend(
        (
            _module_check("google.genai", "google-genai", required=True),
            _module_check("faster_whisper", "faster-whisper", required=True),
            _module_check("yt_dlp", "yt-dlp", required=False),
            _module_check("instagrapi", "instagrapi", required=False),
        )
    )

    gemini_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    checks.append(Check(
        "GEMINI_API_KEY",
        gemini_key,
        "set" if gemini_key else "missing from environment/.env",
    ))
    instagram = bool(
        os.environ.get("IG_USERNAME", "").strip()
        and os.environ.get("IG_PASSWORD", "").strip()
    )
    checks.append(Check(
        "Instagram credentials",
        instagram,
        "set" if instagram else "not set (posting disabled)",
        required=False,
    ))
    return checks


def run_doctor() -> int:
    """Print an offline report and return non-zero for missing required items."""

    info = detect_platform()
    checks = dependency_checks()
    print("Ziv doctor")
    print(f"Platform: {info.label} [{info.family}]")
    print("Dependency checks:")
    for check in checks:
        if check.ok:
            state = "PASS"
        elif check.required:
            state = "FAIL"
        else:
            state = "WARN"
        print(f"  {state:<4} {check.name}: {check.detail}")

    print("Install hints (shown only; no package-manager commands were run):")
    for hint in info.hints:
        print(f"  {hint}")
    return 1 if any(not check.ok and check.required for check in checks) else 0


__all__ = ["Check", "PlatformInfo", "dependency_checks", "detect_platform", "run_doctor"]
