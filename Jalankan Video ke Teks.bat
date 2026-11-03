@echo off
REM Double-click launcher.
REM
REM It deliberately does NOT just call "python". On a machine with more than one
REM Python, "python" resolves to whichever one is first on PATH, and an active
REM conda environment puts itself there, so the app can open on a Python that has
REM none of its components installed.
REM
REM If no Python passes the component check, this still starts the app on the
REM best candidate rather than refusing. The app's own error message names the
REM interpreter and the exact pip command, which is far more use than a dead end
REM here. The reason each candidate was rejected is written to a log file.

cd /d "%~dp0"
setlocal enabledelayedexpansion

set "FOUND="
set "FIRST="
set "LOG=%TEMP%\video-to-text-pemeriksaan.txt"
> "%LOG%" echo Pemeriksaan Python untuk Video ke Teks

call :check "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
call :check "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :check "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :check "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

for /f "delims=" %%P in ('where python 2^>nul') do call :check "%%P"
for /f "delims=" %%P in ('where py 2^>nul') do call :check "%%P"

call :check "%USERPROFILE%\miniconda3\python.exe"
call :check "%USERPROFILE%\anaconda3\python.exe"

if defined FOUND goto run
if defined FIRST (
    set "FOUND=!FIRST!"
    echo.
    echo Peringatan: tidak ada Python yang lolos pemeriksaan komponen.
    echo Aplikasi tetap dibuka supaya pesan galatnya bisa dibaca.
    echo Rincian pemeriksaan: %LOG%
    echo.
    goto run
)
goto tanpa_python

:run
echo Memakai Python: %FOUND%
"%FOUND%" -m video_to_text
if errorlevel 1 goto gagal
endlocal
exit /b 0

REM Records every candidate. Sets FIRST to the first Python that runs at all, and
REM FOUND to the first one that can import everything the app needs.
:check
if defined FOUND exit /b 0
if not exist "%~1" exit /b 0
>> "%LOG%" echo.
>> "%LOG%" echo --- %~1
"%~1" -c "import sys; print(sys.version)" >> "%LOG%" 2>&1
if errorlevel 1 (
    >> "%LOG%" echo    tidak bisa dijalankan
    exit /b 0
)
if not defined FIRST set "FIRST=%~1"
"%~1" -c "import faster_whisper, rapidocr_onnxruntime, PIL, tkinter" >> "%LOG%" 2>&1
if errorlevel 1 (
    >> "%LOG%" echo    komponen belum lengkap di Python ini
    exit /b 0
)
>> "%LOG%" echo    semua komponen lengkap, dipakai
set "FOUND=%~1"
exit /b 0

:tanpa_python
echo.
echo ============================================================
echo  Python tidak ditemukan di komputer ini.
echo.
echo  Pasang Python 3.10 atau lebih baru dari python.org, lalu
echo  centang "Add Python to PATH" saat memasang.
echo.
echo  Rincian pemeriksaan: %LOG%
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
echo  Kalau yang disebut komponen belum terpasang, jalankan
echo  perintah pip yang tertulis di pesan itu.
echo.
echo  Kalau yang disebut ffmpeg, pasang dulu ffmpeg lalu coba lagi.
echo  Untuk memeriksa, ketik: ffmpeg -version
echo.
echo  Rincian pemeriksaan Python: %LOG%
echo ============================================================
echo.
pause
endlocal
exit /b 1
