"""Entry point.

With no arguments, the window opens:
    python -m video_to_text

Headless, for scripts and scheduled runs:
    python -m video_to_text --run "D:\\Video" --quality thorough

Exit codes: 0 all done, 1 some failed, 2 the request could not be carried out.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv[:1] == ["--run"]:
        return _headless(argv[1:])

    from .window import run_app

    run_app()
    return 0


def _headless(argv: list[str]) -> int:
    from .core import media
    from .core.pipeline import process_video
    from .core.settings import find_quality

    if not argv:
        print('Usage: python -m video_to_text --run PATH [--quality fast|thorough]')
        return 2

    location = Path(argv[0])
    quality_code = "fast"
    if "--quality" in argv:
        position = argv.index("--quality")
        if position + 1 >= len(argv):
            print("--quality needs to be followed by fast or thorough.")
            return 2
        quality_code = argv[position + 1]

    try:
        quality = find_quality(quality_code)
    except ValueError as error:
        print(error)
        return 2

    if not media.ffmpeg_available():
        print("ffmpeg was not found. Install ffmpeg first.")
        return 2

    videos = media.find_videos(location)
    if not videos:
        print(f"No video found at: {location}")
        return 2

    anything_failed = False
    for position, video in enumerate(videos, start=1):
        print(f"[{position}/{len(videos)}] {video.name}")
        result = process_video(video, quality, report=lambda message: print("   ", message))
        if result.error:
            anything_failed = True
            print("    FAILED:", result.error)
        else:
            print(f"    Done: {result.txt_file.name}, {result.srt_file.name}")
    return 1 if anything_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
