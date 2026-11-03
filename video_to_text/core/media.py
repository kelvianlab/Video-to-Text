"""Everything that touches the video file: reading its details, pulling the
audio out, and taking screen frames.

All of it is done by ffmpeg. The source video is only ever read, never written
to or modified.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VIDEO_SUFFIXES = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".ts",
}

# Keeps a black ffmpeg console from flashing up in front of the user on Windows.
_HIDE_CONSOLE = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class MediaError(Exception):
    """ffmpeg could not carry out the request."""


@dataclass(frozen=True)
class VideoDetails:
    duration_seconds: float
    width: int
    height: int
    has_audio: bool


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_HIDE_CONSOLE,
    )


def find_videos(location: Path) -> list[Path]:
    """Collect videos from a single file, or from a folder and everything under it."""
    location = Path(location)
    if location.is_file():
        return [location] if location.suffix.lower() in VIDEO_SUFFIXES else []
    if not location.is_dir():
        return []
    return [
        item
        for item in sorted(location.rglob("*"))
        if item.is_file() and item.suffix.lower() in VIDEO_SUFFIXES
    ]


def read_details(video: Path) -> VideoDetails:
    """Read duration, frame size, and whether the video carries any audio."""
    result = _run([
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(video),
    ])
    if result.returncode != 0:
        raise MediaError(f"Video tidak bisa dibaca: {result.stderr.strip()[:200]}")

    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    picture = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    duration = data.get("format", {}).get("duration")
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = 0.0

    return VideoDetails(
        duration_seconds=duration,
        width=int(picture.get("width") or 0),
        height=int(picture.get("height") or 0),
        has_audio=has_audio,
    )


def extract_audio(video: Path, target_wav: Path) -> Path:
    """Copy the video's audio into 16 kHz mono WAV, the shape Whisper expects."""
    target_wav.parent.mkdir(parents=True, exist_ok=True)
    result = _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(target_wav),
    ])
    if result.returncode != 0 or not target_wav.exists():
        raise MediaError(f"Suara tidak bisa diambil: {result.stderr.strip()[:200]}")
    return target_wav


def extract_frames(
    video: Path,
    target_folder: Path,
    interval_seconds: float,
    width: int = 1280,
) -> list[tuple[float, Path]]:
    """Take a screen frame every *interval_seconds*, scaled down so OCR runs faster.

    Returns (seconds into the video, frame file), in time order.
    """
    target_folder.mkdir(parents=True, exist_ok=True)
    rate = 1.0 / max(interval_seconds, 0.05)
    result = _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video),
        # format=yuvj420p is not decoration. Videos that carry a limited colour
        # range, which most downloaded video does, make the JPEG encoder refuse
        # outright: "Non full-range YUV is non-standard". Converting here means
        # every video is handed over in the one form the encoder accepts.
        "-vf", f"fps={rate},scale={width}:-2:flags=bicubic,format=yuvj420p",
        "-q:v", "3",
        str(target_folder / "frame_%06d.jpg"),
    ])
    if result.returncode != 0:
        raise MediaError(f"Gambar layar tidak bisa diambil: {result.stderr.strip()[:200]}")

    frames = sorted(target_folder.glob("frame_*.jpg"))
    # Frame n stands for second (n - 0.5) * interval, the middle of its slice.
    return [
        ((position + 0.5) * interval_seconds, path)
        for position, path in enumerate(frames)
    ]
