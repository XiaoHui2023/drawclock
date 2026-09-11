@echo off
rem Build the dependency-free executable archive.
cd /d "%~dp0\.."

rem Fail before environment creation, downloads, builds, or dist mutation.
where py >nul 2>nul
if errorlevel 1 (
    python tools\check_feedback_reproduction_gate.py --phase release
) else (
    py -3 tools\check_feedback_reproduction_gate.py --phase release
)
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
    call "update.bat"
)

call ".venv\Scripts\activate.bat"

set PY=%CD%\.venv\Scripts\python.exe
%PY% -m pip install -q -U pip setuptools wheel
%PY% -m pip install -q --upgrade --force-reinstall -e ".[dev]" 2>nul
if errorlevel 1 %PY% -m pip install -q --upgrade --force-reinstall -e .
%PY% -m pip install -q --upgrade --force-reinstall "pyinstaller>=6.0"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo ==^> PyInstaller: drawclock.spec
%PY% -m PyInstaller --clean --noconfirm drawclock.spec
if errorlevel 1 exit /b 1

echo ==^> Assembling release archive
%PY% tools\bundle_release.py
if errorlevel 1 exit /b 1
for %%F in (dist\drawclock-*-windows.zip) do set ARCHIVE=%%F
if not defined ARCHIVE exit /b 1
%PY% tools\check_release_archive.py "%ARCHIVE%"
if errorlevel 1 exit /b 1

echo Done: dist\drawclock.exe and dist\drawclock-*-windows.zip
