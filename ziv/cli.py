"""Public Ziv command and workflow dispatch."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from . import pipeline_cli
from .config import CHANNELS_FILE, GEMINI_API_KEY, LINKS_FILE, OUTPUT_DIR, PROJECT_ROOT


def _raw_args(argv: Sequence[str] | None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def _pipeline(args: Sequence[str], *, prog: str = "ziv") -> int:
    return pipeline_cli.main(list(args), prog=prog)


def _preflight(*, needs_download: bool = False) -> int:
    """Fail early with one actionable message before expensive work starts."""
    failures: list[str] = []
    for executable in ("ffmpeg", "ffprobe"):
        if shutil.which(executable) is None:
            failures.append(f"{executable} is missing; run ./setup.sh")
    if importlib.util.find_spec("google.genai") is None:
        failures.append("google-genai is missing; run ./setup.sh")
    if not os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip():
        failures.append("GEMINI_API_KEY is missing; set it in .env")
    if needs_download and importlib.util.find_spec("yt_dlp") is None:
        failures.append("yt-dlp is missing for URL downloads; run ./setup.sh")
    output_parent = OUTPUT_DIR if OUTPUT_DIR.exists() else OUTPUT_DIR.parent
    if not output_parent.exists() or not os.access(output_parent, os.W_OK):
        failures.append(f"output directory is not writable: {OUTPUT_DIR}")
    if failures:
        print("[ziv] Preflight failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 2
    return 0


def _link_file_stats() -> tuple[int, int, int]:
    """Return pending links, completed lines, and generated clip count."""
    from .core.downloader import parse_links_file

    pending = len(parse_links_file(LINKS_FILE))
    done = 0
    if LINKS_FILE.exists():
        try:
            done = sum(
                1 for raw in LINKS_FILE.read_text(encoding="utf-8").splitlines()
                if raw.strip().upper().startswith("DONE ")
                or "# DONE" in raw.upper()
            )
        except OSError:
            pass
    clips = 0
    if OUTPUT_DIR.exists():
        try:
            clips = sum(1 for path in OUTPUT_DIR.rglob("*.mp4") if path.is_file())
        except OSError:
            pass
    return pending, done, clips


def _process_links_file() -> int:
    """Process links.txt and print a compact completion summary."""
    from .core.downloader import parse_links_file

    _, done_before, clips_before = _link_file_stats()
    needs_download = any(
        entry.get("url", "").lower().startswith(("http://", "https://"))
        for entry in parse_links_file(LINKS_FILE)
    )
    preflight = _preflight(needs_download=needs_download)
    if preflight:
        return preflight
    result = _pipeline(["--links", "--no-post"])
    pending_after, done_after, clips_after = _link_file_stats()
    print("[ziv] Run complete" if result == 0 else "[ziv] Run finished with errors")
    print(f"[ziv] Links completed this run: {max(0, done_after - done_before)}")
    print(f"[ziv] Clips created this run: {max(0, clips_after - clips_before)}")
    print(f"[ziv] Pending links: {pending_after}")
    print(f"[ziv] Output: {OUTPUT_DIR}")
    print("[ziv] Instagram posts: 0 (posting is a separate command)")
    return result


def _make(args: Sequence[str]) -> int:
    """Run the simple source-to-queue flow behind ``ziv make``.

    With no arguments, discovery runs first when channels are configured and
    the resulting links are processed in the same command. Direct video paths
    retain the normal flag-based pipeline.
    """
    if args:
        preflight = _preflight()
        if preflight:
            return preflight
        return _pipeline(["--no-post", *args])

    from .core.channels import parse_channels_file
    from .core.downloader import parse_links_file

    channel_entries = parse_channels_file(CHANNELS_FILE)
    link_entries = parse_links_file(LINKS_FILE)
    print("[ziv] Make run: channels.txt -> links.txt -> output/ (no posting).")
    if not channel_entries and not link_entries:
        print("[ziv] Nothing to make yet.")
        print("[ziv] 1. Run `ziv setup` if you have not done so.")
        print("[ziv] 2. Add a channel to channels.txt or a video/path to links.txt.")
        print("[ziv] 3. Run `ziv make` again.")
        return 1

    if channel_entries:
        print(f"[ziv] Scanning {len(channel_entries)} configured channel(s)...")
        preflight = _preflight(needs_download=True)
        if preflight:
            return preflight
        try:
            import yt_dlp  # noqa: F401 - discovery requires the optional package
        except ImportError:
            print(
                "[ziv] yt-dlp is required for channel discovery. "
                "Install it with: uv sync --locked --extra all",
                file=sys.stderr,
            )
            return 2
        result = _pipeline(["--source"])
        if result:
            return result

    # Discovery appends to links.txt, so always parse it again before making.
    pending_links = parse_links_file(LINKS_FILE)
    if pending_links:
        print(f"[ziv] Processing {len(pending_links)} pending link(s)...")
        return _process_links_file()

    print("[ziv] No pending links found in links.txt.")
    return 0


def _run_links_file() -> int:
    """Process links.txt by default without scanning channels or posting."""
    from .core.downloader import parse_links_file

    print("[ziv] Default run: links.txt -> output/ (no channel scan, no posting).")
    pending_links = parse_links_file(LINKS_FILE)
    if pending_links:
        print(f"[ziv] Processing {len(pending_links)} pending link(s)...")
        return _process_links_file()

    if not LINKS_FILE.exists():
        print("[ziv] links.txt does not exist yet. Run `ziv setup` to create it.")
        return 1
    print("[ziv] No pending links found in links.txt.")
    print("[ziv] Add a video URL or local path, then run `ziv` again.")
    if CHANNELS_FILE.exists():
        from .core.channels import parse_channels_file

        if parse_channels_file(CHANNELS_FILE):
            print("[ziv] To discover channel videos first, run `ziv make`.")
    return 0


def _post(args: Sequence[str]) -> int:
    if not args:
        return _pipeline(["--post-now"])
    if list(args) in (["--due"], ["--post-due"]):
        return _pipeline(["--post-due"])
    print("Usage: ziv post [--due]", file=sys.stderr)
    return 1


def _parts(args: Sequence[str], *, number_only: bool = False) -> int:
    from .parts import cli as parts_cli

    forwarded = list(args)
    if number_only:
        forwarded.extend(["--mode", "number-only"])
    return parts_cli.main(forwarded, prog="ziv-parts")


def _source_file(kind: str) -> int:
    """Show the configured text-file sources without creating another database."""
    if kind == "link":
        from .core.downloader import parse_links_file

        path = LINKS_FILE
        entries = parse_links_file(path)
        label = "links"
    else:
        from .core.channels import parse_channels_file

        path = CHANNELS_FILE
        entries = parse_channels_file(path)
        label = "channels"

    print(f"[ziv] {label}: {path}")
    if not path.exists():
        print(f"[ziv] File does not exist yet. Run `ziv setup` to create it.")
        return 0
    if not entries:
        print(f"[ziv] No active {label} configured.")
        return 0

    print(f"[ziv] {len(entries)} active {label}:")
    for entry in entries:
        target = entry.get("url") or entry.get("target", "")
        options = []
        if kind == "link":
            for key, display in (("clips", "clips"), ("min_len", "min"),
                                 ("max_len", "max"), ("sub_style", "style")):
                value = entry.get(key)
                if value is not None:
                    options.append(f"{display}={value}")
            if entry.get("no_subs") is not None:
                options.append(f"subs={'false' if entry['no_subs'] else 'true'}")
        else:
            for key in ("limit", "min_views", "scan"):
                value = entry.get(key)
                if value is not None:
                    options.append(f"{key}={value}")
        suffix = f" | {' '.join(options)}" if options else ""
        print(f"  {target}{suffix}")
    return 0


def _status() -> int:
    """Print one compact, read-only overview of the local Ziv workspace."""
    from .core.channels import parse_channels_file
    from .core.downloader import parse_links_file
    from .core.queue import load_queue, review_holds, status_line
    from .doctor import dependency_checks

    pending = parse_links_file(LINKS_FILE)
    done = 0
    if LINKS_FILE.exists():
        try:
            done = sum(
                1 for raw in LINKS_FILE.read_text(encoding="utf-8").splitlines()
                if raw.strip().upper().startswith("DONE ")
                or "# DONE" in raw.upper()
            )
        except OSError:
            done = 0
    channels = parse_channels_file(CHANNELS_FILE)

    print("Ziv status")
    print("\nSources")
    print(f"  links.txt:    {len(pending)} pending, {done} completed")
    print(f"  channels.txt: {len(channels)} configured")

    print("\nRuntime")
    checks = {check.name: check for check in dependency_checks()}
    for name in ("Python >= 3.10", "ffmpeg", "ffprobe", "yt_dlp",
                 "GEMINI_API_KEY", "Instagram credentials"):
        check = checks.get(name)
        if check is None:
            continue
        state = "OK" if check.ok else ("WARN" if not check.required else "FAIL")
        print(f"  {state:<4} {name}: {check.detail}")

    try:
        queue = load_queue()
        print("\nQueue")
        print(f"  pending posts: {len(queue['pending'])}")
        print(f"  posted:        {len(queue['posted'])}")
        print(f"  failed:        {len(queue['failed'])}")
        print(f"  schedule:      {status_line(queue)}")
        if review_holds(queue):
            print("  review:        BLOCKED - inspect Instagram before retrying")
    except Exception as exc:
        print(f"\nQueue\n  FAIL queue unavailable: {exc}")

    clips = []
    if OUTPUT_DIR.exists():
        try:
            clips = [path for path in OUTPUT_DIR.rglob("*.mp4") if path.is_file()]
        except OSError:
            clips = []
    print("\nOutput")
    print(f"  directory:     {OUTPUT_DIR}")
    print(f"  clips:         {len(clips)}")
    if clips:
        latest = max(clips, key=lambda path: path.stat().st_mtime)
        print(f"  latest:        {latest}")
    state_dir = Path(os.environ.get("STATE_DIR") or PROJECT_ROOT / ".ziv-state")
    print(f"  state:         {state_dir}")
    return 0


def _doctor(args: Sequence[str]) -> int:
    if not args or args[0] in {"dependencies", "deps"}:
        from .doctor import run_doctor

        return run_doctor()
    if args[0] in {"--help", "help"}:
        print("Usage: ziv doctor [dependencies|youtube [URL]]")
        print("  dependencies  check local runtimes and optional integrations")
        print("  youtube URL   validate cookies and probe a YouTube URL")
        return 0
    if args[0] != "youtube":
        print("Usage: ziv doctor [dependencies|youtube [URL]]", file=sys.stderr)
        return 1
    from .core.downloader import check_youtube_access, youtube_auth_status

    status = youtube_auth_status()
    print(f"[youtube] method: {status['method']}")
    print(f"[youtube] {status['message']}")
    if not status["ok"]:
        return 2
    return check_youtube_access(args[1]) if len(args) > 1 else 0


def _completion(args: Sequence[str]) -> int:
    from .completion import SHELLS, script

    if len(args) == 1 and args[0] in SHELLS:
        print(script(args[0]), end="")
        return 0
    print("Usage: ziv completion bash|zsh|fish|powershell", file=sys.stderr)
    return 1


def _complete(args: Sequence[str]) -> int:
    from .completion import complete_command

    return complete_command(args)


def _file_source_command(command: str, args: Sequence[str] = ()) -> int:
    if command == "links":
        return _source_file("link")
    if command == "channels":
        return _source_file("channel")
    if command == "status":
        return _status()
    if command == "doctor":
        return _doctor(args)
    if command in {"add", "catalog", "sources", "import", "run-source"}:
        print(
            "[ziv] Source management uses channels.txt and links.txt. "
            "Edit those files directly.",
            file=sys.stderr,
        )
        return 1
    return -1


def _help() -> int:
    pipeline_cli.build_parser(prog="ziv").print_help()
    print("\nZiv commands:")
    print("  ziv (no args)             process pending entries from links.txt")
    print("  ziv links                  show active entries from links.txt")
    print("  ziv channels               show active entries from channels.txt")
    print("  ziv status                 show sources, runtime, queue, and output")
    print("  ziv completion SHELL      print native bash/zsh/fish/PowerShell completion")
    print("  ziv doctor                check local dependencies and install hints")
    print("  ziv doctor youtube [URL]  validate cookies or probe YouTube")
    print("  ziv setup [--redo|--show] configure Ziv for this machine")
    print("  ziv make|parts|post        run the existing workflows")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run Ziv's normal command-line workflows."""
    args = _raw_args(argv)
    if not args:
        return _run_links_file()

    command, rest = args[0], args[1:]
    if command == "help" or args == ["--help"]:
        return _help()
    if command == "setup":
        from .setup import cli as setup_cli

        return setup_cli.main(rest)
    if command == "completion":
        return _completion(rest)
    if command == "__complete":
        return _complete(rest)
    source_result = _file_source_command(command, rest)
    if source_result >= 0:
        return source_result
    if command == "make":
        return _make(rest)
    if command == "parts":
        return _parts(rest)
    if command in {"number-parts", "number_only"}:
        return _parts(rest, number_only=True)
    if command == "post":
        return _post(rest)
    if command in {"source", "scan"}:
        return _pipeline(["--source", *rest])
    if command in {"queue", "queue-status"}:
        return _pipeline(["--queue-status", *rest])
    if command == "styles":
        return _pipeline(["--list-styles", *rest])

    # Preserve the existing flag-based pipeline interface and explicit paths.
    return _pipeline(args)


__all__ = ["main"]
