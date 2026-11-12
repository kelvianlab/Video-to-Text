"""Fetch NVIDIA's CUDA libraries for the NVIDIA edition of the app.

    python packaging/fetch_cuda.py

Downloads NVIDIA's own pip wheel for cuBLAS (about 530 MB, once) and copies
only the two DLLs Whisper needs, plus the licence, into cuda/.

cuDNN is not needed: CTranslate2 runs Whisper on the card with cuBLAS alone.
Measured on an 11.5-minute video, the text with and without cuDNN was identical.

The NVIDIA edition carries that folder; the ordinary edition does not.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "cuda"

# CTranslate2 4.x is built against CUDA 12.
WHEELS = ["nvidia-cublas-cu12==12.9.2.10"]
NEEDED = {"cublas64_12.dll", "cublasLt64_12.dll"}


def _wheels(folder: Path) -> list[Path]:
    found = sorted(folder.glob("nvidia_*.whl"))
    if len(found) < len(WHEELS):
        subprocess.run(
            [sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:",
             "--platform", "win_amd64", "-d", str(folder), *WHEELS],
            check=True,
        )
        found = sorted(folder.glob("nvidia_*.whl"))
    return found


def main(wheel_folder: str | None = None) -> int:
    folder = Path(wheel_folder) if wheel_folder else Path(tempfile.mkdtemp(prefix="cuda-wheels-"))
    TARGET.mkdir(exist_ok=True)
    licenses = TARGET / "licenses"
    licenses.mkdir(exist_ok=True)
    for wheel in _wheels(folder):
        package = wheel.name.split("-")[0]
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.namelist():
                name = member.rsplit("/", 1)[-1]
                if name in NEEDED:
                    destination = TARGET / name
                elif ".dist-info/" in member and name.upper().startswith("LICENSE"):
                    destination = licenses / f"{package}-{name}"
                else:
                    continue
                with archive.open(member) as source, open(destination, "wb") as out:
                    shutil.copyfileobj(source, out)
    total = sum(f.stat().st_size for f in TARGET.rglob("*") if f.is_file())
    print(f"cuda/: {len(list(TARGET.glob('*.dll')))} DLLs, {total / 2**20:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
