"""Turn the video's audio into text with Whisper.

Uses faster-whisper, which does not need PyTorch. The models travel inside the
app, so nothing is ever downloaded. An NVIDIA card is used when one genuinely
works; otherwise the work runs on the processor.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# The packaged app must never reach for the internet. Set before faster-whisper
# or huggingface_hub is imported, because both read these once at import time.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

_loaded_models: dict[tuple[str, str], object] = {}

_gpu_failure: str | None = None
"""Why the card failed, once it has. A card that failed on the first video
fails the same way on the next, so the slow check is not repeated."""


class _NoCard(Exception):
    """No NVIDIA card at all: the normal case, not worth a note to the user."""

LANGUAGE_NAMES = {"en": "English", "id": "Indonesian"}
"""The languages the app is built for. Anything else may still come out, but
automatic detection never picks it."""

# Whisper often hears Indonesian as Malay: the two share most of their words.
# Left alone, a whole Indonesian video can come back spelled as Malay. When
# choosing between the supported languages, Malay's score counts as Indonesian.
_COUNTS_AS = {"ms": "id"}


@dataclass(frozen=True)
class SpeechSegment:
    start: float
    end: float
    text: str


@dataclass
class SpeechResult:
    segments: list[SpeechSegment]
    used_gpu: bool
    language: str = ""
    language_was_detected: bool = False
    gpu_note: str | None = None
    """Why the card was not used after all, when it was asked for and failed."""


class SpeechError(Exception):
    """The speech model could not be used."""


def model_folder() -> Path:
    """Where the bundled models live.

    In the packaged app that is inside the app's own folder. When running from
    source it is the model/ folder at the top of the project, which the build
    script fills and git ignores.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "model"
    return Path(__file__).resolve().parents[2] / "model"


def model_path(name: str) -> Path:
    return model_folder() / f"faster-whisper-{name}"


def model_available(name: str) -> bool:
    return (model_path(name) / "model.bin").is_file()


def _load(name: str, device: str):
    from faster_whisper import WhisperModel

    key = (name, device)
    if key not in _loaded_models:
        location = model_path(name)
        if not (location / "model.bin").is_file():
            raise SpeechError(
                f"The speech model {name!r} is missing from the app.\n"
                f"Looked in: {location}\n\n"
                "The app folder may be incomplete. Extract it again from the original zip."
            )
        precision = "float16" if device == "cuda" else "int8"
        _loaded_models[key] = WhisperModel(str(location), device=device, compute_type=precision)
    return _loaded_models[key]


def _gpu_model(name: str):
    """Return a working model on the card, or raise with the reason it will not work.

    The check runs a real transcription of one second of silence. Merely building
    the model is not enough: CUDA's maths library is only loaded once there is
    something to compute, so a machine without it passes construction and then
    fails in the middle of the first real video.
    """
    global _gpu_failure
    import ctranslate2
    import numpy as np

    if ctranslate2.get_cuda_device_count() == 0:
        raise _NoCard()
    if _gpu_failure:
        raise RuntimeError(_gpu_failure)
    try:
        model = _load(name, "cuda")
        list(model.transcribe(np.zeros(16000, dtype=np.float32), beam_size=1)[0])
    except SpeechError:
        raise
    except Exception as error:
        _loaded_models.pop((name, "cuda"), None)
        _gpu_failure = f"{type(error).__name__}: {error}"
        raise
    return model


def choose_language(probabilities) -> str:
    """Pick English or Indonesian from Whisper's language scores.

    *probabilities* is the (code, probability) list Whisper returns. Only the
    supported languages compete, so a mixed Indonesian and English video can no
    longer be labelled as some third language.
    """
    scores = dict.fromkeys(LANGUAGE_NAMES, 0.0)
    for code, probability in probabilities:
        code = _COUNTS_AS.get(code, code)
        if code in scores:
            scores[code] += float(probability)
    return max(scores, key=scores.get)


def _pick_language(model, audio, language: str | None) -> tuple[str, bool]:
    if language:
        return language, False
    _, _, probabilities = model.detect_language(
        audio, vad_filter=True, language_detection_segments=3
    )
    return choose_language(probabilities), True


def transcribe(
    audio,
    model_name: str,
    use_gpu: bool = True,
    language: str | None = None,
    report: Callable[[float], None] | None = None,
    beam_size: int = 5,
) -> SpeechResult:
    """Turn 16 kHz mono float audio into timed segments of speech.

    *language* is "en" or "id" to name it outright, or None to choose between
    those two automatically. *report* is called with the last second finished,
    so the window can show progress while the work runs.
    """
    gpu_note = None
    if use_gpu:
        try:
            model = _gpu_model(model_name)
            chosen, detected = _pick_language(model, audio, language)
            return SpeechResult(
                _run(model, audio, chosen, report, beam_size), used_gpu=True,
                language=chosen, language_was_detected=detected,
            )
        except SpeechError:
            raise
        except _NoCard:
            pass  # most computers; the processor simply does the work
        except Exception as error:
            # A card that is there but will not work, or one that gave out
            # part-way. Either way the work still has to finish, and the user
            # is told why the card they asked for was not used.
            gpu_note = f"{type(error).__name__}: {error}"

    try:
        model = _load(model_name, "cpu")
        chosen, detected = _pick_language(model, audio, language)
        segments = _run(model, audio, chosen, report, beam_size)
    except SpeechError:
        raise
    except Exception as error:
        raise SpeechError(
            f"Reading the speech failed.\n\nOriginal error:\n{type(error).__name__}: {error}"
        ) from error
    return SpeechResult(
        segments, used_gpu=False, gpu_note=gpu_note,
        language=chosen, language_was_detected=detected,
    )


def _run(model, audio, language, report, beam_size) -> list[SpeechSegment]:
    segments, _ = model.transcribe(
        audio,
        language=language,
        vad_filter=True,   # skips silence and music, where Whisper invents text
        beam_size=beam_size,
    )
    found: list[SpeechSegment] = []
    for segment in segments:
        text = (segment.text or "").strip()
        if text:
            found.append(SpeechSegment(float(segment.start), float(segment.end), text))
        if report:
            report(float(segment.end))
    return found
