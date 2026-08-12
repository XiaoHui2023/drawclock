from __future__ import annotations

import importlib.util
import subprocess
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
