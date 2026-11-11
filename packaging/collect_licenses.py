"""Put every bundled component's licence into the app folder.

The packaged app carries other people's code and models inside it, so their
licences have to travel with it. This works out which Python distributions
actually ended up in the bundle (by the folders PyInstaller wrote), copies each
one's licence files, and writes THIRD-PARTY-NOTICES.txt beside the exe.

Run after PyInstaller, before zipping. make_zip.py calls it.
"""

from __future__ import annotations

import shutil
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dist" / "Video to Text"
INTERNAL = APP / "_internal"
LICENSES = INTERNAL / "licenses"

# Parts that are not Python distributions, or whose licence the wheel does not
# describe fully. Stated by hand, each with where its source can be had.
EXTRA = [
    (
        "Python",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "PSF-2.0",
        "https://www.python.org/",
        "The Python runtime the app runs on.",
    ),
    (
        "FFmpeg (inside PyAV, folder _internal/av.libs)",
        "as shipped in PyAV's Windows wheel",
        "LGPL-3.0-or-later",
        "https://ffmpeg.org/ ; build scripts: https://github.com/PyAV-Org/PyAV",
        "Used only to read video and audio.",
    ),
    (
        "x264 and x265 (inside PyAV, folder _internal/av.libs)",
        "as shipped in PyAV's Windows wheel",
        "GPL-2.0-or-later",
        "https://code.videolan.org/videolan/x264 ; https://bitbucket.org/multicoreware/x265_git",
        "Video encoders that FFmpeg is linked against. This app only reads video "
        "and never calls them, but the files are present, so their licence applies "
        "to them and their source is available at the addresses given.",
    ),
    (
        "Whisper small model (converted by Systran)",
        "faster-whisper-small",
        "MIT",
        "https://huggingface.co/Systran/faster-whisper-small ; original: https://github.com/openai/whisper",
        "The speech model, in _internal/model/faster-whisper-small.",
    ),
    (
        "PaddleOCR models (converted by RapidOCR)",
        "PP-OCRv3 detection, Latin recognition; PP-OCR v2 direction classifier",
        "Apache-2.0",
        "https://github.com/PaddlePaddle/PaddleOCR ; https://huggingface.co/SWHL/RapidOCR",
        "The on-screen text models.",
    ),
]


def bundled_distributions() -> list[metadata.Distribution]:
    """Distributions that own at least one top-level folder or file in _internal."""
    owners = metadata.packages_distributions()
    present = {path.name.split(".")[0] for path in INTERNAL.iterdir()}
    names = sorted({dist for top in present for dist in owners.get(top, [])}, key=str.lower)
    found = []
    for name in names:
        try:
            found.append(metadata.distribution(name))
        except metadata.PackageNotFoundError:
            pass
    return found


def licence_text(dist: metadata.Distribution) -> str:
    """The licence as the package declares it, from the most precise field it has."""
    expression = dist.metadata.get("License-Expression")
    if expression:
        return expression
    declared = (dist.metadata.get("License") or "").strip()
    if declared and len(declared) < 80:  # some packages paste the whole text here
        return declared.splitlines()[0]
    for classifier in dist.metadata.get_all("Classifier") or []:
        if classifier.startswith("License ::"):
            return classifier.split("::")[-1].strip()
    return "see the project page"


def home(dist: metadata.Distribution) -> str:
    for entry in dist.metadata.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("source", "source code", "repository", "homepage", "home"):
            return url.strip()
    return dist.metadata.get("Home-page") or f"https://pypi.org/project/{dist.metadata['Name']}/"


def main() -> int:
    if not INTERNAL.is_dir():
        print(f"{INTERNAL} not found. Build first.")
        return 1
    shutil.rmtree(LICENSES, ignore_errors=True)
    LICENSES.mkdir(parents=True)

    rows = []
    for dist in bundled_distributions():
        name = dist.metadata["Name"]
        copied = 0
        for file in dist.files or []:
            text = str(file).lower()
            if any(word in text for word in ("licen", "copying", "notice", "authors")) and not text.endswith((".py", ".pyc")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = LICENSES / name / Path(file).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    copied += 1
        where = f"_internal/licenses/{name}/" if copied else home(dist)
        rows.append((name, dist.version, licence_text(dist), where))

    lines = [
        "Video to Text - third-party notices",
        "=" * 36,
        "",
        "Video to Text itself is released under the MIT licence (see LICENSE.txt).",
        "The app folder also carries the following work by others, each under its",
        "own licence. Licence texts that the components ship with are copied into",
        "_internal/licenses/. Nothing here was modified.",
        "",
        "Components",
        "----------",
    ]
    for name, version, licence, where, note in EXTRA:
        lines += [f"{name}", f"    version: {version}", f"    licence: {licence}", f"    source:  {where}", f"    {note}", ""]
    lines += ["Python libraries", "----------------"]
    for name, version, licence, where in rows:
        lines += [f"{name} {version}", f"    licence: {licence}", f"    texts:   {where}", ""]

    (APP / "THIRD-PARTY-NOTICES.txt").write_text("\n".join(lines), encoding="utf-8")
    shutil.copyfile(ROOT / "LICENSE", APP / "LICENSE.txt")
    print(f"{len(rows)} libraries, {len(EXTRA)} other components; notices written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
