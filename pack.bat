@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call "%~dp0update.bat"
)

call ".venv\Scripts\activate.bat"

set PY=%~dp0.venv\Scripts\python.exe
%PY% -m pip install -q -U pip setuptools wheel
%PY% -m pip install -q -e ".[dev]" 2>nul
if errorlevel 1 %PY% -m pip install -q -e .
%PY% -m pip install -q "pyinstaller>=6.0"

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo ==^> PyInstaller: drawclock-cli.spec
%PY% -m PyInstaller --clean --noconfirm drawclock-cli.spec
if errorlevel 1 exit /b 1

echo Done: dist\drawclock.exe
echo See PACKAGING.md for usage.
