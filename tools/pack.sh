#!/usr/bin/env bash
# Build one PyInstaller executable and assemble the release archive.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ensure_venv() {
  if [[ -f "$ROOT/.venv/Scripts/python.exe" ]]; then
    PYTHON_CMD=("$ROOT/.venv/Scripts/python.exe")
  elif [[ -f "$ROOT/.venv/bin/python" ]]; then
    PYTHON_CMD=("$ROOT/.venv/bin/python")
  else
    echo "Creating .venv..."
    case "$(uname -s 2>/dev/null || true)" in
      MINGW*|MSYS*|CYGWIN*|Windows_NT)
        if command -v py >/dev/null 2>&1; then
          py -3 -m venv "$ROOT/.venv"
        else
          python -m venv "$ROOT/.venv"
        fi
        PYTHON_CMD=("$ROOT/.venv/Scripts/python.exe")
        ;;
      *)
        if ! command -v python3 >/dev/null 2>&1; then
          echo "error: python3 is required to create .venv" >&2
          exit 1
        fi
        python3 -m venv "$ROOT/.venv"
        PYTHON_CMD=("$ROOT/.venv/bin/python")
        ;;
    esac
  fi
  echo "==> Python: ${PYTHON_CMD[*]} ($("${PYTHON_CMD[@]}" -V 2>/dev/null || true))"
}

apply_staticx_linux() {
  local pyi_out="$ROOT/dist/drawclock"
  if [[ ! -f "$pyi_out" ]]; then
    return 0
  fi
  if ! command -v patchelf >/dev/null 2>&1; then
    echo "error: Linux staticx requires patchelf, for example: sudo apt install patchelf" >&2
    exit 1
  fi
  "${PYTHON_CMD[@]}" -m pip install -q --upgrade --force-reinstall staticx
  local staticx="$ROOT/.venv/bin/staticx"
  if [[ ! -x "$staticx" ]]; then
    echo "error: .venv/bin/staticx was not found" >&2
    exit 1
  fi
  local tmp_out="$ROOT/dist/.drawclock-staticx.tmp"
  rm -f "$tmp_out"
  echo "==> staticx: $pyi_out -> drawclock"
  "$staticx" "$pyi_out" "$tmp_out"
  mv -f "$tmp_out" "$pyi_out"
  chmod +x "$pyi_out"
}

ensure_venv

"${PYTHON_CMD[@]}" -m pip install -q -U pip setuptools wheel
"${PYTHON_CMD[@]}" -m pip install -q --upgrade --force-reinstall -e ".[dev]" 2>/dev/null \
  || "${PYTHON_CMD[@]}" -m pip install -q --upgrade --force-reinstall -e .
"${PYTHON_CMD[@]}" -m pip install -q --upgrade --force-reinstall "pyinstaller>=6.0"

rm -rf "$ROOT/build" "$ROOT/dist"

echo "==> PyInstaller: drawclock.spec"
"${PYTHON_CMD[@]}" -m PyInstaller --clean --noconfirm "$ROOT/drawclock.spec"

if [[ -f "$ROOT/dist/drawclock.exe" ]]; then
  echo "done: $ROOT/dist/drawclock.exe"
elif [[ -f "$ROOT/dist/drawclock" ]]; then
  case "$(uname -s 2>/dev/null || true)" in
    Linux)
      if [[ "${PACK_LINUX_SKIP_STATICX:-}" == "1" ]]; then
        echo "done: $ROOT/dist/drawclock (PACK_LINUX_SKIP_STATICX=1)"
      else
        apply_staticx_linux
      fi
      ;;
    *) echo "done: $ROOT/dist/drawclock" ;;
  esac
else
  echo "error: dist/drawclock or dist/drawclock.exe was not created" >&2
  exit 1
fi

echo "==> Assembling release archive"
"${PYTHON_CMD[@]}" "$ROOT/tools/bundle_release.py"

echo "PyInstaller output: $ROOT/dist"
