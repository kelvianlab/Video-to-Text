# PyInstaller recipe for the self-contained Windows app.
#
# The result is one folder holding "Video ke Teks.exe" and everything it needs:
# Python itself, every library, the video decoder, the OCR models, and the
# speech models. Nothing is installed and nothing is downloaded when it runs.
#
# One folder rather than a single .exe on purpose. A single .exe of this size
# unpacks several hundred MB into the temp folder on every launch, which takes
# tens of seconds and is scanned again by antivirus each time. The folder
# starts straight away.
#
# Build with packaging\build.bat, which fills model\ first.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
MODELS = ROOT / "model"

# Ship exactly the models the presets name, no more. Anything else lying in
# model/ (a larger model tried out for comparison, say) stays out of the app.
import sys
sys.path.insert(0, str(ROOT))
from video_to_text.core.settings import ALL_QUALITIES

needed = sorted({quality.speech_model for quality in ALL_QUALITIES})
speech_models = []
for name in needed:
    folder = MODELS / f"faster-whisper-{name}"
    if not (folder / "model.bin").is_file():
        raise SystemExit(f"{folder} is missing. Run packaging\build.bat, not PyInstaller directly.")
    speech_models.append((str(folder), f"model/{folder.name}"))

ocr_model = MODELS / "ocr" / "en_PP-OCRv3_rec_infer.onnx"
if not ocr_model.is_file():
    raise SystemExit(f"{ocr_model} is missing. Run packaging\\build.bat, not PyInstaller directly.")
speech_models.append((str(ocr_model), "model/ocr"))

datas = (
    speech_models
    + collect_data_files("faster_whisper")          # the voice-activity model
    # include_py_files matters here. RapidOCR puts its own folder on sys.path
    # and imports ch_ppocr_v3_det and the rest by name at run time, so
    # PyInstaller never sees those imports. Without the .py files the folders
    # arrive empty and load as hollow namespace packages: "module
    # 'ch_ppocr_v3_det' has no attribute 'TextDetector'".
    + collect_data_files("rapidocr_onnxruntime", include_py_files=True)
)
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")

a = Analysis(
    [str(ROOT / "packaging" / "start.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    # Imported only by the RapidOCR files above, which PyInstaller cannot trace.
    hiddenimports=["video_to_text.window", "pyclipper", "shapely", "shapely.geometry", "six"],
    excludes=["torch", "tensorflow", "matplotlib", "pandas", "scipy", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Video ke Teks",
    console=False,
    upx=False,   # UPX-packed DLLs are a common antivirus false positive
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="Video ke Teks",
)
