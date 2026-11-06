"""Everything that touches the video file: reading its details, pulling the
audio out, and taking screen frames.

All of it goes through PyAV, which carries ffmpeg's own decoders inside it.
PyAV is already a requirement of the speech reader, so using it here means the
app needs no separate ffmpeg program: nothing to install, nothing to find on
PATH, and about 440 MB less to ship.

The source video is only ever opened for reading, never written to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VIDEO_SUFFIXES = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".ts",
}

SPEECH_SAMPLE_RATE = 16000
"""Whisper is trained on 16 kHz mono audio, so that is what it is given."""


class MediaError(Exception):
    """The video could not be read."""


@dataclass(frozen=True)
class VideoDetails:
    duration_seconds: float
    width: int
    height: int
    has_audio: bool


def _open(video: Path):
    import av

    try:
        return av.open(str(video), mode="r")
    except Exception as error:
        raise MediaError(f"Video tidak bisa dibuka: {type(error).__name__}: {error}") from error


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
    with _open(video) as container:
        picture = next((s for s in container.streams if s.type == "video"), None)
        has_audio = any(s.type == "audio" for s in container.streams)
        duration = container.duration / 1_000_000 if container.duration else 0.0
        return VideoDetails(
            duration_seconds=float(duration),
            width=int(picture.codec_context.width) if picture else 0,
            height=int(picture.codec_context.height) if picture else 0,
            has_audio=has_audio,
        )


def _decoded(container, stream):
    """Yield decoded frames, stepping over damaged packets instead of stopping.

    Downloaded and screen-recorded video often has a few broken packets. One of
    them should cost a fraction of a second of picture or sound, not the whole
    video.
    """
    import av

    for packet in container.demux(stream):
        try:
            yield from packet.decode()
        except av.error.InvalidDataError:
            continue


def load_audio(video: Path):
    """Return the video's sound as 16 kHz mono float samples, ready for Whisper."""
    import av
    import numpy as np

    with _open(video) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise MediaError("Video ini tidak punya suara.")

        resampler = av.AudioResampler(format="s16", layout="mono", rate=SPEECH_SAMPLE_RATE)
        pieces = []
        for frame in _decoded(container, stream):
            for converted in resampler.resample(frame):
                pieces.append(converted.to_ndarray().reshape(-1))
        for converted in resampler.resample(None):  # what the resampler still holds
            pieces.append(converted.to_ndarray().reshape(-1))

    if not pieces:
        raise MediaError("Suara di video ini tidak bisa dibaca sama sekali.")
    return np.concatenate(pieces).astype(np.float32) / 32768.0


def extract_frames(
    video: Path,
    target_folder: Path,
    interval_seconds: float,
    width: int = 1280,
) -> list[tuple[float, Path]]:
    """Save a screen frame every *interval_seconds*, scaled down so OCR runs faster.

    Returns (seconds into the video, frame file), in time order. The time is
    the frame's own timestamp, so it stays right even when the video's frame
    rate wanders, which screen recordings often do.

    Colour is converted by frame.to_image(), which handles the limited colour
    range that most downloaded video carries. The ffmpeg JPEG encoder refused
    that outright; this path never meets the problem.
    """
    from PIL import Image

    target_folder.mkdir(parents=True, exist_ok=True)
    interval = max(interval_seconds, 0.05)
    taken: list[tuple[float, Path]] = []

    with _open(video) as container:
        stream = next((s for s in container.streams if s.type == "video"), None)
        if stream is None:
            raise MediaError("Video ini tidak punya gambar.")
        stream.thread_type = "AUTO"  # decode on every core

        # Sample the middle of each slice, as the old ffmpeg fps filter did. The
        # very first frame of a video is often still fading in, and OCR on it
        # measured noticeably worse: words ran together without spaces.
        next_at = interval / 2
        for frame in _decoded(container, stream):
            seconds = frame.time
            if seconds is None or seconds < next_at:
                continue
            picture = frame.to_image()
            if picture.width > width:
                height = max(2, round(picture.height * width / picture.width))
                picture = picture.resize((width, height), Image.BICUBIC)
            path = target_folder / f"frame_{len(taken) + 1:06d}.jpg"
            picture.save(path, quality=92)
            taken.append((float(seconds), path))
            # Step forward from the planned time, not from this frame's time, so
            # small timestamp jitter does not slowly push every sample later.
            while next_at <= seconds:
                next_at += interval

    return taken
