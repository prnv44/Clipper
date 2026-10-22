#!/usr/bin/env bash
# Canonical Linux launcher for Ziv's normal CLI.
# Explicit workflows and flags are forwarded to ``ziv``.
set -eu
ROOT="$(dirname "$(readlink -f "$0")")"
cd "$ROOT"
PYTHON=""
CANDIDATES=()
if [ -n "${VIRTUAL_ENV:-}" ]; then
    CANDIDATES+=("$VIRTUAL_ENV/bin/python")
fi
CANDIDATES+=("$ROOT/.venv/bin/python" "$ROOT/venv/bin/python")
for candidate in "${CANDIDATES[@]}"; do
    if [ -x "$candidate" ]; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "[ziv] No project Python environment found (.venv or venv); see README.md Setup." >&2
    exit 1
fi
exec "$PYTHON" -m ziv "$@"
