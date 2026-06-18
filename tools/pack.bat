@echo off
rem Build one PyInstaller executable and assemble the release archive.
cd /d "%~dp0\.."

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

echo Done: dist\drawclock.exe and dist\drawclock-*-windows.zip
