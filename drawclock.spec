# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: drawclock onefile."""
from __future__ import annotations

from pathlib import Path

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

block_cipher = None


def _repo_root_from_spec() -> Path:
    spec = Path(SPECPATH).resolve()
    seeds = [spec.parent]
    try:
        seeds.append(Path.cwd().resolve())
    except OSError:
        pass
    for seed in seeds:
        for base in [seed, *seed.parents]:
            if (base / "pyproject.toml").is_file() and (
                base / "src" / "__main__.py"
            ).is_file():
                return base
    return spec.parent


repo_root = _repo_root_from_spec()
entry = repo_root / "src" / "__main__.py"
lib_dir = repo_root / "drawio-lib"

datas = []
if lib_dir.is_dir():
    datas.append((str(lib_dir), "drawio-lib"))

hiddenimports = [
    "migrate",
    "drawio_layout",
    "drawio_build",
    "layout_validate",
    "pipeline",
    "drawio_decode",
    "drawio_graph",
    "drawio_library",
    "drawio_ports",
    "topology",
    "config_export",
    "device_model",
    "device_attrs_validate",
    "device_attrs_convert",
    "validate_config",
]

a = Analysis(
    [str(entry)],
    pathex=[str(repo_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="drawclock",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
