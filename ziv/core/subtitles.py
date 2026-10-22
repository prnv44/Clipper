"""Speech-to-text subtitles with karaoke-style word highlighting.

Uses faster-whisper (tiny/int8 = fast on old CPUs, ~75MB download).
Builds ASS subtitles burned into the video by ffmpeg's libass.

Timing model
------------
Each Dialogue line covers exactly the words it shows: it appears when the
first word starts and disappears a beat after the last one, never overlapping
the next line and never running past the end of the clip. The ASS karaoke
tags are computed so each word's colour flips at the moment that word starts
being spoken, so the highlight stays glued to the audio even when whisper
leaves gaps between word timestamps.
"""
from __future__ import annotations

import math
import os
import sys
import subprocess
import tempfile
from pathlib import Path

from .lowspec import WHISPER_COMPUTE, WHISPER_MODEL, WHISPER_THREADS, lowspec_input_args

_MODEL = None  # lazy singleton

# --- ASS style presets -------------------------------------------------------
# ASS colours are &HAABBGGRR (alpha, Blue, Green, Red — BGR, not RGB!).
# With karaoke (\k) tags: SecondaryColour is the text before it is spoken,
# PrimaryColour is the highlight once spoken. So the pair must always be
# (primary=highlight, secondary=base).
STYLES: dict[str, dict] = {
    # Exact-copy Hormozi look: heavy ALL-CAPS Montserrat, white fill, thick
    # black stroke (no box), one yellow word-pop per beat, 1-3 words on screen,
    # lower-middle of the frame (60-70% down), instant pop, no fades.
    # Spec: font 80-120px on 1080x1920, stroke 8-12px, highlight #FFD93D.
    "hormozi": {
        "font": "Montserrat", "font_size": 96, "bold": True,
        "primary": "&H003DD9FF",     # yellow highlight  (RGB #FFD93D)
        "secondary": "&H00FFFFFF",   # white base
        "outline_color": "&H00000000", "back": "&H00000000",
        "border_style": 1, "outline": 10, "shadow": 0, "alignment": 2,
        "margin_v": 576,             # baseline ~70% down the 1920px frame
        "max_words": 3, "uppercase": True, "scale": 108,
    },
    "clean": {    # smaller white line near the bottom; soft amber highlight
        "font": "Arial", "font_size": 52, "bold": False,
        "primary": "&H0050D2FF",     # soft amber        (RGB 255,210,80)
        "secondary": "&H00FFFFFF",   # white base
        "outline_color": "&H00101010", "back": "&H80000000",
        "border_style": 1, "outline": 3, "shadow": 1, "alignment": 2,
        "margin_v": 620, "max_words": 7, "uppercase": False,
    },
    "yellow": {   # bright yellow highlight pop, no box
        "font": "Montserrat", "font_size": 62, "bold": True,
        "primary": "&H0000E5FF",     # yellow highlight  (RGB 255,229,0)
        "secondary": "&H00FFFFFF",   # white base
        "outline_color": "&H00000000", "back": "&H00000000",
        "border_style": 1, "outline": 4, "shadow": 2, "alignment": 5,
        "margin_v": 0, "max_words": 4, "uppercase": False,
    },
}

FONT_OVERRIDE = os.environ.get("SUB_FONT", "")

# --- Timing tuning -----------------------------------------------------------
LINE_SPLIT_GAP = 0.7        # pause (s) long enough to start a new caption line
LINE_SPLIT_DURATION = 4.2   # max seconds one caption line stays on screen
WORD_GLOW = 0.30            # keep a finished line up this long after its last word
MIN_WORD_LEN = 0.05         # never let a word's spoken span be shorter than this
MAX_WORD_LEN = 1.5          # ...or longer than this (guards bad whisper end stamps)
FADE_MS = 60                # line fade, only on edges that don't touch another line
MAX_LINE_CHARS = 25         # max chars per caption row (font is BIG — this keeps
                            # even "EXTRAORDINARILY"-style lines inside the frame)
_PUNCT_EDGES = "\"'\u201c\u201d\u2018\u2019.!?…,;:-\u2014()[]"  # stripped off word edges


def _get_model():
    """Load whisper model once per process."""
    global _MODEL
    if _MODEL is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            print("[subs] faster-whisper not installed. Run: uv sync --locked --extra all",
                  file=sys.stderr)
            raise SystemExit(1) from exc
        print(f"[subs] Loading whisper '{WHISPER_MODEL}' ({WHISPER_COMPUTE})...")
        _MODEL = WhisperModel(WHISPER_MODEL, device="cpu", compute_type=WHISPER_COMPUTE,
                              cpu_threads=WHISPER_THREADS, num_workers=1)
    return _MODEL


def transcribe(video_path: Path, language: str | None = None,
               clip_timestamps: list[float] | None = None) -> list[dict]:
    """Transcribe a whole video or selected source-time windows.

    ``clip_timestamps`` is a flat ``[start, end, start, end, ...]`` list
    understood by faster-whisper. Selected windows keep their source timeline,
    so the returned words can be used directly for subtitles and clip editing.
    """
    model = _get_model()
    if clip_timestamps:
        return _transcribe_selected(model, video_path, clip_timestamps, language)
    print("[subs] Transcribing full source audio...")
    transcribe_kwargs = {
        "language": language,
        "word_timestamps": True,
        "vad_filter": True,
        "beam_size": 1,
    }
    segments, info = model.transcribe(str(video_path), **transcribe_kwargs)
    print(f"[subs] Detected language: {info.language} (p={info.language_probability:.2f})")

    words: list[dict] = []
    for seg in segments:
        for w in seg.words or []:
            # braces would open an ASS override block — neutralise them
            token = w.word.strip().replace("{", "(").replace("}", ")")
            if token:
                words.append({"start": w.start, "end": w.end, "word": token})
    print(f"[subs] {len(words)} words transcribed")
    return words


def _transcribe_selected(model, video_path: Path, timestamps: list[float],
                         language: str | None) -> list[dict]:
    """Decode only selected audio windows, not hours of audio/features in RAM."""
    if len(timestamps) % 2:
        raise ValueError("Selected timestamps require start/end pairs")
    words = []
    with tempfile.TemporaryDirectory(prefix="ziv_speech_") as tmp:
        audio = Path(tmp) / "window.wav"
        for start, end in zip(timestamps[::2], timestamps[1::2]):
            if not math.isfinite(start + end) or start < 0 or end <= start:
                raise ValueError("Invalid selected audio window")
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error", *lowspec_input_args(), "-ss", str(start),
                "-i", str(video_path), "-t", str(end - start), "-map", "0:a:0",
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio),
            ], check=True, capture_output=True, timeout=300)
            print(f"[subs] Transcribing {start:.1f}-{end:.1f}s")
            segments, info = model.transcribe(
                str(audio), language=language, word_timestamps=True,
                vad_filter=True, beam_size=1)
            # Consume before rewriting the temp file; output stays on source time.
            for segment in segments:
                for word in segment.words or []:
                    token = word.word.strip().replace("{", "(").replace("}", ")")
                    a, b = max(start, start + word.start), min(end, start + word.end)
                    if token and b > a:
                        words.append({"start": a, "end": b, "word": token})
    return words


def _ass_time(seconds: float) -> str:
    """Format as H:MM:SS.CC (centiseconds) for ASS.

    ASS timestamps are centisecond-quantized, and libass switches karaoke
    cells at the same quantization. Rounding UP would sometimes stretch a
    word's tag past the next line's start, stalling the karaoke cursor and
    making highlights lag behind speech — so truncate instead.
    """
    cs = int(max(0.0, seconds) * 100)   # truncate, never round up
    cs = min(cs, 35999999)              # keep it inside a day, just in case
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _prepare_window(words: list[dict], clip_start: float,
                    clip_end: float) -> tuple[list[dict], float]:
    """Words inside the clip window, on the clip's local timeline.

    Copies the word dicts (the caller's list is reused across clips) and
    enforces a sane, strictly forward-moving timeline: whisper + VAD can
    return overlapping or out-of-order word edges, which would desync the
    karaoke cursor.
    """
    clip_len = max(0.0, clip_end - clip_start)
    window = []
    for word in words:
        try:
            raw_start = float(word["start"])
            raw_end = float(word["end"])
            token = str(word["word"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(raw_start) and math.isfinite(raw_end)) or not token:
            continue
        if raw_end <= raw_start:
            continue
        # Cap first, then test overlap. Otherwise a stale long segment can be
        # clipped into a later reel and be incorrectly resurrected at its start.
        raw_end = min(raw_end, raw_start + MAX_WORD_LEN)
        start = max(raw_start, clip_start)
        end = min(raw_end, clip_end)
        if end <= start:
            continue
        token = token.replace("\\", "＼").replace("{", "(").replace("}", ")")
        token = " ".join(token.split())
        window.append({"start": start, "end": end, "word": token})
    window.sort(key=lambda w: w["start"])

    prev_start = clip_start
    for w in window:
        w["start"] = max(w["start"], prev_start)
        w["end"] = min(w["end"], clip_end)
        if w["end"] <= w["start"]:
            continue
        prev_start = w["start"]
        w["_s"] = max(0.0, w["start"] - clip_start)   # clip-local start
        w["_e"] = w["end"] - clip_start               # clip-local end
        # Hormozi captions drop punctuation: pure words, caps, nothing else
        # (commas/periods read as clutter at 96px; braces already neutralised
        # in transcribe because they'd open ASS override blocks).
        w["word"] = w["word"].strip().strip(_PUNCT_EDGES).strip() or w["word"].strip()
    return window, clip_len


def _group_lines(window: list[dict], max_words: int) -> list[list[dict]]:
    """Group words into caption lines.

    Splits on long pauses and on line duration, not just word count, so a
    line never lingers over a silence and never hangs around half a sentence.
    """
    lines: list[list[dict]] = [[window[0]]]
    for w in window[1:]:
        cur = lines[-1]
        gap = w["_s"] - cur[-1]["_e"]
        same_onset = int(w["_s"] * 100) == int(cur[-1]["_s"] * 100)
        if ((len(cur) >= max_words and not same_onset)
                or gap > LINE_SPLIT_GAP
                or w["_s"] - cur[0]["_s"] > LINE_SPLIT_DURATION):
            lines.append([w])
        else:
            cur.append(w)
    return lines


def _split_rows(chunk: list[dict], max_words: int,
                max_chars: int = MAX_LINE_CHARS) -> list[list[dict]]:
    """Split a caption chunk into display rows that fit the frame.

    The Hormozi look uses a huge font, so long groups wrap onto a second row
    (stacked with a hard newline) instead of shrinking or overflowing: the
    highlight flows row to row exactly like the original edits.
    """
    rows: list[list[dict]] = [[]]
    row_chars = 0
    for w in chunk:
        word = w["word"]
        if rows[-1] and (row_chars + 1 + len(word) > max_chars
                         or len(rows[-1]) >= max_words):
            rows.append([])
            row_chars = 0
        rows[-1].append(w)
        row_chars += len(word) + (1 if rows[-1][:-1] else 0)
    return [r for r in rows if r]


def _karaoke_line(rows: list[list[dict]], next_start: float | None, clip_len: float,
                  fade_in: int, fade_out: int, upper: bool,
                  pop_scale: int | None = None) -> tuple[float, float, str]:
    r"""Build one Dialogue line. Returns (start, end, text).

    ASS `\k` advances the karaoke cursor through the following syllable. Word
    i carries the interval from its own onset to the NEXT onset, so the fill
    tracks speech instead of trailing behind it.
    """
    flat = [w for row in rows for w in row]
    start = flat[0]["_s"]
    index = 0
    row_texts: list[str] = []
    for row in rows:
        parts: list[str] = []
        for w in row:
            following = flat[index + 1]["_s"] if index + 1 < len(flat) else w["_e"]
            # Quantize absolute boundaries rather than accumulating rounded
            # intervals; this prevents drift over long lines.
            kcs = max(0, int(following * 100) - int(w["_s"] * 100))
            parts.append(r"{\k%d}%s" % (kcs, w["word"].upper() if upper else w["word"]))
            index += 1
        row_texts.append(" ".join(parts))
    joined = r"\N".join(row_texts)

    # Line ends a beat after the last word, but never past the clip end and
    # never into the next line.
    end = flat[-1]["_e"] + WORD_GLOW
    end = min(end, clip_len)
    if next_start is not None:
        end = min(end, next_start)
    if end <= start:
        end = min(clip_len, start + 0.1)
    if end <= start:
        return start, start, ""

    prefix = ""
    if pop_scale:
        # instant (no fade) scale pop: every word lands with a tiny 1.08x snap,
        # settling immediately — the Hormozi "punch" without animation smear
        pop_ms = 90
        prefix = (r"{\fscx%d\fscy%d\t(0,%d,\fscx100\fscy100)}"
                  % (pop_scale, pop_scale, pop_ms))
    fade = r"{\fad(%d,%d)}" % (fade_in, fade_out)
    return start, end, prefix + fade + joined


def build_ass(words: list[dict], clip_start: float, clip_end: float,
              style_name: str, width: int = 1080, height: int = 1920) -> str:
    """Build a full ASS subtitle file for one clip window."""
    style = STYLES.get(style_name, STYLES["hormozi"])
    font = FONT_OVERRIDE or style["font"]

    window, clip_len = _prepare_window(words, clip_start, clip_end)
    if not window:
        return ""
    lines = _group_lines(window, style["max_words"])

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},{style['font_size']},{style['primary']},{style['secondary']},{style['outline_color']},{style['back']},{-1 if style['bold'] else 0},0,0,0,100,100,0,0,{style['border_style']},{style['outline']},{style['shadow']},{style['alignment']},60,60,{style['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []
    for i, chunk in enumerate(lines):
        next_start = lines[i + 1][0]["_s"] if i + 1 < len(lines) else None
        prev_end = lines[i - 1][-1]["_e"] if i > 0 else None
        # fade only on edges that don't touch another line (no blinking
        # between back-to-back lines)
        fade_in = FADE_MS if (prev_end is None or chunk[0]["_s"] - prev_end > 0.25) else 0
        fade_out = FADE_MS if (next_start is None or next_start - chunk[-1]["_e"] > 0.25) else 0

        if style_name == "hormozi":
            fade_in = fade_out = 0  # avoid blinking on rapid speech
        rows = _split_rows(chunk, style["max_words"])
        start, end, text = _karaoke_line(rows, next_start, clip_len,
                                         fade_in, fade_out, style["uppercase"],
                                         pop_scale=None)
        if int(end * 100) <= int(start * 100):
            continue
        events.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Sub,,0,0,0,,{text}"
        )
    return header + "\n".join(events) + "\n"


def words_for_window(words: list[dict], start: float, end: float) -> list[dict]:
    """Slice the global word list to a clip window."""
    return [w for w in words if w["end"] > start and w["start"] < end]
