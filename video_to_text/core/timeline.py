"""Merge what was heard and what was shown into one list, in time order.

Every line is labelled SUARA (heard) or LAYAR (shown) so a reader knows where
it came from. When both start at the same second, SUARA goes first, because the
speaker is usually explaining what is on the screen.
"""

from __future__ import annotations

from dataclasses import dataclass

HEARD = "SUARA"
SHOWN = "LAYAR"

_LABEL_ORDER = {HEARD: 0, SHOWN: 1}


@dataclass(frozen=True)
class Line:
    start: float
    end: float
    source: str
    text: str


def merge(speech_segments, screen_segments) -> list[Line]:
    """Put both lists into one, ordered from the start of the video to the end."""
    everything: list[Line] = []
    for segment in speech_segments:
        everything.append(Line(segment.start, segment.end, HEARD, segment.text))
    for segment in screen_segments:
        everything.append(Line(segment.start, segment.end, SHOWN, segment.text))
    everything.sort(key=lambda line: (line.start, _LABEL_ORDER.get(line.source, 9)))
    return everything


def clock(seconds: float, millisecond_separator: str = ",") -> str:
    """Turn seconds into hours:minutes:seconds, the shape .srt files use."""
    seconds = max(0.0, float(seconds))
    whole = int(seconds)
    milliseconds = int(round((seconds - whole) * 1000))
    if milliseconds == 1000:  # rounding can push it up a full second
        whole += 1
        milliseconds = 0
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{millisecond_separator}{milliseconds:03d}"
