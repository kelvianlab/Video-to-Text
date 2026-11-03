"""Turn the video's audio into text with Whisper.

Uses faster-whisper, which does not need PyTorch. An NVIDIA card is used when
one is genuinely usable; otherwise the work falls back to the processor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_loaded_models: dict[tuple[str, str], object] = {}


@dataclass(frozen=True)
class SpeechSegment:
    start: float
    end: float
    text: str


class SpeechError(Exception):
    """The speech model could not be used."""


def gpu_usable() -> bool:
    """Check that the graphics card really works, not merely that one exists."""
    try:
        from faster_whisper import WhisperModel

        WhisperModel("tiny", device="cuda", compute_type="float16")
        return True
    except Exception:
        return False


def _import_whisper():
    """Import faster-whisper, or explain in plain words how to install it.

    A bare ModuleNotFoundError tells a non-technical user nothing, and it is the
    most likely thing to go wrong: on a machine with several Pythons, the app can
    start on one that has no components installed.
    """
    try:
        from faster_whisper import WhisperModel

        return WhisperModel
    except ImportError as error:
        import sys

        # The original text is kept. An ImportError here is not always a missing
        # package: a native library that fails to load reports itself the same
        # way, and hiding that leaves nothing to act on.
        raise SpeechError(
            "Komponen pembaca suara tidak bisa dimuat.\n\n"
            f"Keterangan asli dari Python:\n{type(error).__name__}: {error}\n\n"
            f"Python yang dipakai sekarang:\n{sys.executable}\n\n"
            "Kalau keterangan di atas menyebut modul yang hilang, jalankan sekali:\n"
            f'"{sys.executable}" -m pip install faster-whisper'
        ) from error


def _load_model(name: str, use_gpu: bool):
    """Prepare a model and keep it, so the next video does not reload it."""
    device = "cuda" if use_gpu else "cpu"
    precision = "float16" if use_gpu else "int8"
    key = (name, device)
    if key not in _loaded_models:
        WhisperModel = _import_whisper()

        try:
            _loaded_models[key] = WhisperModel(name, device=device, compute_type=precision)
        except Exception as error:
            if use_gpu:
                return _load_model(name, use_gpu=False)
            raise SpeechError(
                f"Model suara {name!r} tidak bisa disiapkan: {str(error)[:200]}"
            ) from error
    return _loaded_models[key]


def transcribe(
    wav_file: Path,
    model_name: str,
    use_gpu: bool = True,
    language: str | None = None,
    report: Callable[[float], None] | None = None,
) -> list[SpeechSegment]:
    """Turn audio into timed segments of speech.

    *report* is called with the last second finished, so the window can show
    progress while the work runs.
    """
    model = _load_model(model_name, use_gpu)
    segments, _ = model.transcribe(
        str(wav_file),
        language=language,
        vad_filter=True,
        beam_size=5,
    )

    found: list[SpeechSegment] = []
    for segment in segments:
        text = (segment.text or "").strip()
        if text:
            found.append(SpeechSegment(float(segment.start), float(segment.end), text))
        if report:
            report(float(segment.end))
    return found
