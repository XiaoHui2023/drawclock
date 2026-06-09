@echo off
rem 统一打包：仓库根 .venv，PyInstaller onefile（Windows 无 staticx）。一次构建 drawclock 与 drawclock-reload。
rem 每次 pip 对项目与打包工具 --force-reinstall，避免 .venv 残留旧依赖。
rem 用法（仓库根）：pack.bat
rem 产物：dist\drawclock.exe、dist\drawclock-reload.exe、dist\drawclock-<version>-windows.zip
rem 压缩包内含可执行文件、README.md、json.md、drawio-lib\；不含 example\、tools\ 等；清单见 tools\bundle_release.py
rem Spec：drawclock-cli.spec、drawclock-reload.spec（仓库根）
rem 单文件内附带 drawio-lib\；运行须 -l / --library 指定器件库。
rem 示例：
rem   dist\drawclock.exe -i example\demo.drawio -l drawio-lib\drawclock.xml -o example\out\clock-tree.json
rem   dist\drawclock-reload.exe -i example\fig1.drawio -l drawio-lib\drawclock.xml -o example\out\fig1-reloaded.drawio
rem 只打单个目标或 Linux staticx：见 tools\pack.sh 文件头注释。
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call "%~dp0update.bat"
)

call ".venv\Scripts\activate.bat"

set PY=%~dp0.venv\Scripts\python.exe
%PY% -m pip install -q -U pip setuptools wheel
%PY% -m pip install -q --upgrade --force-reinstall -e ".[dev]" 2>nul
if errorlevel 1 %PY% -m pip install -q --upgrade --force-reinstall -e .
%PY% -m pip install -q --upgrade --force-reinstall "pyinstaller>=6.0"

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo ==^> PyInstaller: drawclock-cli.spec
%PY% -m PyInstaller --clean --noconfirm drawclock-cli.spec
if errorlevel 1 exit /b 1

if exist build rmdir /s /q build

echo ==^> PyInstaller: drawclock-reload.spec
%PY% -m PyInstaller --clean --noconfirm drawclock-reload.spec
if errorlevel 1 exit /b 1

echo ==^> 组装发布压缩包
%PY% tools\bundle_release.py
if errorlevel 1 exit /b 1

echo 完成: dist\drawclock.exe dist\drawclock-reload.exe 及 dist\drawclock-*-windows.zip
