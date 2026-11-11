@echo off
REM Builds the self-contained app into dist\Video to Text, then zips it.
REM For whoever makes a release. People who only want to use the app download
REM the finished zip and never run this.
REM
REM Needs Python 3.14 as "py -3.14". Downloads about 475 MB of models the first
REM time (into model\, which git ignores); later builds reuse them.

cd /d "%~dp0\.."
setlocal
set "PY=py -3.14"

%PY% -m pip install -r requirements-build.txt || goto failed
%PY% packaging\fetch_models.py small || goto failed
%PY% -m pytest -q || goto failed
%PY% -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\video-to-text.spec || goto failed
%PY% packaging\make_zip.py || goto failed

echo.
echo Done. The result is in the dist folder.
endlocal
exit /b 0

:failed
echo.
echo Build failed. See the messages above.
endlocal
exit /b 1
