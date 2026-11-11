"""The two quality presets, Fast and Thorough.

Every number that changes the result lives here, so the difference between the
two presets can be read in one place.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Quality:
    """One preset the user picks in the window."""

    code: str
    label: str
    """Shown on the radio button."""
    explanation: str
    """Shown under the radio buttons."""

    # Speech side
    speech_model: str
    """Whisper model name. It must be one the app ships with."""
    beam_size: int
    """How many candidate wordings Whisper weighs at each step.

    Measured on two minutes of Indonesian speech with the small model on CPU:
    1 took 39 s, 5 took 69 s, and both read the words correctly. The wider
    search mostly helps with names and rare words.
    """

    # Screen side
    frame_interval_seconds: float
    """How often a screen frame is taken for reading."""
    min_frame_change: float
    """How different a frame must be from the previous one to be read again.

    A value from 0 to 1, compared against the single most-changed tile of the
    screen. The numbers are small because that is their real scale: on actual
    screen recordings a changing counter measures about 0.003 to 0.014, while a
    genuinely still screen measures zero.

    This filter only saves time; it never decides what ends up in the result.
    What decides that is the text comparison. So the threshold is deliberately
    low: better to read a frame that turns out identical than to miss a screen
    that really did change.
    """
    min_confidence: float
    """OCR results below this are dropped as probably misread."""


FAST = Quality(
    code="fast",
    label="Fast",
    explanation=(
        "Almost twice as quick. Good for getting the gist of a video. Names and "
        "rarely used terms are misheard more often."
    ),
    speech_model="small",
    beam_size=1,
    frame_interval_seconds=2.0,
    min_frame_change=0.0030,
    min_confidence=0.60,
)

THOROUGH = Quality(
    code="thorough",
    label="Thorough",
    explanation=(
        "Slower, but mishears less and misses less of the text on screen. "
        "Use this when the result will become notes or a script."
    ),
    speech_model="small",
    beam_size=5,
    frame_interval_seconds=1.0,
    min_frame_change=0.0015,
    min_confidence=0.50,
)

ALL_QUALITIES = (FAST, THOROUGH)


def find_quality(code: str) -> Quality:
    """Look a preset up by its code."""
    for quality in ALL_QUALITIES:
        if quality.code == code:
            return quality
    raise ValueError(f"Unknown quality preset: {code!r}")
