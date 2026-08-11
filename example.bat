@echo off

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call "%~dp0update.bat"
)

call ".venv\Scripts\activate.bat"

if not exist "example\out" mkdir "example\out"

echo === 1/7 install ELK layout dependency ===
if not exist "node_modules\elkjs" call npm install --ignore-scripts
if errorlevel 1 exit /b 1

echo.
echo === 2/7 build drawio library ===
python scripts\build_drawio_lib.py
if errorlevel 1 exit /b 1

echo.
echo === 3/7 build example fig1 + fig2 ===
python scripts\build_example_demo.py
if errorlevel 1 exit /b 1

echo.
echo === 4/7 drawio-to-json: fig1 + fig2 -^> clock-tree.json ===
python src drawio-to-json -i example\fig1.drawio example\fig2.drawio -o example\out\clock-tree.json -l drawio-lib\drawclock.xml
if errorlevel 1 exit /b 1

echo.
echo === 5/7 reload fig1 + fig2 ===
python src reload -i example\fig1.drawio -l drawio-lib\drawclock.xml -o example\out\fig1-reloaded.drawio
if errorlevel 1 exit /b 1
python src reload -i example\fig2.drawio -l drawio-lib\drawclock.xml -o example\out\fig2-reloaded.drawio
if errorlevel 1 exit /b 1

echo.
echo === 6/7 build JSON auto-layout examples ===
python scripts\build_auto_layout_examples.py
if errorlevel 1 exit /b 1

echo.
echo === 7/7 pytest: reload + example ===
pytest tests\test_reload.py tests\test_parse_drawio.py::test_example_fig1_embeds_library_labels tests\test_parse_drawio.py::test_example_two_figs_cross_from_no_from_in_json -q --tb=short
if errorlevel 1 exit /b 1

echo.
echo === example\out\clock-tree.json (excerpt) ===
powershell -NoProfile -Command "Get-Content example\out\clock-tree.json -TotalCount 50"

echo.
echo Done. Outputs: example\out\clock-tree.json, fig1-reloaded.drawio, fig2-reloaded.drawio
