@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "BUNDLE_DIR=%~dp0..\.."
set "OUTPUT=%~1"
if not defined OUTPUT set "OUTPUT=%CD%\drawclock-horizontal-spacing.svg"
set "SPACING=%~2"
if not defined SPACING set "SPACING=10"
"%BUNDLE_DIR%\drawclock.exe" -i "%SCRIPT_DIR%..\auto-layout\33-description-colors.json" -l "%BUNDLE_DIR%\libraries" -o "%OUTPUT%" --horizontal-spacing "%SPACING%"
if errorlevel 1 exit /b %errorlevel%
for %%A in ("%OUTPUT%") do if %%~zA LEQ 0 exit /b 1
echo Generated %OUTPUT%
