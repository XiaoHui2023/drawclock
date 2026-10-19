@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "BUNDLE_DIR=%~dp0..\.."
set "OUTPUT=%~1"
if not defined OUTPUT set "OUTPUT=%CD%\drawclock-crossing-style.svg"
set "STYLE=%~2"
if not defined STYLE set "STYLE=arc"
"%BUNDLE_DIR%\drawclock.exe" -i "%SCRIPT_DIR%..\auto-layout\05-dense-cross-root.json" -l "%BUNDLE_DIR%\libraries" -o "%OUTPUT%" --crossing-style "%STYLE%"
if errorlevel 1 exit /b %errorlevel%
for %%A in ("%OUTPUT%") do if %%~zA LEQ 0 exit /b 1
echo Generated %OUTPUT%
