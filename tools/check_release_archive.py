#!/usr/bin/env python3
"""Fail when the default release archive contains non-user files."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path


REQUIRED = {
    "doc/README.md",
    "doc/draw.md",
    "doc/licenses/NotoSansCJK-OFL-1.1.txt",
    "example/draw.json",
    "example/auto-layout/33-description-colors.json",
}


def _names(path: Path) -> list[str]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
    elif tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as archive:
            names = [item.name for item in archive.getmembers() if item.isfile()]
    else:
        raise ValueError("archive must be ZIP or tar")
    names = [name.replace("\\", "/").lstrip("./") for name in names]
    top = {name.split("/", 1)[0] for name in names}
    if len(top) != 1:
        raise ValueError("archive must contain exactly one top directory")
    prefix = next(iter(top)) + "/"
    if any(not name.startswith(prefix) for name in names):
        raise ValueError("archive contains a file outside its top directory")
    return sorted(name[len(prefix):] for name in names)


def validate(path: Path) -> list[str]:
    names = _names(path)
    errors = []
    missing = sorted(REQUIRED - set(names))
    if missing:
        errors.append("missing required files: " + ", ".join(missing))
    binaries = [name for name in names if name in {"drawclock", "drawclock.exe"}]
    if len(binaries) != 1:
        errors.append("archive must contain exactly one drawclock executable")
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
    allowed = REQUIRED | set(binaries) | set(libraries)
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
