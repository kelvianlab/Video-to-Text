"""Zip dist/Video to Text into the one file people download.

    python packaging/make_zip.py            ordinary edition
    python packaging/make_zip.py --nvidia   adds cuda/ for NVIDIA cards

The zip holds a single top-level folder, so extracting it anywhere gives one
tidy "Video to Text" folder instead of scattering files.
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


def main(nvidia: bool = False) -> int:
    app = ROOT / "dist" / "Video to Text"
    if not (app / "Video to Text.exe").is_file():
        print(f"Nothing to zip: {app} has no exe. Build first.")
        return 1

    import collect_licenses

    if collect_licenses.main() != 0:
        return 1

    cuda = ROOT / "cuda"
    if nvidia and not any(cuda.glob("*.dll")):
        print("No cuda/ folder. Run packaging/fetch_cuda.py first.")
        return 1
    edition = "-NVIDIA" if nvidia else ""
    target = ROOT / "dist" / f"Video-to-Text-{__version__}-Windows{edition}.zip"
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                archive.write(path, Path("Video to Text") / path.relative_to(app))
        if nvidia:
            # Lands at _internal/cuda, where speech.cuda_folder() looks.
            for path in sorted(cuda.rglob("*")):
                if path.is_file():
                    archive.write(path, Path("Video to Text") / "_internal" / "cuda" / path.relative_to(cuda))

    size = target.stat().st_size
    print(f"{target.name}: {size / 1024**2:.0f} MB")
    if size >= GITHUB_FILE_LIMIT:
        print("Too big: GitHub refuses release files of 2 GB or more.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(nvidia="--nvidia" in sys.argv))
