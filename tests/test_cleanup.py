"""Disposable-media cleanup must preserve durable history and source sidecars."""
import json
from pathlib import Path

from ziv.core.cleanup import delete_clip_artifacts, delete_source_artifacts


def test_posted_clip_cleanup_removes_only_generated_sidecars(tmp_path: Path) -> None:
    clip = tmp_path / "reel.mp4"
    sidecars = [clip.with_suffix(".ass"),
                clip.with_name("reel.caption.txt"),
                clip.with_name("reel_cover.jpg")]
    for path in [clip, *sidecars]:
        path.write_bytes(b"generated")
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    removed = delete_clip_artifacts(clip, enabled=True)

    assert set(removed) == {clip, *sidecars}
    assert not any(path.exists() for path in [clip, *sidecars])
    assert manifest.exists()


def test_source_cleanup_removes_download_cache_but_keeps_local_caption_sidecar(tmp_path: Path) -> None:
    local = tmp_path / "source.mp4"
    local_caption = tmp_path / "source.vtt"
    local.write_bytes(b"source")
    local_caption.write_text("WEBVTT", encoding="utf-8")
    delete_source_artifacts(local, enabled=True)
    assert not local.exists()
    assert local_caption.exists()

    downloads = tmp_path / "downloads"
    downloads.mkdir()
    master = downloads / "abc.mp4"
    analysis = downloads / "abc_analysis.mp4"
    metadata = downloads / "abc.json"
    captions = downloads / "abc.en.vtt"
    for path in (master, analysis, captions):
        path.write_bytes(b"generated")
    metadata.write_text(json.dumps({"source_captions": str(captions)}), encoding="utf-8")

    removed = delete_source_artifacts(master, enabled=True)

    assert set(removed) == {master, analysis, metadata, captions}
    assert not any(path.exists() for path in (master, analysis, metadata, captions))
