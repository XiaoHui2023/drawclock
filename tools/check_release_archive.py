#!/usr/bin/env python3
"""Fail when the default release archive contains non-user files."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED = {
    "doc/README.md",
    "doc/draw.md",
    "example/draw.json",
    "example/README.md",
    "example/auto-layout/README.md",
    *{
        f"example/auto-layout/{path.name}"
        for path in (ROOT / "example" / "auto-layout").glob("*.json")
    },
}


def _platform_scripts(binary: str) -> set[str]:
    suffix = ".bat" if binary == "drawclock.exe" else ".sh"
    return {
        f"example/run-example/{path.name}"
        for path in (ROOT / "example" / "run-example").glob(f"*{suffix}")
    }


def _names(path: Path) -> tuple[list[str], dict[str, int]]:
    modes: dict[str, int] = {}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
    elif tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as archive:
            members = [item for item in archive.getmembers() if item.isfile()]
            names = [item.name for item in members]
            modes = {
                item.name.replace("\\", "/").lstrip("./"): item.mode
                for item in members
            }
    else:
        raise ValueError("archive must be ZIP or tar")
    names = [name.replace("\\", "/").lstrip("./") for name in names]
    top = {name.split("/", 1)[0] for name in names}
    if len(top) != 1:
        raise ValueError("archive must contain exactly one top directory")
    prefix = next(iter(top)) + "/"
    if any(not name.startswith(prefix) for name in names):
        raise ValueError("archive contains a file outside its top directory")
    stripped_modes = {
        name[len(prefix):]: mode
        for name, mode in modes.items()
        if name.startswith(prefix)
    }
    return sorted(name[len(prefix):] for name in names), stripped_modes


def validate(path: Path) -> list[str]:
    names, modes = _names(path)
    errors = []
    missing = sorted(REQUIRED - set(names))
    if missing:
        errors.append("missing required files: " + ", ".join(missing))
    binaries = [name for name in names if name in {"drawclock", "drawclock.exe"}]
    if len(binaries) != 1:
        errors.append("archive must contain exactly one drawclock executable")
    expected_scripts = set().union(
        *(_platform_scripts(binary) for binary in binaries)
    ) if binaries else set()
    if binaries and not expected_scripts:
        errors.append("source example script directory is empty")
    missing_scripts = sorted(expected_scripts - set(names))
    if missing_scripts:
        errors.append("missing platform example scripts: " + ", ".join(missing_scripts))
    unexpected_scripts = sorted(
        {
            name for name in names
            if name.startswith("example/run-example/")
            and Path(name).suffix in {".sh", ".bat"}
        } - expected_scripts
    )
    if unexpected_scripts:
        errors.append("unexpected platform example script: " + ", ".join(unexpected_scripts))
    non_executable = sorted(
        name for name in expected_scripts
        if name.endswith(".sh") and name in modes and not modes[name] & 0o111
    )
    if non_executable:
        errors.append("non-executable shell example scripts: " + ", ".join(non_executable))
    libraries = [name for name in names if name.startswith("libraries/")]
    if (
        not libraries
        or any(not name.endswith(".xml") or name.count("/") != 1 for name in libraries)
    ):
        errors.append("libraries must be flat and contain only XML files")
    if any(name in {"README.md", "draw.md"} for name in names):
        errors.append("documentation must be contained in doc/")
    if any(name.startswith("drawio-lib/") for name in names):
        errors.append("legacy drawio-lib directory is forbidden")
    license_files = [
        name for name in names
        if Path(name).name.lower().startswith(("license", "licence", "copying", "notice"))
    ]
    if license_files:
        errors.append("license files are forbidden: " + ", ".join(license_files))
    allowed = REQUIRED | set(binaries) | set(libraries) | expected_scripts
    unexpected = sorted(set(names) - allowed)
    if unexpected:
        errors.append("unexpected files: " + ", ".join(unexpected))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    errors = validate(args.archive.resolve())
    if errors:
        print("release archive surface: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("release archive surface: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
