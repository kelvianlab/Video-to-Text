"""Entry point for the packaged app. PyInstaller needs a plain script to start
from; this one only hands over to the package."""

import sys

from video_to_text.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
