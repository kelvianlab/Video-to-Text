"""Tests that run the real video reader and the real window.

The first group writes a small genuine video with PyAV, so the reader is
exercised on the same decoders a user's video goes through. The second opens
the actual window: a broken window module once passed every other test.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

av = pytest.importorskip("av")
np = pytest.importorskip("numpy")

from video_to_text.core import media  # noqa: E402

SECONDS = 4
FPS = 10
AUDIO_RATE = 44100


def _write_video(path: Path, with_audio: bool = True, limited_range: bool = True) -> Path:
    """Write a SECONDS-long video whose picture changes once per second."""
    with av.open(str(path), mode="w") as out:
        picture = out.add_stream("libx264" if "libx264" in av.codecs_available else "mpeg4", rate=FPS)
        picture.width, picture.height, picture.pix_fmt = 320, 240, "yuv420p"
        sound = None
        if with_audio:
            sound = out.add_stream("aac", rate=AUDIO_RATE)
            sound.layout = "stereo"

        for index in range(SECONDS * FPS):
            shade = 40 + 50 * (index // FPS)
            pixels = np.full((240, 320, 3), shade, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            if limited_range:
                frame = frame.reformat(format="yuv420p")
            for packet in picture.encode(frame):
                out.mux(packet)
        for packet in picture.encode():
            out.mux(packet)

        if sound is not None:
            chunk = 1024
            total = SECONDS * AUDIO_RATE
            for start in range(0, total, chunk):
                count = min(chunk, total - start)
                t = (np.arange(start, start + count) / AUDIO_RATE).astype(np.float32)
                tone = (0.3 * np.sin(2 * math.pi * 440 * t)).astype(np.float32)
                frame = av.AudioFrame.from_ndarray(
                    np.stack([tone, tone]).reshape(1, -1), format="flt", layout="stereo"
                )
                frame.sample_rate = AUDIO_RATE
                frame.pts = start
                for packet in sound.encode(frame):
                    out.mux(packet)
            for packet in sound.encode():
                out.mux(packet)
    return path


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory) -> Path:
    return _write_video(tmp_path_factory.mktemp("video") / "sample.mp4")


def test_details_are_read(sample_video):
    details = media.read_details(sample_video)
    assert details.has_audio
    assert (details.width, details.height) == (320, 240)
    assert abs(details.duration_seconds - SECONDS) < 0.5


def test_a_silent_video_is_recognised(tmp_path):
    video = _write_video(tmp_path / "silent.mp4", with_audio=False)
    assert not media.read_details(video).has_audio
    with pytest.raises(media.MediaError):
        media.load_audio(video)


def test_audio_comes_out_as_16khz_mono_floats(sample_video):
    audio = media.load_audio(sample_video)
    assert audio.dtype == np.float32
    assert audio.ndim == 1
    assert abs(len(audio) / media.SPEECH_SAMPLE_RATE - SECONDS) < 0.3
    assert 0.1 < float(np.abs(audio).max()) <= 1.0  # the tone survived, unclipped


def test_frames_are_taken_mid_slice_with_their_real_times(sample_video, tmp_path):
    frames = media.extract_frames(sample_video, tmp_path / "f", interval_seconds=1.0)
    times = [seconds for seconds, _ in frames]
    assert len(frames) == SECONDS
    for expected, actual in zip([0.5, 1.5, 2.5, 3.5], times):
        assert abs(actual - expected) <= 1 / FPS + 1e-6
    assert all(path.is_file() and path.stat().st_size > 0 for _, path in frames)


def test_limited_range_video_is_converted_not_refused(sample_video, tmp_path):
    # The ffmpeg JPEG encoder used to refuse exactly this kind of video.
    frames = media.extract_frames(sample_video, tmp_path / "g", interval_seconds=2.0)
    assert frames


def test_wide_frames_are_scaled_down(tmp_path):
    from PIL import Image

    video = _write_video(tmp_path / "wide.mp4", with_audio=False)
    frames = media.extract_frames(video, tmp_path / "h", interval_seconds=2.0, width=160)
    with Image.open(frames[0][1]) as picture:
        assert picture.size == (160, 120)


def test_an_unreadable_file_gives_a_plain_error(tmp_path):
    broken = tmp_path / "damaged.mp4"
    broken.write_bytes(b"not a video")
    with pytest.raises(media.MediaError):
        media.read_details(broken)


# --- the window ---------------------------------------------------------------

tk = pytest.importorskip("tkinter")


@pytest.fixture
def window():
    from video_to_text.window import App

    try:
        app = App()
    except tk.TclError as error:  # no display, as on some CI machines
        pytest.skip(f"no display: {error}")
    app.withdraw()
    yield app
    app.destroy()


def test_the_window_opens_with_every_control(window):
    from video_to_text import __version__

    assert __version__ in window.title()
    for name in ("start_button", "stop_button", "language_box", "summary", "open_button"):
        assert hasattr(window, name)


def test_every_language_choice_maps_to_whisper(window):
    from video_to_text.window import LANGUAGES

    assert set(window.language_box.cget("values")) == set(LANGUAGES)
    assert LANGUAGES["Indonesian"] == "id"
    assert LANGUAGES["English"] == "en"
    assert None in LANGUAGES.values()


def test_choices_are_locked_while_working(window):
    window._lock(True)
    assert str(window.language_box.cget("state")) == "disabled"
    assert str(window.start_button.cget("state")) == "disabled"
    window._lock(False)
    assert str(window.language_box.cget("state")) == "readonly"


# --- choosing the language ----------------------------------------------------

from video_to_text.core.speech import choose_language  # noqa: E402


def test_english_wins_when_it_scores_highest():
    assert choose_language([("en", 0.8), ("id", 0.1), ("de", 0.05)]) == "en"


def test_malay_is_counted_as_indonesian():
    # Indonesian heard as Malay, the usual mistake, must still come out as id.
    assert choose_language([("ms", 0.5), ("en", 0.3), ("id", 0.15)]) == "id"


def test_a_third_language_can_never_be_chosen():
    assert choose_language([("ja", 0.9), ("en", 0.06), ("id", 0.04)]) in ("en", "id")


def _press_start_and_wait(window, seconds: float = 20.0) -> None:
    """Press Start and pump the window until the run is over.

    The window's event loop is deliberately not running here, only pumped. That
    is stricter than real use: a worker thread that touches a Tk variable fails
    at once ("main thread is not in main loop") instead of working by luck.
    """
    import time

    window.start_button.invoke()
    deadline = time.time() + seconds
    while window.busy or str(window.start_button.cget("state")) == "disabled":
        window.update()
        assert time.time() < deadline, "the run never finished"
        time.sleep(0.02)
    window.update()


def test_a_full_run_through_the_window(window, tmp_path, monkeypatch):
    from video_to_text import window as window_module
    from video_to_text.core.pipeline import VideoResult

    video = tmp_path / "sample.mp4"
    video.write_bytes(b"x")
    received = {}

    def fake_process(path, preset, use_gpu, language, report, should_stop):
        received.update(preset=preset.code, use_gpu=use_gpu, language=language)
        report("Reading speech...")
        txt, srt = tmp_path / "sample.txt", tmp_path / "sample.srt"
        txt.write_text("isi"), srt.write_text("isi")
        return VideoResult(video=path, txt_file=txt, srt_file=srt, speech_count=3, screen_count=2)

    monkeypatch.setattr(window_module, "process_video", fake_process)
    monkeypatch.setattr(window_module.speech, "model_available", lambda name: True)

    window.location.set(str(video))
    window.quality.set("thorough")
    window.language.set("Indonesian")
    window.use_gpu.set(False)
    _press_start_and_wait(window)

    assert received == {"preset": "thorough", "use_gpu": False, "language": "id"}
    assert window.status.get().startswith("Finished.")
    assert "DONE  sample.mp4" in window.summary.get("1.0", "end")
    assert str(window.open_button.cget("state")) == "normal"
    assert str(window.language_box.cget("state")) == "readonly"


def test_a_failed_video_is_reported_in_the_window(window, tmp_path, monkeypatch):
    from video_to_text import window as window_module
    from video_to_text.core.pipeline import VideoResult

    video = tmp_path / "damaged.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(
        window_module, "process_video",
        lambda path, *a, **k: VideoResult(video=path, error="MediaError: The video cannot be opened"),
    )
    monkeypatch.setattr(window_module.speech, "model_available", lambda name: True)

    window.location.set(str(video))
    _press_start_and_wait(window)

    assert window.status.get() == "No video could be done."
    assert "The video cannot be opened" in window.summary.get("1.0", "end")
    assert str(window.open_button.cget("state")) == "disabled"
