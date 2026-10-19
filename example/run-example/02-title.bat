@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "BUNDLE_DIR=%~dp0..\.."
set "OUTPUT=%~1"
if not defined OUTPUT set "OUTPUT=%CD%\drawclock-title.svg"
set "TITLE=%~2"
if not defined TITLE set "TITLE=DrawClock title example"
"%BUNDLE_DIR%\drawclock.exe" -i "%SCRIPT_DIR%..\auto-layout\01-linear.json" -l "%BUNDLE_DIR%\libraries" -o "%OUTPUT%" --title "%TITLE%"
if errorlevel 1 exit /b %errorlevel%
for %%A in ("%OUTPUT%") do if %%~zA LEQ 0 exit /b 1
echo Generated %OUTPUT%
