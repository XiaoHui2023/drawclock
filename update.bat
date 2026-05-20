@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)
call ".venv\Scripts\activate.bat"
pip install -e ".[dev]"
