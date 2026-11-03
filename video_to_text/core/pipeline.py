"""The main run: one video in, a .txt and a .srt out.

The order is:
    extract audio -> read speech -> take screen frames -> read screens
    -> merge by time -> save

Working files go in the system's temporary folder and are deleted afterwards.
The source video is never opened for writing.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import media, screen, speech
from .output import save
from .settings import Quality
from .timeline import Line, merge


@dataclass
class VideoResult:
    video: Path
    txt_file: Path | None = None
    srt_file: Path | None = None
    speech_count: int = 0
    screen_count: int = 0
    frames_checked: int = 0
    frames_read: int = 0
    used_gpu: bool = False
    had_audio: bool = True
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def _summary(quality: Quality, result: VideoResult) -> str:
    """One line describing how the result was produced. Shown to the user."""
    if not result.had_audio:
        speech_part = "Video tanpa suara, jadi hanya tulisan layar yang dibaca."
    else:
        device = "kartu grafis NVIDIA" if result.used_gpu else "prosesor (CPU)"
        speech_part = (
            f"Suara dibaca model {quality.speech_model} dengan {device}: "
            f"{result.speech_count} potongan."
        )
    return (
        f"Mutu: {quality.label}. {speech_part} "
        f"Layar: {result.screen_count} tampilan dari {result.frames_checked} gambar."
    )


def process_video(
    video: Path,
    quality: Quality,
    use_gpu: bool = True,
    language: str | None = None,
    report: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> VideoResult:
    """Run one video all the way through to saved files."""
    video = Path(video)
    result = VideoResult(video=video)
    say = report or (lambda message: None)
    stop_now = should_stop or (lambda: False)

    workspace = Path(tempfile.mkdtemp(prefix="video_to_text_"))
    try:
        details = media.read_details(video)
        result.had_audio = details.has_audio

        speech_segments: list = []
        if details.has_audio:
            say("Mengambil suara dari video...")
            wav_file = media.extract_audio(video, workspace / "audio.wav")
            if stop_now():
                result.error = "Dihentikan oleh pengguna."
                return result

            say("Membaca suara menjadi teks...")
            result.used_gpu = use_gpu and speech.gpu_usable()
            speech_segments = speech.transcribe(
                wav_file,
                quality.speech_model,
                use_gpu=result.used_gpu,
                language=language,
                report=lambda second: say(f"Membaca suara... detik ke-{int(second)}"),
            )
        else:
            result.notes.append("Video ini tidak punya suara, jadi hanya layar yang dibaca.")

        if stop_now():
            result.error = "Dihentikan oleh pengguna."
            return result

        say("Mengambil gambar layar...")
        frames = media.extract_frames(
            video, workspace / "frames", quality.frame_interval_seconds
        )
        result.frames_checked = len(frames)

        say("Membaca tulisan di layar...")
        counter = {"read": 0}

        def report_screens(done: int, total: int, read_so_far: int) -> None:
            counter["read"] = read_so_far
            say(f"Membaca tulisan layar... gambar {done} dari {total}")

        screen_segments = screen.read_screens(
            frames,
            min_frame_change=quality.min_frame_change,
            min_confidence=quality.min_confidence,
            interval_seconds=quality.frame_interval_seconds,
            report=report_screens,
        )
        result.frames_read = counter["read"]

        result.speech_count = len(speech_segments)
        result.screen_count = len(screen_segments)

        lines: list[Line] = merge(speech_segments, screen_segments)
        say("Menyimpan hasil...")
        result.txt_file, result.srt_file = save(video, lines, _summary(quality, result))
        return result

    except Exception as error:
        result.error = f"{type(error).__name__}: {error}"
        return result
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
