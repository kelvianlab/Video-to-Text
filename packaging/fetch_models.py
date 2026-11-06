"""Put the speech models into model/ so the build can pack them inside the app.

Run once before building. A model already in model/ is left alone, so a second
build downloads nothing. This is the only step anywhere that touches the
internet, and it happens on the build machine, never on the user's.

    python packaging/fetch_models.py small
"""

from __future__ import annotations

import sys
from pathlib import Path

FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
ROOT = Path(__file__).resolve().parents[1]


def fetch(name: str) -> None:
    target = ROOT / "model" / f"faster-whisper-{name}"
    if (target / "model.bin").is_file():
        print(f"{name}: already present")
        return
    from huggingface_hub import snapshot_download

    print(f"{name}: downloading from Systran/faster-whisper-{name} ...")
    snapshot_download(
        f"Systran/faster-whisper-{name}", local_dir=str(target), allow_patterns=FILES
    )
    missing = [f for f in FILES if not (target / f).is_file()]
    if missing:
        raise SystemExit(f"{name}: incomplete, missing {missing}")
    print(f"{name}: done")


def fetch_ocr() -> None:
    """PaddleOCR's Latin text model, as converted by the RapidOCR project."""
    target = ROOT / "model" / "ocr" / "en_PP-OCRv3_rec_infer.onnx"
    if target.is_file():
        print("ocr: already present")
        return
    import shutil

    from huggingface_hub import hf_hub_download

    print("ocr: downloading en_PP-OCRv3_rec_infer.onnx from SWHL/RapidOCR ...")
    source = hf_hub_download("SWHL/RapidOCR", "PP-OCRv3/en_PP-OCRv3_rec_infer.onnx")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    print("ocr: done")


if __name__ == "__main__":
    for model_name in sys.argv[1:] or ["small"]:
        fetch(model_name)
    fetch_ocr()
