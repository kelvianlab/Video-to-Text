"""The main run: one video in, a .txt and a .srt out.

The order is:
    load audio -> read speech -> take screen frames -> read screens
    -> merge by time -> save

Screen frames go in the system's temporary folder and are deleted afterwards.
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
    language: str = ""
    language_was_detected: bool = False
    had_audio: bool = True
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def counted(number: int, singular: str, plural: str | None = None) -> str:
    """"1 piece", "2 pieces": English needs the count and the noun to agree."""
    return f"{number} {singular if number == 1 else (plural or singular + 's')}"


def _summary(quality: Quality, result: VideoResult) -> str:
    """One line describing how the result was produced. Shown to the user."""
    if not result.had_audio:
        speech_part = "Video has no sound, so only the screen text was read."
    else:
        device = "NVIDIA graphics card" if result.used_gpu else "processor (CPU)"
        name = speech.LANGUAGE_NAMES.get(result.language, result.language)
        how = "chosen automatically" if result.language_was_detected else "chosen by user"
        speech_part = (
            f"Speech in {name} ({how}), read by the {quality.speech_model} model "
            f"on the {device}: {counted(result.speech_count, 'piece')}."
        )
    return (
        f"Quality: {quality.label}. {speech_part} "
        f"Screen: {counted(result.screen_count, 'entry', 'entries')} "
        f"from {counted(result.frames_checked, 'picture')}."
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
            say("Taking the sound from the video...")
            audio = media.load_audio(video)
            if stop_now():
                result.error = "Stopped by the user."
                return result

            say("Turning speech into text...")
            speech_result = speech.transcribe(
                audio,
                quality.speech_model,
                use_gpu=use_gpu,
                language=language,
                beam_size=quality.beam_size,
                report=lambda second: say(f"Reading speech... second {int(second)}"),
            )
            speech_segments = speech_result.segments
            result.used_gpu = speech_result.used_gpu
            result.language = speech_result.language
            result.language_was_detected = speech_result.language_was_detected
            if speech_result.gpu_note:
                result.notes.append(
                    "An NVIDIA graphics card is present but could not be used, so the "
                    "processor read the speech. Same result, just slower. "
                    f"Technical detail: {speech_result.gpu_note[:120]}"
                )
        else:
            result.notes.append("This video has no sound, so only the screen was read.")

        if stop_now():
            result.error = "Stopped by the user."
            return result

        say("Taking screen pictures...")
        frames = media.extract_frames(
            video, workspace / "frames", quality.frame_interval_seconds
        )
        result.frames_checked = len(frames)

        say("Reading the text on screen...")
        counter = {"read": 0}

        def report_screens(done: int, total: int, read_so_far: int) -> None:
            counter["read"] = read_so_far
            say(f"Reading screen text... picture {done} of {total}")

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
        say("Saving the results...")
        result.txt_file, result.srt_file = save(video, lines, _summary(quality, result))
        return result

    except Exception as error:
        result.error = f"{type(error).__name__}: {error}"
        return result
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
