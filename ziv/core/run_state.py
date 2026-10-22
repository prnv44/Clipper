"""Small durable state for retryable source-processing failures."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from ..config import LINKS_FILE, PROJECT_ROOT


def state_dir() -> Path:
    return Path(os.environ.get("STATE_DIR") or PROJECT_ROOT / ".ziv-state")


def failures_path(links_path: Path | None = None) -> Path:
    """Return the failure journal associated with a links file."""
    path = Path(links_path or LINKS_FILE).resolve()
    if path == Path(LINKS_FILE).resolve():
        return state_dir() / "source-failures.json"
    safe_name = path.name.replace(".", "_")
    return state_dir() / f"{safe_name}.failures.json"


def _read(path: Path) -> dict[str, dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(entry, dict)
        for key, entry in value.items()
    ) else {}


def load_failures(links_path: Path | None = None) -> dict[str, dict]:
    return _read(failures_path(links_path))


def _write(path: Path, value: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def record_failure(
    line_no: int,
    source: str,
    *,
    phase: str,
    error: str,
    links_path: Path | None = None,
    retryable: bool = True,
) -> None:
    path = failures_path(links_path)
    failures = _read(path)
    key = str(line_no)
    previous = failures.get(key, {})
    failures[key] = {
        "line": line_no,
        "source": source[:300],
        "phase": phase[:40],
        "error": str(error)[:500],
        "attempts": int(previous.get("attempts", 0)) + 1,
        "last_at": time.time(),
        "retryable": bool(retryable),
    }
    _write(path, failures)


def clear_failure(line_no: int, links_path: Path | None = None) -> None:
    path = failures_path(links_path)
    failures = _read(path)
    if str(line_no) not in failures:
        return
    failures.pop(str(line_no), None)
    if failures:
        _write(path, failures)
    else:
        path.unlink(missing_ok=True)


__all__ = [
    "clear_failure",
    "failures_path",
    "load_failures",
    "record_failure",
    "state_dir",
]
