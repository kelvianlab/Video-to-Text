# Video to Text

**Turn a video into text: both the words that are spoken and the words shown on screen.**

Runs on your own machine. Your video is never uploaded and never modified.

The app's own window is in Indonesian, because it was built for Indonesian users.

---

## Why this exists

Screen recordings carry a lot that is never said out loud: the command typed into
a terminal, an error message, a number ticking upward, a subtitle burned into the
picture. An ordinary transcriber only listens to the audio, so all of that is lost.

This reads both, and lays them out in the order they happened:

```
[00:00:12] [SUARA] jadi sekarang kita jalankan perintahnya
[00:00:14] [LAYAR] PS C:\> python -m video_to_text --run "D:\Video"
[00:00:21] [LAYAR] Discovered 8.046 items (5,23GB)
```

`SUARA` means heard, `LAYAR` means shown on screen.

## Using it

```
python -m video_to_text
```

1. Pick one video, or a folder holding many.
2. Pick **Cepat** (fast) or **Teliti** (thorough).
3. Press **Mulai** (start).

The results land next to the video: a `.txt` to read, and a `.srt` that a video
player can load as subtitles.

A file that is already there is **never overwritten**. If the name is taken, the
result gets a number, for example `video (2).txt`.

### Headless, from a terminal

```
python -m video_to_text --run "D:\Video" --quality thorough
```

Exit codes: `0` all done, `1` some failed, `2` the request could not be carried out.

## Fast or Thorough

| | Fast (Cepat) | Thorough (Teliti) |
|---|---|---|
| Speech model | `small`, 484 MB download | `medium`, 1.5 GB download |
| Screen frame taken every | 2 seconds | 1 second |
| Speed | roughly 3 to 4 times quicker | slower |

A model is downloaded once. After that the tool runs with no internet at all.
The download size is always stated before anything is fetched.

## What it needs

| Needs | Note |
|---|---|
| Python 3.10 or newer | |
| ffmpeg | must be callable from the terminal |
| `faster-whisper` | reads the speech; does not need PyTorch |
| `rapidocr-onnxruntime` | reads the on-screen text |
| An NVIDIA card | optional, but makes the speech side far quicker |

```
pip install faster-whisper rapidocr-onnxruntime pillow
```

## How accurate is it

The result is a machine's best guess, not a guaranteed transcript. These numbers
come from real recordings, so you know what to expect.

**On-screen text.** On a screenshot of an Indonesian-language app, all 11 lines
were read correctly, at confidence 0.74 to 0.94. A long sentence such as
*"Aman: folder sumber hanya dibaca, tidak ada yang diubah atau dihapus di sana"*
came through whole and correct.

**What it gets wrong.** Letters that resemble digits get swapped, `l` read as `1`.
Text cut off at the edge of the screen is read in part. Spaces between English
words sometimes vanish, giving `batman thedark knight`. Text that is very small,
blurred, or on screen only briefly can be missed completely.

**Speed.** A 40-second recording whose screen changed constantly took 39 seconds
on Fast without a graphics card. A video whose screen mostly holds still is far
quicker, because unchanged screens are skipped without being read.

## Not writing the same screen twice

There are two filters, and which one does what matters.

**The frame filter** compares a screen with the one before it. If nothing changed,
the frame is skipped without being read at all. This exists purely to save time.

The screen is split into tiles and the **most-changed** tile is taken, rather than
the average across the whole screen. That is necessary because the changes worth
catching often occupy a small patch. Measured on a real recording, a counter going
from `1.912 items` to `8.046 items` reads as **0.0001** when averaged over the whole
screen, but **0.003 to 0.014** when measured by tile.

**The text filter** compares what was read against the previous reading. This is
what decides whether a screen is recorded. Two screens count as the same only when
every number matches exactly **and** the rest of the text is near enough identical.

The rule about numbers is deliberate: on a progress dialog or a terminal, the number
is the part that changes and the part worth keeping. The cost is that a `l` misread
as `1` produces one duplicate line. That trade was taken knowingly: a spare line
costs less than a changed number vanishing without trace.

## Layout

```
video_to_text/
  __main__.py        entry point, with or without the window
  window.py          the window; every string the user sees lives here
  core/
    settings.py      the numbers that separate Fast from Thorough
    media.py         ffmpeg: video details, audio, screen frames
    speech.py        Whisper
    screen.py        OCR and the two repetition filters
    timeline.py      merging heard and shown by time
    output.py        writing .txt and .srt without overwriting
    pipeline.py      one video from start to saved files
tests/
  test_core.py       the parts that decide what ends up in the result
```

`core` needs no window, so it can be tested and driven from a terminal.
`timeline`, `output`, and the filters in `screen` need no model at all, which is
why the whole test suite finishes in well under a second.

## Running the tests

```
pip install pytest
python -m pytest tests -q
```

## Deliberate limits

- The source video is only ever read, never written to or deleted.
- Nothing from the video is sent anywhere. The only time an internet connection
  is needed is the first download of a model.
- A result file that already exists is never overwritten.
- No part of the video or its text is stored anywhere except the result files.

## License

[MIT](LICENSE)

This tool calls on other people's work, each under its own licence:
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT),
[RapidOCR](https://github.com/RapidAI/RapidOCR) (Apache 2.0), and
[ffmpeg](https://ffmpeg.org/) (LGPL or GPL, depending on the build installed).
The Whisper models come from OpenAI under the MIT licence. All three are called as
separate tools; none of their code is copied into this one.
