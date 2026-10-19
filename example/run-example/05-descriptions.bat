@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "BUNDLE_DIR=%~dp0..\.."
set "OUTPUT=%~1"
if not defined OUTPUT set "OUTPUT=%CD%\drawclock-descriptions.svg"
"%BUNDLE_DIR%\drawclock.exe" -i "%SCRIPT_DIR%..\auto-layout\34-configurable-text-and-table.json" -l "%BUNDLE_DIR%\libraries" -o "%OUTPUT%" --description-align center --description-anchor top-left --description-offset-x 5 --description-offset-y -7
if errorlevel 1 exit /b %errorlevel%
for %%A in ("%OUTPUT%") do if %%~zA LEQ 0 exit /b 1
echo Generated %OUTPUT%
