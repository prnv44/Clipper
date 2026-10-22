"""Public Ziv command and workflow dispatch."""
from __future__ import annotations

import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from . import pipeline_cli
from .catalog import CatalogError, SourceCatalog
from .config import CHANNELS_FILE, LINKS_FILE


def _raw_args(argv: Sequence[str] | None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def _pipeline(args: Sequence[str], *, prog: str = "ziv") -> int:
    return pipeline_cli.main(list(args), prog=prog)


def _make(args: Sequence[str]) -> int:
    """Run the simple source-to-queue flow behind ``ziv make``.

    With no arguments, discovery runs first when channels are configured and
    the resulting links are processed in the same command. Direct video paths
    retain the normal flag-based pipeline.
    """
    if args:
        return _pipeline(["--no-post", *args])

    from .core.channels import parse_channels_file
    from .core.downloader import parse_links_file

    channel_entries = parse_channels_file(CHANNELS_FILE)
    link_entries = parse_links_file(LINKS_FILE)
    if not channel_entries and not link_entries:
        print("[ziv] Nothing to make yet.")
        print("[ziv] 1. Run `ziv setup` if you have not done so.")
        print("[ziv] 2. Add a channel to channels.txt or a video/path to links.txt.")
        print("[ziv] 3. Run `ziv make` again.")
        return 1

    if channel_entries:
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
    if parse_links_file(LINKS_FILE):
        return _pipeline(["--links", "--no-post"])

    print("[ziv] Discovery found no new videos to make.")
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


def _catalog() -> SourceCatalog:
    catalog = SourceCatalog()
    # Import is explicit and idempotent: the TUI can show the files users
    # already maintain without silently rewriting them.
    catalog.import_files()
    return catalog


def _add_source(args: Sequence[str]) -> int:
    if len(args) < 3 or args[0] not in {"link", "channel"}:
        print("Usage: ziv add link|channel NAME URL_OR_PATH [key=value ...]", file=sys.stderr)
        return 1
    kind, name, target = args[:3]
    options = {}
    for token in args[3:]:
        key, separator, value = token.partition("=")
        if separator and key and value:
            options[key] = value
    catalog = SourceCatalog()
    try:
        record = (catalog.add_link(name, target, options) if kind == "link"
                  else catalog.add_channel(name, target, options))
    except (CatalogError, OSError, ValueError) as exc:
        print(f"[ziv] {exc}", file=sys.stderr)
        return 2
    try:
        catalog.materialize(kind, name)
    except (CatalogError, OSError, ValueError) as exc:
        print(f"[ziv] {exc}", file=sys.stderr)
        return 2
    print(f"[ziv] Added {record['kind']} '{record['name']}' -> {record['target']}")
    return 0


def _list_sources(kind: str | None = None) -> int:
    try:
        records = _catalog().statuses(kind)
    except (CatalogError, OSError, ValueError) as exc:
        print(f"[ziv] {exc}", file=sys.stderr)
        return 2
    if not records:
        print("[ziv] No sources in the catalog. Use 'ziv add link' or 'ziv add channel'.")
        return 0
    for record in records:
        print(f"{record['kind']:<7} {record['status']:<8} "
              f"{record['name']}: {record['target']}")
    return 0


def _run_source(args: Sequence[str]) -> int:
    if len(args) != 2 or args[0] not in {"link", "channel"}:
        print("Usage: ziv run-source link|channel NAME", file=sys.stderr)
        return 1
    kind, name = args
    try:
        record = SourceCatalog().get(kind, name)
    except (CatalogError, OSError, ValueError) as exc:
        print(f"[ziv] {exc}", file=sys.stderr)
        return 2
    if kind == "channel":
        from .core.channels import scan_channels

        state_dir = SourceCatalog().path.parent
        state_dir.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix="ziv-channel-", suffix=".txt",
            dir=state_dir, delete=False)
        path = Path(temporary.name)
        try:
            options = " ".join(f"{key}={value}" for key, value
                               in record.get("options", {}).items())
            temporary.write(record["target"])
            temporary.write(f" | {options}" if options else "")
            temporary.write("\n")
            temporary.flush()
            temporary.close()
            scan_channels(path, LINKS_FILE)
            return 0
        finally:
            path.unlink(missing_ok=True)
    target = record["target"]
    if target.lower().startswith(("http://", "https://")):
        state_dir = SourceCatalog().path.parent
        state_dir.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix="ziv-source-", suffix=".txt",
            dir=state_dir, delete=False)
        path = Path(temporary.name)
        try:
            options = " ".join(f"{key}={value}" for key, value
                               in record.get("options", {}).items())
            temporary.write(target + (f" | {options}" if options else "") + "\n")
            temporary.flush()
            temporary.close()
            return _pipeline(["--links", str(path), "--no-post"])
        finally:
            path.unlink(missing_ok=True)
    return _pipeline([target, "--no-post"])


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


def _catalog_command(command: str, args: Sequence[str]) -> int:
    if command == "add":
        return _add_source(args)
    if command in {"sources", "catalog", "links", "channels"}:
        kind = {"links": "link", "channels": "channel"}.get(command)
        return _list_sources(kind)
    if command == "import":
        report = SourceCatalog().import_files()
        print(f"[ziv] Imported {report['added']} source(s); {report['skipped']} skipped")
        return 0
    if command == "doctor":
        return _doctor(args)
    return -1


def _help() -> int:
    pipeline_cli.build_parser(prog="ziv").print_help()
    print("\nZiv commands:")
    print("  ziv                         run the normal command-line interface")
    print("  ziv add link NAME TARGET   add a named video source")
    print("  ziv add channel NAME URL   add a named YouTube channel")
    print("  ziv links|channels         list catalog entries")
    print("  ziv import                 import links.txt and channels.txt")
    print("  ziv run-source KIND NAME  run one catalog entry")
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
        return _pipeline([])

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
    catalog_result = _catalog_command(command, rest)
    if catalog_result >= 0:
        return catalog_result
    if command == "make":
        return _make(rest)
    if command == "parts":
        return _parts(rest)
    if command in {"number-parts", "number_only"}:
        return _parts(rest, number_only=True)
    if command == "post":
        return _post(rest)
    if command == "run-source":
        return _run_source(rest)
    if command in {"source", "scan"}:
        return _pipeline(["--source", *rest])
    if command in {"queue", "queue-status"}:
        return _pipeline(["--queue-status", *rest])
    if command == "styles":
        return _pipeline(["--list-styles", *rest])

    # Preserve the existing flag-based pipeline interface and explicit paths.
    return _pipeline(args)


__all__ = ["main"]
