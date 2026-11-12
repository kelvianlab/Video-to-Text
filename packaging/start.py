"""Entry point for the packaged app. PyInstaller needs a plain script to start
from; this one hands over to the package, after one check.

Windows refuses to load a DLL whose full path is longer than 260 characters.
The deepest DLL in the folder adds about 80 characters to wherever the folder
was put, so a folder extracted deep inside long-named folders fails with
"The filename or extension is too long". When that would happen, the app
restarts itself through the folder's short (8.3) name, which Windows gives
every long name on the system drive. If no short name exists, it says plainly
what to do instead of failing halfway through a video.
"""

import os
import subprocess
import sys

LIMIT = 259          # MAX_PATH minus the terminating zero
DEEPEST = 100        # the longest path inside the folder is 90; keep a margin
RELAUNCHED = "VIDEO_TO_TEXT_SHORT_PATH"


def _too_long(folder: str) -> bool:
    return len(folder) + DEEPEST > LIMIT


def _short_name(path: str) -> str:
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    size = ctypes.windll.kernel32.GetShortPathNameW(path, buffer, len(buffer))
    return buffer.value if 0 < size < len(buffer) else path


def _tell(message: str) -> None:
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, message, "Video to Text", 0x10)


def _check_folder() -> int | None:
    """Return an exit code when the app must not continue here, else None."""
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return None
    folder = os.path.dirname(sys.executable)
    if not _too_long(folder):
        return None
    short_exe = _short_name(sys.executable)
    if not os.environ.get(RELAUNCHED) and not _too_long(os.path.dirname(short_exe)):
        env = dict(os.environ, **{RELAUNCHED: "1"})
        return subprocess.call([short_exe, *sys.argv[1:]], env=env)
    _tell(
        "This folder is too deep for Windows to open the app from it:\n\n"
        f"{folder}\n\n"
        "Move the 'Video to Text' folder somewhere with a shorter path, "
        "for example C:\\Video to Text or your Desktop, and open it again."
    )
    return 2


if __name__ == "__main__":
    code = _check_folder()
    if code is not None:
        sys.exit(code)

    from video_to_text.__main__ import main

    sys.exit(main())
