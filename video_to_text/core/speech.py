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
    """Check that the graphics card really works, not merely that one exists.

    This has to run an actual transcription, not just build the model. Building
    one succeeds on a machine whose CUDA maths libraries are missing, because
    cuBLAS is only loaded once there is something to compute; the failure then
    lands in the middle of a real video instead of here.
    """
    try:
        import numpy as np
        from faster_whisper import WhisperModel

        model = WhisperModel("tiny", device="cuda", compute_type="float16")
        silence = np.zeros(16000, dtype=np.float32)  # one second
        list(model.transcribe(silence, beam_size=1)[0])
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


def read_wav(wav_file: Path):
    """Read a 16 kHz mono 16-bit WAV into the float array Whisper expects.

    Doing this here rather than handing Whisper the file path keeps PyAV out of
    the picture entirely. faster-whisper otherwise decodes the file itself by
    calling av.open(..., metadata_errors=...), an argument PyAV 19 removed, so
    the two break against each other even though their declared versions agree.
    Since media.extract_audio already produced this exact WAV with ffmpeg, there
    is nothing left for a second decoder to do.
    """
    import wave

    import numpy as np

    with wave.open(str(wav_file), "rb") as handle:
        if handle.getsampwidth() != 2 or handle.getnchannels() != 1:
            raise SpeechError(
                "Berkas suara sementara tidak sesuai dugaan "
                f"({handle.getnchannels()} kanal, {handle.getsampwidth() * 8} bit)."
            )
        frames = handle.readframes(handle.getnframes())

    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(
    wav_file: Path,
    model_name: str,
    use_gpu: bool = True,
    language: str | None = None,
    report: Callable[[float], None] | None = None,
    on_gpu_failure: Callable[[str], None] | None = None,
) -> list[SpeechSegment]:
    """Turn audio into timed segments of speech.

    *report* is called with the last second finished, so the window can show
    progress while the work runs. *on_gpu_failure* is called with the reason if
    the graphics card gives out and the work moves to the processor.
    """
    audio = read_wav(wav_file)
    try:
        return _run(audio, model_name, use_gpu, language, report)
    except RuntimeError as error:
        if not use_gpu:
            raise SpeechError(
                f"Pembacaan suara gagal.\n\nKeterangan asli:\n{error}"
            ) from error
        # The card passed its check but gave out part-way through. The work still
        # has to finish, so it moves to the processor, and the caller is told so
        # the report does not claim a card did work it did not do.
        if on_gpu_failure:
            on_gpu_failure(str(error))
        return _run(audio, model_name, use_gpu=False, language=language, report=report)


def _run(
    audio,
    model_name: str,
    use_gpu: bool,
    language: str | None,
    report: Callable[[float], None] | None,
) -> list[SpeechSegment]:
    model = _load_model(model_name, use_gpu)
    segments, _ = model.transcribe(
        audio,
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
