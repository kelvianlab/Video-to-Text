"""Zip dist/Video ke Teks into the one file people download.

The zip holds a single top-level folder, so extracting it anywhere gives one
tidy "Video ke Teks" folder instead of scattering files.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from video_to_text import __version__  # noqa: E402

GITHUB_FILE_LIMIT = 2 * 1024**3


def main() -> int:
    app = ROOT / "dist" / "Video ke Teks"
    if not (app / "Video ke Teks.exe").is_file():
        print(f"Nothing to zip: {app} has no exe. Build first.")
        return 1

    import collect_licenses

    if collect_licenses.main() != 0:
        return 1

    target = ROOT / "dist" / f"Video-ke-Teks-{__version__}-Windows.zip"
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                archive.write(path, Path("Video ke Teks") / path.relative_to(app))

    size = target.stat().st_size
    print(f"{target.name}: {size / 1024**2:.0f} MB")
    if size >= GITHUB_FILE_LIMIT:
        print("Too big: GitHub refuses release files of 2 GB or more.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
