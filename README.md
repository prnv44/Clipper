# Ziv

Ziv is a terminal-first toolkit for turning long videos into high-quality
vertical clips:

| Workflow | Command | Result |
| --- | --- | --- |
| Podcast highlights | `./ziv.sh make podcast.mp4 --clips auto` | AI chooses the worthwhile standalone moments; the count follows the content. |
| Condensed story parts | `./ziv.sh parts story.mp4` | AI retains a coherent story and exports chronological, roughly 60-second parts. |
| Number-only parts | `./ziv.sh number-parts cartoon.mp4` | Gemini finds funny moments, then the export burns only `1`, `2`, `3`… as part labels. |

Podcast highlights and condensed story parts use Gemini and caption timing;
all workflows export 1080x1920 H.264 files. Podcast highlights feed the
Instagram posting queue. The [parts workflow](ziv/parts/README.md)
exports files with the full source picture over a blurred background.

## Workflow

```text
channels.txt / links.txt / local video
      ↓
channel scanner ranks videos by views (upload date is ignored)
      ↓
source captions are read in bounded semantic chunks
      ↓
Gemini selects complete spoken moments and visually reviews framing
       ↓
source captions provide timing when available; Whisper covers the fallback
      ↓
FFmpeg center-crops or selectively fits clips into 1080x1920
      ↓
clips enter the Instagram queue
      ↓
Ziv's `post` workflow uploads them at a paced interval
```

The pipeline does not include YouTube uploads, TikTok uploads, multi-account
routing, jump cuts, progress bars, hooks, or auto-watcher modes. Channel
discovery is limited to finding unseen high-performing source videos by view
count. Framing is deliberately selective: normal close-ups use the fast center
crop, while Gemini can request a full-frame fit with blurred padding when a
center crop would cut off a presentation, screen, or group.

## Quality

The default `QUALITY=highest` profile produces:

- 1080x1920 vertical output
- H.264 High Profile, level 4.1, `yuv420p`
- 30 fps
- CRF 15 with the medium x264 preset
- AAC audio at 256 kbps

Source downloads use up to 1440p for long videos and 2160p for shorter videos
before the vertical crop. A quality-aware cache refuses to reuse an older
lower-resolution master when a sharper source is requested.

The medium preset is intentional: at the same CRF, `slow` mostly saves a
small amount of file size while costing much more CPU time. Instagram will
transcode the upload anyway.

Instagram performs its own final server-side transcode. The private API can
upload the prepared high-quality file, but it cannot reliably toggle
Instagram's mobile **Upload at highest quality** account setting. Enable that
setting in the Instagram app as well.

For a weaker computer:

```dotenv
QUALITY=high
X264_PRESET=veryfast
SOURCE_MAX_HEIGHT=1080
FFMPEG_THREADS=2
WHISPER_MODEL=tiny
WHISPER_COMPUTE=int8
WHISPER_THREADS=2
SUBTITLE_SOURCE=auto
MAKE_COVERS=false
MAKE_MAX_SOURCES=1
QUEUE_MAX_PENDING=4
AUTO_MAX_CLIPS=40
```

`QUALITY=high` uses CRF 17 and 192k audio; `X264_PRESET=veryfast` is the
important encoding-speed override. The source-height setting reduces download
and decoding work while output remains 1080x1920. Smaller sources look softer
after a vertical crop. Decoder, filter, encoder, and Whisper pools are bounded;
each fragment/clip renders sequentially. Set `AUDIO_NORMALIZATION=false` to
skip loudness normalization if consistent volume is less important.

Keep `AUTO_MAX_CLIPS` generous: it limits discovery, while `QUEUE_MAX_PENDING`
limits how much is rendered and queued at a time. A small posting queue can
still support ten good clips from a source over several make/post runs.

## Setup

Run one setup script. It installs FFmpeg, installs or uses `uv`, creates
`.venv`, installs the locked `.[all]` dependencies, and starts the Ziv setup
wizard.

### Linux / macOS

```bash
chmod +x setup.sh ziv.sh
./setup.sh
```

On Ubuntu/Debian, the script uses `apt`; on Fedora it uses `dnf`; on Arch it
uses `pacman`; on macOS it uses Homebrew. It may ask for your administrator
password to install FFmpeg and curl.

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

The Windows script uses `winget` to install FFmpeg when it is missing. `uv`
uses a compatible Python 3.10+ interpreter and installs every project
dependency, including `yt-dlp`.

### What setup does

`setup` detects your CPU, memory, operating system, GPU hints, and FFmpeg
availability. It recommends a safe processing profile and asks for:

- Gemini model and API key;
- YouTube cookie method, if anonymous access is not enough;
- quality, subtitles, Whisper, output, queue, and cleanup settings; and
- optional Instagram username, password, and 2FA code.

The setup script installs system dependencies; the wizard does not read cookie
contents, automate a login or CAPTCHA, or upload anything. It stores local
configuration in `.env` with secrets hidden from display. Never commit `.env`, cookies,
`.ig_session`, output media, or `.ziv-state`.

After a successful setup, Ziv creates these files if they are missing:

```text
channels.txt    # YouTube channels for automatic discovery
links.txt       # YouTube URLs or local video paths
```

They contain only commented instructions and examples. Existing files are
never overwritten, so rerunning setup is safe.

Check the installation with:

```powershell
.\ziv.ps1 doctor
```

or on Linux/macOS:

```bash
./ziv.sh doctor
```

For headless setup, pass `--non-interactive` and use `ZIV_SETUP_*` variables
or repeated `--set KEY=VALUE` options.

## Ziv command and launchers

The public command is `ziv`. Use `ziv.sh` on Linux/macOS or `ziv.ps1` in
PowerShell on Windows:

```bash
./ziv.sh --help                  # normal CLI help
./ziv.sh make video.mp4          # render and queue, never post
./ziv.sh parts story.mp4
./ziv.sh number-parts cartoon.mp4
./ziv.sh add link interview URL  # add a named source
./ziv.sh add channel comedy URL  # add a named channel
./ziv.sh links                   # list links and statuses
./ziv.sh channels                # list channels and statuses
./ziv.sh doctor youtube          # validate local cookie configuration
./ziv.sh completion bash         # generate shell completion
./ziv.sh post                    # post the queue now
./ziv.sh post --due              # post only when the schedule allows
./ziv.sh source                  # scan configured channels
./ziv.sh queue                   # show queue status
```

The equivalent Windows commands are:

```powershell
.\ziv.ps1 --help
.\ziv.ps1 make video.mp4
.\ziv.ps1 parts story.mp4
.\ziv.ps1 doctor
.\ziv.ps1 queue
```

With the project installed in the active virtual environment, the same
workflows are available as `ziv`, for example `ziv make video.mp4`. Arguments
that are not one of the named workflows are forwarded to the existing
flag-based pipeline, so commands such as `ziv --links --no-post` and
`ziv --dry-run video.mp4` retain their current behavior. `ziv --help` is the
main CLI reference.

The launchers only select the project virtual environment and forward arguments
to `python -m ziv`; the `ziv` package owns the public commands and workflow
implementation.

### Simple automatic flow

1. Run setup once; it creates `channels.txt` and `links.txt`.
2. Put YouTube channels in `channels.txt`, or video URLs/local paths in
   `links.txt`.
3. Run `./ziv.sh make` on Linux/macOS or `.\ziv.ps1 make` in PowerShell.

With no arguments, `make` discovers unseen videos from configured channels,
adds them to `links.txt`, then processes the pending links in the same run. It
never posts to Instagram automatically. Use `post` separately when you are
ready. If channel discovery is configured without `yt-dlp`, Ziv stops with an
actionable installation message before making network requests.

## Make clips

Ziv is intentionally a normal command-line tool. Use explicit commands and
flags from a shell, script, cron job, or terminal multiplexer. It does not open
a full-screen UI or prompt for a workflow when called without arguments.

### Content-based automatic count

`--clips auto` is the default. Gemini reads the caption chunks, proposes
complete standalone moments, and selects worthwhile, varied ideas without
filling a fixed quota. One source may yield 3 clips and another 10. The default
ceiling is 40, with up to 10 candidates proposed per transcript chunk.

```bash
./ziv.sh make podcast.mp4 --clips auto
./ziv.sh make podcast.mp4 --clips auto --min 20 --max 75
./ziv.sh make podcast.mp4 --clips 5
./ziv.sh make podcast.mp4 --clips auto --auto-mode duration
```

Automatic highlights respect `--min` and `--max` (defaults: 15 and 60 seconds),
as well as per-link overrides. `--auto-mode duration` uses the earlier estimate
of roughly one clip per ten minutes, controlled by
`AUTO_CLIP_DENSITY_MINUTES`. `AUTO_CLIP_MODE` sets the default strategy.

Source captions provide the best spoken evidence. Without captions, the
podcast workflow retains its visual/audio fallback and selected-window Whisper
for subtitle timing; sparse frames cannot reliably judge spoken stories.

### Queue-limited rendering and resume

Selection is independent of queue capacity. The source manifest records the
full `planned_clips` list, completed clips, `remaining`, and `complete` status.
Make renders a batch that fits `QUEUE_MAX_PENDING`. After posting frees slots,
rerun the same command to continue using cached selection and completed renders:

```bash
./ziv.sh make podcast.mp4
./ziv.sh post
./ziv.sh make podcast.mp4
```

In link mode, an unfinished source stays active in `links.txt`. It becomes
`# DONE`, and source cleanup becomes eligible, after every selected clip has
been rendered and handed to the queue. Stable clip IDs acknowledge completed
work even when posting cleanup has removed an earlier MP4. `--no-upload`
exports all selected highlights in one sequential run without the queue bound.

### Inputs and options

Local video:

```bash
./ziv.sh make /path/to/video.mp4
```

Multiple local files or a folder:

```bash
./ziv.sh make /path/to/videos --clips auto
```

Channel mode uses `channels.txt`:

```bash
./ziv.sh make
```

With no arguments, `./ziv.sh make` first scans every configured channel, ranks its
videos by view count regardless of upload date, appends unseen winners to
`links.txt`, and then processes those links. It does not choose only recent
uploads. The scan stores selected video IDs in `output/channel_history.json`
so the same winner is not added repeatedly; later scans advance to the next
unseen high-performing videos. Compact channel listings are cached for 24
hours by default, and `CHANNEL_BACKLOG_MAX=20` prevents a scan from filling the
machine with unprocessed sources.

Run discovery without processing:

```bash
.venv/bin/ziv source
```

Configure channels in this format:

```text
https://www.youtube.com/@veritasium | limit=5
@lexfridman | limit=3 | min_views=100000
```

`limit` controls the number of unseen winners per channel. `min_views` sets an
optional floor. `scan=0` (the default) examines the full available channel
video list, so older high-performing videos are eligible. Set `scan=N` only if
a channel is extremely large and you deliberately want to cap metadata work.
The ranking is still view-dominant, with light like/comment, topic-potential,
and title-diversity signals. `CHANNEL_BACKLOG_MAX=20` prevents discovery from
adding more than 20 active, unprocessed links; existing links are not deleted
when you lower that setting. `ziv setup` creates `channels.txt` with the format.

Direct link mode remains available:

```bash
.venv/bin/ziv --links --no-post
```

Each link is marked `# DONE` after successful processing. `links.txt` includes
commented examples for per-link settings such as `clips=5`, `min=10`, and
`max=45`.

Useful options:

```bash
./ziv.sh make video.mp4 --no-subs
./ziv.sh make video.mp4 --no-captions
./ziv.sh make video.mp4 --sub-style clean
./ziv.sh make video.mp4 --dry-run
./ziv.sh make video.mp4 --subtitle-source source
./ziv.sh make video.mp4 --no-covers --profile
```

`--dry-run` writes `selection.json` under the source output directory so the
chosen windows and their evidence can be reviewed before rendering.

`SUBTITLE_SOURCE=auto` (the default) uses timestamped YouTube or local VTT/SRT
captions for the burned-in subtitle timing. It distributes phrase-cue timing
across individual words for karaoke highlighting. Set
`--subtitle-source whisper` when source captions are unavailable or their
timing needs to be regenerated locally. `--subtitle-source source` requires a
usable caption track.

## Cut a condensed story into parts

Use the separate parts workflow for challenge, adventure, documentary, and
MrBeast-style story videos:

```bash
./ziv.sh parts /path/to/story.mp4
./ziv.sh parts 'https://www.youtube.com/watch?v=VIDEO_ID'
./ziv.sh parts story.mp4 --part-seconds 60 --labels
./ziv.sh parts story.mp4 --dry-run
```

For cartoons, episodes, or any video that must not be condensed, use the
number-only variant:

```bash
./ziv.sh number-parts cartoon.mp4
./ziv.sh number-parts cartoon.mp4 --part-seconds 60 --background blur
./ziv.sh parts cartoon.mp4 --mode number-only --dry-run
```

This variant runs Gemini over the long video to find funny, surprising, absurd,
reaction, visual-gag, and punchline moments. It keeps those selected moments in
chronological order, packs them into roughly 60-second parts, skips Whisper and
subtitles, and burns only the numeric part marker (`1`, `2`, `3` …) near the
top of the video. It still uses the full-picture vertical layout: `blur` keeps
the landscape frame visible, while `plain` uses lighter plain padding.

It does not preserve every source second: filler and non-funny footage are
intentionally omitted. If you need the complete source without selection, use
FFmpeg directly or the existing story workflow with an appropriate plan.

The equivalent Python command is:

```bash
.venv/bin/ziv-parts story.mp4
```

Use `ziv-parts story.mp4` when you need the direct parts entry point. The
normal `ziv parts` command is the recommended interface. An installed package
also provides the `ziv-parts` command.

### How the story edit works

1. Read source captions and sparsely sampled frames to identify story beats.
2. Retain setup, rules/stakes, essential developments, causal context, and
   the payoff; remove sponsors, filler, and repeated explanations.
3. Arrange the retained original footage and audio in source order.
4. Divide that edited timeline near 60 seconds, preferring nearby sentence
   endings and edit joins. Part count follows the retained story length.
5. Render numbered 1080x1920, 30 fps H.264 files with the full picture over a
   blurred background. A part can contain several source ranges.

Parts have a 90-second hard ceiling and may be shorter or longer than the
target to accommodate natural boundaries or the final remainder. Subtitle
timings are remapped onto the edited timeline so omitted speech disappears
and the retained words remain aligned.

YouTube captions or a local `.vtt`/`.srt` sidecar are preferred. Use
`--caption-file captions.srt` to supply a specific track. When captions are
missing, the parts workflow transcribes the source in sequential, cached
five-minute Whisper windows to obtain spoken evidence. That adds processing
time even with `--no-subs`, because the story planner still needs evidence.

### Output and recovery

```text
output/parts/<source-id>/
  story_plan.json
  manifest.json
  part_001.mp4
  part_001.ass
  part_002.mp4
  ...
```

`story_plan.json` records retained source ranges and the part-to-source mapping.
`--dry-run` generates this plan before rendering. `manifest.json` records
completed exports. Rerun the same command after an interruption to reuse story
selection, completed fragments, and completed parts. Temporary fragments are
removed after their final part has been assembled and validated.

The parts workflow exports files independently of the posting queue and
preserves its input video. `--out DIR` selects an export directory.

Number-only output sets `mode` to `number-only`, records Gemini's selected
funny-moment ranges, and writes `labels: numeric part number only` in the plan.
Its output is export-only and never enters the Instagram queue.

Useful options:

```bash
./ziv.sh parts story.mp4 --labels                  # visible Part N / Total label
./ziv.sh parts story.mp4 --background plain        # lighter than blurred padding
./ziv.sh parts story.mp4 --subtitle-source whisper # regenerate retained word timing
./ziv.sh parts story.mp4 --sub-style clean
./ziv.sh parts story.mp4 --no-subs --profile
./ziv.sh parts cartoon.mp4 --mode number-only --no-subs
```

The blurred background is processed at a smaller resolution before scaling
to the final canvas. Fragments render one at a time and are joined with stream
copy, avoiding a second full video encode or a large full-story intermediate.
For architecture and detailed usage, see [ziv/parts/README.md](ziv/parts/README.md).

## Post to Instagram

Post the queue immediately:

```bash
./ziv.sh post
```

Post only when the configured window and cooldown allow:

```bash
./ziv.sh post --due
```

The queue stores a JSON-safe Instagram media code after every successful
upload, so a successful post cannot be mistaken for a failed upload because of
Media-object serialization. Posting state now lives in `.ziv-state/`,
separate from disposable rendered/downloaded media. Before each upload it
writes a durable safety hold. If the request outcome is unknown, posting stops
instead of automatically risking a duplicate.

After checking Instagram, resolve a hold explicitly:

```bash
.venv/bin/ziv --confirm-posted /path/to/reel.mp4 MEDIA_CODE
# or, only after confirming no Reel exists:
.venv/bin/ziv --retry-after-review /path/to/reel.mp4
```

Inspect the queue:

```bash
.venv/bin/ziv queue
```

Reset the cooldown:

```bash
.venv/bin/ziv --reset-gap
```

Remove a clip from the queue:

```bash
.venv/bin/ziv --ignore /absolute/path/to/reel.mp4
```

Clean up clips that were already recorded as posted:

```bash
.venv/bin/ziv --cleanup-posted
```

## Configuration

Useful optional settings in `.env`:

```dotenv
QUALITY=highest
# SOURCE_MAX_HEIGHT=2160
# SOURCE_LONG_THRESHOLD_MINUTES=10
# SOURCE_MAX_HEIGHT_LONG=1440
# SOURCE_MAX_HEIGHT_SHORT=2160
# WHISPER_MODEL=tiny
# WHISPER_COMPUTE=int8
# WHISPER_THREADS=2
# X264_PRESET=veryfast
# SUB_FONT=Arial
# POST_HOURS=17-0
# QUEUE_MIN_GAP_MINUTES=60
# QUEUE_MAX_GAP_MINUTES=120
# QUEUE_MAX_ATTEMPTS=3
# CHANNEL_BACKLOG_MAX=20
# CHANNEL_CACHE_HOURS=24
# CHANNEL_SCAN_MAX=0
# MAKE_MAX_SOURCES=2
# QUEUE_MAX_PENDING=12
# SUBTITLE_SOURCE=auto
# MAKE_COVERS=false
# AUDIO_NORMALIZATION=true
# FFMPEG_THREADS=2
# GEMINI_MIN_INTERVAL_SECONDS=20
# GEMINI_SELECTION_CHUNK_CHARS=18000
# AUTO_CLIP_MODE=content
# AUTO_MAX_CLIPS=40
# AUTO_CANDIDATES_PER_CHUNK=10
# AUTO_CLIP_DENSITY_MINUTES=10
# ANALYSIS_MAX_FRAMES=12       # visual fallback samples; lower for weak CPUs
# PARTS_TARGET_SECONDS=60
# PARTS_BACKGROUND=blur
# PARTS_MODE=story
```

Unquoted inline comments separated by whitespace are supported, for example
`SUBTITLE_SOURCE=auto # prefer source captions`. Quoted values preserve literal
`#` characters. Already-exported shell environment variables take precedence
over `.env` values.

## Disposable media cleanup

The lean defaults remove the processed source after a successful render and
remove a clip's MP4, ASS, caption sidecar, and cover after Instagram confirms
the upload. Queue state, posted history, manifests, and checkpoints remain.

```dotenv
DELETE_SOURCE_AFTER_CLIP=true
DELETE_POSTED_CLIPS=true
```

Podcast source cleanup happens only after the full selected plan and its
manifest are complete, including all queue-limited batches. Parts exports retain
the input source and clean up their generated assembly fragments.
Posted-clip cleanup happens only after a valid Instagram media code has been
durably recorded. An uncertain upload is held for review and is never cleaned
up automatically. Set either value to `false` to retain that media.

For YouTube links that trigger bot protection, authentication is required.
The error is not a Python or FFmpeg failure: YouTube rejected an anonymous
request. First log into YouTube in a browser and solve any CAPTCHA, then close
that browser before yt-dlp reads its cookie database.

Use one of these methods in `.env`:

```dotenv
# Browser cookies (choose your actual browser):
YTDLP_COOKIES_FROM_BROWSER=firefox
# YTDLP_COOKIES_FROM_BROWSER=brave
# YTDLP_COOKIES_FROM_BROWSER=chrome:Profile 1

# Or a Netscape/Mozilla cookies.txt export instead:
# YTDLP_COOKIES_FILE=/absolute/path/to/cookies.txt
```

Do not set both methods. Verify authentication without downloading a video:

```bash
.venv/bin/ziv --check-youtube \
  'https://www.youtube.com/watch?v=h5NvTTOlOtI'
```

If browser-cookie extraction still fails, refresh the YouTube session and
export a fresh Netscape cookies file. Keep cookies outside the repository;
`.gitignore` excludes common cookie filenames. yt-dlp's current FAQ warns that
cookies should come from the same browser/IP session that passed any CAPTCHA.

## Tests

Fast offline checks:

```bash
.venv/bin/python -m pytest -q
```

This runs the checked-in suite without installing packages or contacting the
network. Use the Python executable from your project environment.

The `tests/` directory is source-repository code for contributors and CI. It
is intentionally not included in the built runtime wheel or sdist.

The optional synthetic FFmpeg tests verify single-window clips and multi-range
story-part assembly, including subtitles, labels, audio, and render resume:

```bash
.venv/bin/python -m pytest -q --run-integration
```

A real Instagram upload requires credentials and network access and is not run
by the test suite.

## Open-source development

Ziv is MIT-licensed. The repository includes contributor, security, and code
of conduct policies. Pull requests should keep the default test suite offline
and must not include credentials, browser cookies, generated media, or local
state. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

Shell completion is available without an extra dependency:

```bash
eval "$(ziv completion bash)"       # Bash
eval "$(ziv completion zsh)"        # Zsh
ziv completion fish | source        # Fish
ziv completion powershell           # PowerShell output
```

## Project layout

- `ziv/cli.py` - public command and workflow dispatch
- `ziv/pipeline_cli.py` - pipeline command implementation and Instagram posting
- `ziv/pipeline.py` - selection, selected transcription, rendering, queueing
- `ziv/core/highlights.py` - Gemini highlight selection
- `ziv/core/subtitles.py` - Whisper timing and ASS subtitles
- `ziv/core/cutter.py` - center crop, render, and covers
- `ziv/core/downloader.py` - optional links.txt downloads and source captions
- `ziv/core/source_text.py` - WebVTT/SRT parsing and caption download cache
- `ziv/core/transcripts.py` - bounded, cached full-source Whisper evidence
- `ziv/parts/` - condensed-story planning, timeline mapping, and parts export
- `ziv/core/cleanup.py` - successful-source and confirmed-post media cleanup
- `ziv/core/profiling.py` - opt-in stage timing metrics
- `ziv/core/queue.py` - durable Instagram-only queue and review holds
- `ziv/platforms/instagram.py` - login and Reel upload
- `setup.sh` - one-time Linux/macOS dependency setup
- `setup.ps1` - one-time Windows dependency setup
- `ziv.sh` - the one canonical Linux CLI launcher
- `ziv.ps1` - the Windows PowerShell CLI launcher
- `ziv/` - the sole application package
- `uv.lock` - pinned Python dependencies for reproducible installs
- `.github/workflows/tests.yml` - native GitHub Actions checks without Docker
