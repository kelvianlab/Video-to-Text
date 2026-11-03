@echo off
REM Double-click launcher.
REM
REM It deliberately does NOT just call "python". On a machine with more than one
REM Python, "python" resolves to whichever one happens to be first on PATH, and
REM an active conda environment puts itself first. That is how this app once
REM opened on a Python that had none of its components installed and failed with
REM a bare ModuleNotFoundError. So: find a Python that actually has what this
REM app needs, and use that one.

cd /d "%~dp0"
setlocal

set "FOUND="

REM Candidates in order: the usual per-user install, then py launcher versions,
REM then whatever PATH offers, then conda as a last resort.
call :try "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if defined FOUND goto run
call :try "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if defined FOUND goto run
call :try "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined FOUND goto run

for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined FOUND call :try "%%P"
)
if defined FOUND goto run

call :try "%USERPROFILE%\miniconda3\python.exe"
if defined FOUND goto run
call :try "%USERPROFILE%\anaconda3\python.exe"
if defined FOUND goto run

goto tidak_lengkap

:run
echo Memakai Python: %FOUND%
"%FOUND%" -m video_to_text
if errorlevel 1 goto gagal
endlocal
exit /b 0

REM Sets FOUND only when this Python exists AND can import what the app needs.
:try
if not exist "%~1" exit /b 0
"%~1" -c "import faster_whisper, rapidocr_onnxruntime, PIL, tkinter" >nul 2>&1
if errorlevel 1 exit /b 0
set "FOUND=%~1"
exit /b 0

:tidak_lengkap
echo.
echo ============================================================
echo  Komponen aplikasi belum terpasang.
echo.
echo  Di komputer ini ada Python, tetapi belum ada satu pun yang
echo  punya semua komponen yang dibutuhkan aplikasi ini.
echo.
echo  Jalankan sekali perintah ini, lalu coba lagi:
echo.
echo    pip install faster-whisper rapidocr-onnxruntime pillow
echo.
echo  Kalau di komputer ini ada lebih dari satu Python, pasang di
echo  Python yang ingin dipakai, contohnya:
echo.
echo    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -m pip install faster-whisper rapidocr-onnxruntime pillow
echo ============================================================
echo.
pause
endlocal
exit /b 2

:gagal
echo.
echo ============================================================
echo  Aplikasi berhenti dengan galat. Pesan aslinya ada di atas.
echo.
echo  Kalau yang disebut ffmpeg, pasang dulu ffmpeg lalu coba lagi.
echo  Untuk memeriksa, ketik: ffmpeg -version
echo ============================================================
echo.
pause
endlocal
exit /b 1
