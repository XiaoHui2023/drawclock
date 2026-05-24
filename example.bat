@echo off

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (

    call "%~dp0update.bat"

)

call ".venv\Scripts\activate.bat"

if not exist "example\out" mkdir "example\out"

if not exist "example\demo.drawio" (

    python scripts\build_example_demo.py

    if errorlevel 1 exit /b 1

)

echo === encode: demo.drawio -^> JSON ===

python src encode -i example\demo.drawio -o example\out --layout

if errorlevel 1 exit /b 1

echo.

echo === decode: JSON -^> restored.drawio ===

python src decode --config example\out\clock-tree.json --layout example\out\drawio-layout.json --library drawio-lib\drawclock.xml -o example\out\restored.drawio

if errorlevel 1 exit /b 1

echo.

echo === encode: round-trip check ===

python src encode -i example\out\restored.drawio -o example\out\roundtrip --layout

if errorlevel 1 exit /b 1

echo.

echo === example\out\clock-tree.json (excerpt) ===

powershell -NoProfile -Command "Get-Content example\out\clock-tree.json -TotalCount 40"

echo.

echo Done. See example\out\roundtrip\ and example\out\restored.drawio

