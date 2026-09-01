from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from verify_librsvg_output import verify_librsvg_output


def _render_and_verify(
    command: list[str], root: Path, work: Path, name: str, example: Path,
) -> None:
    source = work / f"{name}.svg"
    flattened = work / f"{name}-librsvg.svg"
    subprocess.run(
        [
            *command,
            "-i", str(example),
            "-l", str(root / "drawio-lib/drawclock"),
            "-o", str(source),
        ],
        check=True,
        env={**os.environ, "PATH": os.environ.get("PATH", "")},
        timeout=120,
    )
    subprocess.run(
        ["rsvg-convert", "-f", "svg", str(source), "-o", str(flattened)],
        check=True,
        timeout=60,
    )
    result = verify_librsvg_output(source, flattened)
    print(name, " ".join(f"{key}={value}" for key, value in result.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    args = parser.parse_args()
    root = args.package_root.resolve()
    binary = root / "drawclock"
    if not binary.is_file():
        raise FileNotFoundError(f"release binary is missing: {binary}")
    with tempfile.TemporaryDirectory(prefix="drawclock-rsvg-") as directory:
        work = Path(directory)
        examples = (
            ("draw", root / "example/draw.json"),
            ("frequency", root / "example/auto-layout/22-terminal-frequency-table.json"),
        )
        for suffix, example in examples:
            _render_and_verify([str(binary)], root, work, f"frozen-{suffix}", example)
            _render_and_verify(
                [sys.executable, "-I", "-S", str(root / "src")],
                root, work, f"source-{suffix}", example,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
