# Ziv

Ziv turns long videos into vertical clips for review and optional Instagram
posting. The normal workflow uses only two source files:

```text
channels.txt
links.txt
```

There is no source database or catalog to maintain.

## Quick start

### Linux and macOS

```bash
git clone https://github.com/prnv44/Clipper.git
cd Clipper
chmod +x setup.sh ziv.sh
./setup.sh
```

`setup.sh` installs FFmpeg/FFprobe when needed, installs or uses `uv`, creates
the project environment, installs the locked dependencies, and starts the Ziv
setup wizard.

### Windows PowerShell

```powershell
git clone https://github.com/prnv44/Clipper.git
cd Clipper
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

`setup.ps1` uses `winget` for FFmpeg when needed and uses `uv` to install the
project dependencies. Python 3.10 or newer is supported; setup does not force
a particular minor version.

The wizard saves local settings to `.env` and creates `channels.txt` and
`links.txt` if they are missing. Existing source files are never overwritten.

## Add sources

### `channels.txt`

Put one YouTube channel URL or handle per line:

```text
https://www.youtube.com/@example
@another-channel | limit=5 min_views=100000
```

Supported channel options:

```text
limit=5       # maximum winners added from this channel
min_views=100000
scan=50       # listing entries inspected; 0 means all available entries
```

### `links.txt`

Put one YouTube URL or local video path per line:

```text
https://www.youtube.com/watch?v=VIDEO_ID
/absolute/path/to/video.mp4 | clips=5 | min=10 max=45 | style=clean
```

Supported link options:

```text
clips=auto    # content-based automatic count
clips=5       # request a fixed count
min=10        # shortest clip in seconds
max=45        # longest clip in seconds
style=clean   # subtitle style
subs=false    # disable subtitles for this source
```

Use comments for notes. Processed lines are marked `# DONE`; they are skipped
on later runs. Keep credentials out of both files.

## Run Ziv

Linux/macOS:

```bash
./ziv.sh doctor       # check the local installation
./ziv.sh links        # show active links.txt entries
./ziv.sh channels     # show active channels.txt entries
./ziv.sh              # process pending links.txt entries
./ziv.sh make         # discover channels, then process links.txt
./ziv.sh parts video.mp4
./ziv.sh post         # post the queue when you are ready
```

Windows PowerShell:

```powershell
.\ziv.ps1 doctor
.\ziv.ps1 links
.\ziv.ps1 channels
.\ziv.ps1 make
.\ziv.ps1 parts video.mp4
.\ziv.ps1 post
```

`make` never posts automatically. It discovers unseen channel videos, appends
them to `links.txt`, renders pending sources, and adds finished clips to the
Instagram queue. Posting is always a separate `post` command.

To process one local file directly:

```bash
./ziv.sh make podcast.mp4 --clips auto
./ziv.sh make podcast.mp4 --clips 5 --min 20 --max 60
```

Useful commands:

```bash
./ziv.sh --help
./ziv.sh queue
./ziv.sh source
./ziv.sh doctor youtube
./ziv.sh styles
./ziv.sh completion bash
```

## Configuration

The setup wizard writes `.env`. At minimum, set a Gemini key for AI highlight
selection:

```dotenv
GEMINI_API_KEY=your_key_here
```

Instagram settings are only needed for posting:

```dotenv
IG_USERNAME=your_username
IG_PASSWORD=your_password
```

Copy `.env.example` for the complete list of optional settings. The important
performance settings are:

```dotenv
QUALITY=highest
X264_PRESET=medium
WHISPER_MODEL=tiny
WHISPER_COMPUTE=int8
FFMPEG_THREADS=2
```

For a weaker computer, use `QUALITY=high`, `X264_PRESET=veryfast`,
`SOURCE_MAX_HEIGHT=1080`, and `WHISPER_MODEL=tiny`.

If YouTube requires authentication, configure one method in `.env`:

```dotenv
YTDLP_COOKIES_FROM_BROWSER=firefox
# or
YTDLP_COOKIES_FILE=/absolute/path/to/cookies.txt
```

Never commit `.env`, cookies, `.ig_session`, output media, or `.ziv-state`.

## What `doctor` checks

Run:

```bash
./ziv.sh doctor
```

It checks:

- Python version;
- FFmpeg and FFprobe;
- Gemini and Whisper packages;
- `yt-dlp` when channels are configured;
- Instagram packages and credentials;
- `channels.txt` and `links.txt`;
- output and state directory writability.

For missing runtime packages or tools, rerun `./setup.sh` on Linux/macOS or
`.\setup.ps1` on Windows. For missing credentials, edit `.env` and rerun
`doctor`.

## Output and quality

Clips are rendered as vertical 1080x1920 H.264 video with AAC audio. The
default quality profile favors source detail. The pipeline uses source captions
when available and Whisper as a fallback for subtitle timing.

Generated media and checkpoints are stored below `output/`. Queue history and
render state are kept in `.ziv-state/` so interrupted work can resume safely.

## Safety behavior

- `make` does not post.
- Upload attempts use durable queue state and review holds for uncertain results.
- Setup does not automate browser login or CAPTCHA solving.
- Source files are never overwritten by setup.
- Corrupt queue state is not silently replaced with an empty queue.

## Development

The project uses `uv.lock` for reproducible dependencies:

```bash
uv sync --locked --extra all --extra dev
uv run python -m pytest -q
python -m compileall -q ziv tests
bash -n setup.sh
bash -n ziv.sh
git diff --check
```

The default test suite is offline. Integration tests that need media tools are
opt-in.

## Project layout

```text
setup.sh / setup.ps1       one-time dependency setup
ziv.sh / ziv.ps1           runtime launchers
ziv/cli.py                 public commands
ziv/core/                  download, discovery, rendering, queueing
ziv/parts/                 chronological story-part workflow
channels.txt               channel input file
links.txt                  video/path input file
.env.example               configuration reference
uv.lock                    locked Python dependencies
tests/                     offline contributor tests
```

Ziv is MIT licensed. See `SECURITY.md`, `CONTRIBUTING.md`, and
`CODE_OF_CONDUCT.md` for project policies.
