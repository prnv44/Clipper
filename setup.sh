#!/usr/bin/env bash
# One-time Ziv setup for Linux and macOS.
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

install_system_tools() {
    case "$(uname -s)" in
        Darwin)
            if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
                return
            fi
            command -v brew >/dev/null 2>&1 || {
                printf '%s\n' '[ziv] Install Homebrew first: https://brew.sh' >&2
                exit 1
            }
            brew install ffmpeg
            ;;
        Linux)
            if command -v apt-get >/dev/null 2>&1; then
                as_root apt-get update
                as_root apt-get install -y ffmpeg curl
            elif command -v dnf >/dev/null 2>&1; then
                as_root dnf install -y ffmpeg curl
            elif command -v pacman >/dev/null 2>&1; then
                as_root pacman -Sy --needed --noconfirm ffmpeg curl
            else
                printf '%s\n' '[ziv] Install FFmpeg and FFprobe with your package manager, then rerun setup.sh.' >&2
                exit 1
            fi
            ;;
        *)
            printf '%s\n' '[ziv] Unsupported OS. Install FFmpeg and FFprobe, then run the uv steps from README.md.' >&2
            exit 1
            ;;
    esac
}

install_uv() {
    if command -v uv >/dev/null 2>&1; then
        UV="$(command -v uv)"
        return
    fi

    command -v curl >/dev/null 2>&1 || {
        printf '%s\n' '[ziv] curl is required to install uv.' >&2
        exit 1
    }
    mkdir -p "$ROOT/.tools"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$ROOT/.tools" sh
    UV="$ROOT/.tools/uv"
}

install_system_tools
install_uv

# uv selects the compatible Python available on this machine. The project
# supports Python 3.10 and newer; do not force a particular minor release.
"$UV" sync --locked --extra all

exec "$ROOT/.venv/bin/python" -m ziv setup "$@"
