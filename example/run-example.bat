@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "BUNDLE_DIR=%SCRIPT_DIR%.."
set "OUTPUT=%~1"
if not defined OUTPUT set "OUTPUT=%CD%\drawclock-example.svg"
set "TITLE=%~2"
if not defined TITLE set "TITLE=DrawClock release example"

"%BUNDLE_DIR%\drawclock.exe" ^
  -i "%SCRIPT_DIR%auto-layout\34-configurable-text-and-frequency.json" ^
  -l "%BUNDLE_DIR%\libraries" ^
  -o "%OUTPUT%" ^
  --title "%TITLE%" ^
  --crossing-style arc ^
  --description-align center ^
  --description-anchor top-left ^
  --horizontal-spacing 180 ^
  --name-align center ^
  --frequency-headers "Work frequency" "SCAN" "BIST" "Custom" ^
  --frequency-align center
if errorlevel 1 exit /b %errorlevel%
if not exist "%OUTPUT%" exit /b 1
echo Generated %OUTPUT%
