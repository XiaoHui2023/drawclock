"""Download the target-platform wheelhouse used by offline source installs."""

from __future__ import annotations

import json
import pathlib
import platform
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
WHEELHOUSE = ROOT / ".source-wheelhouse"
REQUIREMENTS = ROOT / "requirements-offline.txt"
PYTHON_MINORS = ("310", "311", "312", "313", "314")


def _target_platform() -> str:
    system = platform.system()
    if system == "Windows":
        return "win_amd64"
    if system == "Linux":
        return "manylinux2014_x86_64"
    raise SystemExit(f"unsupported source bundle platform: {system}")


def main() -> int:
    if WHEELHOUSE.exists():
        shutil.rmtree(WHEELHOUSE)
    WHEELHOUSE.mkdir(parents=True)
    target = _target_platform()
    for minor in PYTHON_MINORS:
        command = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--disable-pip-version-check",
            "--only-binary=:all:",
            "--no-deps",
            "--dest",
            str(WHEELHOUSE),
            "--platform",
            target,
            "--implementation",
            "cp",
            "--python-version",
            minor,
            "--abi",
            f"cp{minor}",
            "-r",
            str(REQUIREMENTS),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
    wheels = sorted(path.name for path in WHEELHOUSE.glob("*.whl"))
    if not wheels:
        raise SystemExit("offline source wheelhouse is empty")
    manifest = {
        "schema": 1,
        "platform": target,
        "cpython": list(PYTHON_MINORS),
        "wheels": wheels,
    }
    (WHEELHOUSE / "wheelhouse-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"prepared offline source wheelhouse: platform={target} "
        f"wheels={len(wheels)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
