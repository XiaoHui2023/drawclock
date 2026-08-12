from __future__ import annotations

import importlib.util
import struct
import subprocess
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _runtime_module():
    spec = importlib.util.spec_from_file_location(
        "fetch_release_runtime", ROOT / "tools" / "fetch_release_runtime.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frozen_smoke_module():
    spec = importlib.util.spec_from_file_location(
        "run_frozen_example", ROOT / "tools" / "run_frozen_example.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_rgb_png(path: Path, *, width: int, height: int, value: int) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    scanlines = b"".join(
        b"\0" + bytes([value, value, value]) * width for _ in range(height)
    )
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanlines))
        + chunk(b"IEND", b"")
    )


def test_build_environment_version_probe_records_incompatible_runtime(
    tmp_path: Path, monkeypatch,
) -> None:
    module = _runtime_module()
    executable = tmp_path / "chrome-headless-shell"
    executable.touch()
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=127, stdout="", stderr="GLIBC_2.25 not found\n"
        ),
    )

    assert module._probe_version(executable) == {
        "returncode": 127,
        "output": "GLIBC_2.25 not found",
    }


def test_png_quality_gate_rejects_valid_but_blank_raster(tmp_path: Path) -> None:
    module = _frozen_smoke_module()
    image = tmp_path / "blank.png"
    _write_rgb_png(image, width=20, height=10, value=255)

    try:
        module._assert_png_image(image, expected_size=(20, 10))
    except AssertionError as exc:
        assert "blank or nearly blank" in str(exc)
    else:
        raise AssertionError("blank PNG escaped the frozen quality gate")


def test_png_quality_gate_accepts_nonblank_raster(tmp_path: Path) -> None:
    module = _frozen_smoke_module()
    image = tmp_path / "dark.png"
    _write_rgb_png(image, width=20, height=10, value=0)

    module._assert_png_image(image, expected_size=(20, 10))


def test_png_quality_gate_rejects_corrupted_chunk(tmp_path: Path) -> None:
    module = _frozen_smoke_module()
    image = tmp_path / "corrupted.png"
    _write_rgb_png(image, width=20, height=10, value=0)
    data = bytearray(image.read_bytes())
    data[-5] ^= 1
    image.write_bytes(data)

    try:
        module._assert_png_image(image, expected_size=(20, 10))
    except AssertionError as exc:
        assert "CRC mismatch" in str(exc)
    else:
        raise AssertionError("corrupted PNG escaped the frozen quality gate")
