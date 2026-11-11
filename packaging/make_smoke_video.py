"""Make a short test video with known speech and known on-screen text.

Used to check a finished build end to end: the built app must hear the words
and read the caption back. The speech comes from a WAV made by Windows' own
voice (see the release workflow), so the test needs nothing downloaded.

    python packaging/make_smoke_video.py speech.wav smoke.mp4
"""

from __future__ import annotations

import sys
import wave

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CAPTION = "VIDEO TO TEXT READY"
FPS = 10


def caption_picture(width: int = 960, height: int = 540) -> np.ndarray:
    picture = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(picture)
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    box = draw.textbbox((0, 0), CAPTION, font=font)
    x = (width - (box[2] - box[0])) // 2
    y = (height - (box[3] - box[1])) // 2
    draw.text((x, y), CAPTION, fill="black", font=font)
    return np.asarray(picture)


def main(wav_path: str, video_path: str) -> int:
    with wave.open(wav_path, "rb") as sound:
        rate = sound.getframerate()
        channels = sound.getnchannels()
        width = sound.getsampwidth()
        samples = np.frombuffer(sound.readframes(sound.getnframes()), dtype=np.int16)
    if width != 2:
        print("expected 16-bit audio")
        return 1
    samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)  # to mono
    seconds = len(samples) / rate + 1.0

    frame = caption_picture()
    with av.open(video_path, mode="w") as out:
        picture = out.add_stream("libx264", rate=FPS)
        picture.width, picture.height, picture.pix_fmt = frame.shape[1], frame.shape[0], "yuv420p"
        voice = out.add_stream("aac", rate=rate)
        voice.layout = "mono"

        for _ in range(int(seconds * FPS)):
            for packet in picture.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")):
                out.mux(packet)
        for packet in picture.encode():
            out.mux(packet)

        chunk = 1024
        for start in range(0, len(samples), chunk):
            piece = samples[start:start + chunk].reshape(1, -1)
            audio = av.AudioFrame.from_ndarray(piece, format="s16", layout="mono")
            audio.sample_rate = rate
            audio.pts = start
            for packet in voice.encode(audio):
                out.mux(packet)
        for packet in voice.encode():
            out.mux(packet)

    print(f"{video_path}: {seconds:.1f} s, caption {CAPTION!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
