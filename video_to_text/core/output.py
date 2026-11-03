"""Write the result as .txt and .srt files next to the video.

A file that already exists is never overwritten. If the name is taken, a number
is added to the end.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .timeline import Line, clock


def free_name(candidate: Path) -> Path:
    """Find a file name that is still free, never overwriting what is there."""
    if not candidate.exists():
        return candidate
    for position in range(2, 1000):
        other = candidate.with_name(f"{candidate.stem} ({position}){candidate.suffix}")
        if not other.exists():
            return other
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return candidate.with_name(f"{candidate.stem} ({stamp}){candidate.suffix}")


def build_txt(lines: list[Line], video_name: str, summary: str) -> str:
    """Build the plain-text file, written for a person to read."""
    parts = [
        f"Hasil penyalinan video: {video_name}",
        f"Dibuat: {datetime.now():%d-%m-%Y %H:%M}",
        summary,
        "",
        "Keterangan label:",
        "  [SUARA] kata-kata yang terdengar di video",
        "  [LAYAR] tulisan yang tampil di layar video",
        "",
        "Hasil ini perkiraan mesin, bukan salinan yang dijamin tepat.",
        "Suara yang bising dan tulisan kecil atau cepat bisa salah atau terlewat.",
        "",
        "-" * 68,
        "",
    ]
    for line in lines:
        at = clock(line.start, millisecond_separator=".")[:-4]  # seconds are enough
        body = line.text.replace("\n", "\n" + " " * 20)
        parts.append(f"[{at}] [{line.source}] {body}")
    if not lines:
        parts.append("(tidak ada suara maupun tulisan layar yang terbaca)")
    return "\n".join(parts) + "\n"


def build_srt(lines: list[Line]) -> str:
    """Build a .srt subtitle file a video player can open."""
    parts: list[str] = []
    for position, line in enumerate(lines, start=1):
        end = max(line.end, line.start + 0.5)  # a subtitle needs some duration
        parts.append(str(position))
        parts.append(f"{clock(line.start)} --> {clock(end)}")
        parts.append(f"[{line.source}] {line.text}")
        parts.append("")
    return "\n".join(parts)


def save(video: Path, lines: list[Line], summary: str) -> tuple[Path, Path]:
    """Write the .txt and .srt next to the video. Returns where both landed."""
    video = Path(video)
    txt_file = free_name(video.with_suffix(".txt"))
    srt_file = free_name(video.with_suffix(".srt"))

    txt_file.write_text(build_txt(lines, video.name, summary), encoding="utf-8")
    srt_file.write_text(build_srt(lines), encoding="utf-8")
    return txt_file, srt_file
