# Contributing to Ziv

Thanks for helping improve Ziv. Changes should be small, reproducible, and
safe for users who run the tool without credentials.

## Development setup

Run the one-time setup script, then use the project-local environment:

```bash
./setup.sh --non-interactive
uv sync --locked --extra all --extra dev
.venv/bin/python -m pytest -q
```

FFmpeg/FFprobe are required only for media integration tests and real renders.
The default test suite is offline and must not need Gemini, YouTube, or
Instagram credentials.

## Before opening a pull request

Run:

```bash
python -m compileall -q ziv tests
.venv/bin/python -m pytest -q
bash -n ziv.sh
bash -n setup.sh
git diff --check
```

Add or update tests for user-visible behavior. Do not commit `.env`, cookies,
sessions, output media, `.ziv-state`, virtual environments, or downloaded files.

## Design rules

- Keep normal CLI commands non-interactive unless the command explicitly asks
  for setup or a secret.
- Never automate login, CAPTCHA solving, or access-control bypasses.
- Never log API keys, passwords, cookie contents, or session data.
- Keep provider/network calls behind testable boundaries.
- Preserve resumable checkpoints and conservative queue safety behavior.
