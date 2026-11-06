@echo off
REM Builds the self-contained app into dist\Video ke Teks, then zips it.
REM For whoever makes a release. People who only want to use the app download
REM the finished zip and never run this.
REM
REM Needs Python 3.14 as "py -3.14". Downloads about 475 MB of models the first
REM time (into model\, which git ignores); later builds reuse them.

cd /d "%~dp0\.."
setlocal
set "PY=py -3.14"

%PY% -m pip install -r requirements-build.txt || goto gagal
%PY% packaging\fetch_models.py small || goto gagal
%PY% -m pytest -q || goto gagal
%PY% -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\video-to-text.spec || goto gagal
%PY% packaging\make_zip.py || goto gagal

echo.
echo Selesai. Hasilnya ada di folder dist.
endlocal
exit /b 0

:gagal
echo.
echo Pembuatan gagal. Lihat pesan di atas.
endlocal
exit /b 1
