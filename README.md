# Video to Text

**Turn a video into text: both the words that are spoken and the words shown on screen.**

Runs on your own computer. Your video is never uploaded and never modified.
It works on any video file you have, whether or not it ever had subtitles.

The app's window is in Indonesian, because it was built for Indonesian users.

---

## Download and use

> **Bahasa Indonesia:** unduh `Video-ke-Teks-…-Windows.zip` dari halaman
> [Releases](../../releases/latest), klik kanan lalu **Extract All**, buka folder
> `Video ke Teks`, lalu klik dua kali **`Video ke Teks.exe`**. Tidak perlu memasang
> Python, ffmpeg, atau apa pun. Tidak perlu internet.

1. Download **`Video-ke-Teks-<version>-Windows.zip`** from the
   [Releases](../../releases/latest) page. It is about 600 MB, because everything the
   app needs is inside it.
2. Right-click the zip and choose **Extract All**. Keep the extracted folder together;
   the `.exe` needs the `_internal` folder next to it.
3. Open the folder and double-click **`Video ke Teks.exe`**.

Nothing to install, nothing else to download, no internet needed. Python, the video
decoder, and both reading models all travel inside the folder.

The first time, Windows may say **"Windows protected your PC"**. That is because the
app is not code-signed, not because anything is wrong with it. Click **More info**,
then **Run anyway**. Windows asks only once.

### In the window

1. **Pick a video**, or a folder of videos (they are done one by one).
2. **Pick Cepat or Teliti** (fast or thorough, see below).
3. **Pick the spoken language**, or leave it on automatic.
4. Press **Mulai**.

The results land next to the video: a `.txt` to read, and a `.srt` that any video
player can load as subtitles. A file that is already there is **never overwritten**;
if the name is taken the result gets a number, for example `video (2).txt`.

## What the result looks like

```
[00:00:00] [SUARA] Gila kamu Mas, kamu yang gila!
[00:00:05] [LAYAR] Ultra
                    Claude Code included
                    No 5-hour limit
[00:00:10] [SUARA] Itu adalah contoh drama, teman-teman.
[00:00:21] [LAYAR] CHATGPT
                    CLAUDE
[00:00:23] [LAYAR] GEMINI
                    DEEPSEEK
```

`SUARA` is what was heard, `LAYAR` is what was shown. Each screen entry holds only the
lines that were new at that moment, so a title that stays on screen for the whole video
is written once, not once a second.

## Languages

The app is built for **English and Indonesian**. Each is written in the language it
was spoken in; nothing is translated.

On automatic, the app chooses between those two only. That matters more than it
sounds: left to itself, the speech model often hears Indonesian as Malay, the two
share most of their words, and a whole Indonesian video can come back spelled as
Malay. Choosing between English and Indonesian alone, with Malay counted as
Indonesian, removes that mistake. Other languages are not supported.

## Cepat or Teliti

Both use the same speech model. Teliti searches harder for the right wording and
looks at the screen twice as often.

| | Cepat (fast) | Teliti (thorough) |
|---|---|---|
| Speech | narrow search | wide search, better with names and rare words |
| Screen picture taken every | 2 seconds | 1 second |
| 39 s English video, screen changing constantly | about 50 s | about 70 s |
| 2 min Indonesian video | about 85 s | about 140 s |

Timings are from a laptop working on its processor alone. A video whose screen
mostly holds still is quicker, because an unchanged screen is skipped without being
read.

**An NVIDIA graphics card** can speed up the speech side, but only on a computer
that already has NVIDIA's CUDA 12 libraries installed; they are far too large to
ship inside the app. Without them the app simply uses the processor, and the
result is the same.

## How accurate is it

The result is a machine's best guess, not a guaranteed transcript.

**Speech.** On a 2-minute Indonesian video full of slang and English tech terms, the
sentences came through whole and readable. What goes wrong is names and brand words:
`Claude` heard as `cloud`, `DeepSeek` as `deepsik`. Read the result before quoting it.

**On-screen text.** English keeps its spaces (`SHORT FOR REVERSE`, `On the rise`).
What goes wrong: `I` and `l` get swapped (`Can Al find`), text cut off at the edge of
the frame is read in part, and very small, blurred, or briefly shown text can be
missed.

## Running from source

Only needed to work on the app itself. Python 3.14:

```
pip install -r requirements-build.txt
python packaging/fetch_models.py small
python -m pytest -q
python -m video_to_text
```

`fetch_models.py` puts the models in `model/` (about 475 MB, once). It is the only
step anywhere that touches the internet; the app never does.

Headless, from a terminal:

```
python -m video_to_text --run "D:\Video" --quality thorough --language id
```

Exit codes: `0` all done, `1` some failed, `2` the request could not be carried out.

### Building the download

```
packaging\build.bat
```

This installs the exact library versions in `requirements.txt`, fetches the models,
runs the tests, builds the app folder with PyInstaller, gathers every bundled
component's licence into it, and zips it. The result is
`dist\Video-ke-Teks-<version>-Windows.zip`.

The app is one folder rather than one `.exe` on purpose. A single `.exe` this size
unpacks several hundred MB to the temp folder on every launch, which takes tens of
seconds and is scanned by antivirus each time. The folder starts straight away.

## Layout

```
video_to_text/
  __main__.py        entry point, with or without the window
  window.py          the window; every string the user sees lives here
  core/
    settings.py      the numbers that separate Cepat from Teliti
    media.py         reading the video: details, sound, screen pictures (PyAV)
    speech.py        Whisper, the bundled model, choosing the language
    screen.py        OCR, and the filters that stop repeats
    timeline.py      merging heard and shown by time
    output.py        writing .txt and .srt without overwriting
    pipeline.py      one video from start to saved files
packaging/           build recipe, model fetcher, licence collector, zipper
tests/               runs the real video reader and the real window
```

## Deliberate limits

- The source video is only ever read, never written to or deleted.
- Nothing from the video is sent anywhere. The app works with no internet at all.
- A result file that already exists is never overwritten.

## License

The app's own code: [MIT](LICENSE).

The download also carries other people's work, each under its own licence, all
listed in `THIRD-PARTY-NOTICES.txt` inside the app folder with their licence texts
in `_internal/licenses/`. The main ones:
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) and
[CTranslate2](https://github.com/OpenNMT/CTranslate2) (MIT),
the Whisper model (MIT),
[RapidOCR](https://github.com/RapidAI/RapidOCR) and the PaddleOCR models (Apache 2.0),
[PyAV](https://github.com/PyAV-Org/PyAV) (BSD) with FFmpeg inside it (LGPL 3).
PyAV's FFmpeg is linked against the x264 and x265 encoders (GPL 2); this app only
reads video and never uses them, but their files are present, so the notices say
where their source can be had.
