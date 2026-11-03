"""Read the text that appears on screen in a video, using OCR.

Two filters keep the same screen from being written down over and over, and
keep the work from taking longer than it needs to:

1. Before a frame is read, it is compared with the previous one. If the screen
   has not changed, the frame is skipped without being read at all. This is
   where nearly all the time is saved, because comparing two frames is far
   cheaper than running OCR on one.
2. After a frame is read, its text is compared with the previous text. If they
   say the same thing, nothing new is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_reader = None

FINGERPRINT_SIDE = 128
TILES = 16  # the screen is split into TILES x TILES parts, 8x8 dots each

# These sizes were chosen after measuring real screen recordings. At 32x32
# averaged over the whole screen, a changing counter measured 0.0001, which
# cannot be told apart from a still screen. At 128x128 by tile, the same change
# measures 0.003 to 0.014, which is clearly not zero.


@dataclass(frozen=True)
class ScreenSegment:
    start: float
    end: float
    text: str


class ScreenError(Exception):
    """The screen-text reader could not be used."""


def _get_reader():
    global _reader
    if _reader is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as error:
            import sys

            # Same reasoning as in speech.py: keep the original text, because a
            # native library that fails to load looks exactly like a missing one.
            raise ScreenError(
                "Komponen pembaca tulisan layar tidak bisa dimuat.\n\n"
                f"Keterangan asli dari Python:\n{type(error).__name__}: {error}\n\n"
                f"Python yang dipakai sekarang:\n{sys.executable}\n\n"
                "Kalau keterangan di atas menyebut modul yang hilang, jalankan sekali:\n"
                f'"{sys.executable}" -m pip install rapidocr-onnxruntime pillow'
            ) from error
        _reader = RapidOCR()
    return _reader


def _fingerprint(path: Path, side: int = FINGERPRINT_SIDE) -> list[int]:
    """Reduce a frame to a small grey square, used only for comparing frames."""
    from PIL import Image

    with Image.open(path) as picture:
        small = picture.convert("L").resize((side, side), Image.BILINEAR)
        return list(small.getdata())


def frame_difference(first: list[int] | None, second: list[int] | None) -> float:
    """How different two frames are, from 0 (identical) to 1 (nothing alike).

    What comes back is the single most-changed tile, not the average over the
    whole screen. The reason: the changes worth catching often occupy only a
    small patch, such as a "Discovered 8,046 items" counter or one new line in
    a terminal. Averaged across the screen, a change that small disappears and
    the frame looks unchanged, when that patch is exactly where the content is.
    """
    if not first or not second or len(first) != len(second):
        return 1.0

    side = FINGERPRINT_SIDE
    tile_width = side // TILES
    largest = 0.0

    for tile_y in range(TILES):
        for tile_x in range(TILES):
            total = 0
            for row in range(tile_width):
                start = (tile_y * tile_width + row) * side + tile_x * tile_width
                for offset in range(tile_width):
                    total += abs(first[start + offset] - second[start + offset])
            difference = total / (tile_width * tile_width * 255)
            if difference > largest:
                largest = difference
    return largest


def tidy_text(lines: list[str]) -> str:
    """Join OCR lines into one block, dropping the empty ones."""
    kept = [line.strip() for line in lines if line and line.strip()]
    return "\n".join(kept)


def numbers_in(text: str) -> list[str]:
    """Pull out every number, without the dots and commas that group digits."""
    import re

    return [
        match.replace(".", "").replace(",", "")
        for match in re.findall(r"\d[\d.,]*", text)
    ]


def same_screen(first: str, second: str, threshold: float = 0.985) -> bool:
    """Decide whether two screens say the same thing.

    Both of these must hold:

    1. Every number matches exactly. This matters because a screen that changes
       only in its numbers, such as a progress counter or a remaining time, is
       precisely the change worth recording. Without this rule those numbers are
       swallowed, since the surrounding text is identical.
    2. The rest of the text is near enough identical. The threshold is high so
       that only small misreadings, such as one wrong letter, count as the same.
    """
    import difflib

    left = " ".join(first.split()).lower()
    right = " ".join(second.split()).lower()
    if not left or not right:
        return left == right
    if left == right:
        return True
    if numbers_in(left) != numbers_in(right):
        return False
    return difflib.SequenceMatcher(None, left, right).ratio() >= threshold


def read_screens(
    timed_frames: list[tuple[float, Path]],
    min_frame_change: float,
    min_confidence: float,
    interval_seconds: float,
    report: Callable[[int, int, int], None] | None = None,
) -> list[ScreenSegment]:
    """Read the text from a list of screen frames, skipping screens that held still.

    Each result carries the time it appeared and the time the screen changed again.
    """
    reader = _get_reader()
    found: list[ScreenSegment] = []
    previous_fingerprint: list[int] | None = None
    previous_text = ""
    appeared_at = 0.0
    total = len(timed_frames)
    read_count = 0

    for position, (seconds, path) in enumerate(timed_frames):
        if report:
            report(position + 1, total, read_count)

        fingerprint = _fingerprint(path)
        if frame_difference(previous_fingerprint, fingerprint) < min_frame_change:
            continue  # the screen has not changed, no need to read it again
        previous_fingerprint = fingerprint

        read_count += 1
        reading, _ = reader(str(path))
        lines = [
            text
            for _, text, confidence in (reading or [])
            if float(confidence) >= min_confidence
        ]
        text = tidy_text(lines)
        if not text:
            continue
        if previous_text and same_screen(previous_text, text):
            continue  # same words, only shifted slightly or misread

        if previous_text:
            found.append(ScreenSegment(appeared_at, seconds, previous_text))
        previous_text = text
        appeared_at = seconds

    if previous_text:
        ended_at = timed_frames[-1][0] + interval_seconds if timed_frames else appeared_at
        found.append(ScreenSegment(appeared_at, ended_at, previous_text))
    return found
