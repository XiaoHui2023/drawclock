#!/usr/bin/env python3
"""Exercise the Linux archive source without its frozen executable."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_packaged_source.py <extracted-package-root>", file=sys.stderr)
        return 2

    package_root = pathlib.Path(sys.argv[1]).resolve()
    required = (
        package_root / "src" / "__main__.py",
        package_root / "libraries",
        package_root / "example" / "draw.json",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("missing packaged source input: " + ", ".join(missing), file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="drawclock-source-only-") as temp:
        deployment = pathlib.Path(temp) / "deployment"
        shutil.copytree(package_root / "src", deployment / "src")
        shutil.copytree(package_root / "libraries", deployment / "libraries")
        deployment.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package_root / "example" / "draw.json", deployment / "input.json")
        output = deployment / "output.svg"
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(deployment / "src"),
                "-i",
                str(deployment / "input.json"),
                "-l",
                str(deployment / "libraries"),
                "-o",
                str(output),
            ],
            cwd=deployment,
            check=False,
        )
        if completed.returncode:
            return completed.returncode
        if not output.is_file() or output.stat().st_size == 0:
            print("packaged source did not generate SVG", file=sys.stderr)
            return 1
        root = ET.fromstring(output.read_text(encoding="utf-8"))
        if not root.tag.endswith("svg"):
            print("packaged source output is not SVG", file=sys.stderr)
            return 1
        if not any("component" in item.get("class", "").split() for item in root.iter()):
            print("packaged source output has no components", file=sys.stderr)
            return 1

    print("packaged source-only deployment passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
