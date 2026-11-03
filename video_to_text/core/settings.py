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
    """Shown on the radio button, in Indonesian."""
    explanation: str
    """Shown under the radio buttons, in Indonesian."""

    # Speech side
    speech_model: str
    """Whisper model name. Bigger is more accurate but slower."""
    download_size: str
    """Model download size, shown to the user before anything is downloaded."""

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
    label="Cepat",
    explanation=(
        "Kira-kira 3 sampai 4 kali lebih cepat. Cocok untuk melihat isi video "
        "secara garis besar. Kata yang jarang dipakai dan tulisan kecil di layar "
        "lebih sering salah."
    ),
    speech_model="small",
    download_size="484 MB",
    frame_interval_seconds=2.0,
    min_frame_change=0.0030,
    min_confidence=0.60,
)

THOROUGH = Quality(
    code="thorough",
    label="Teliti",
    explanation=(
        "Lebih lambat, tetapi lebih jarang salah dengar dan lebih jarang "
        "melewatkan tulisan di layar. Pakai ini kalau hasilnya mau dijadikan "
        "catatan atau naskah."
    ),
    speech_model="medium",
    download_size="1,5 GB",
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
