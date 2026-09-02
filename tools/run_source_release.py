"""Validate and run an extracted release entirely through its source tree."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


REQUIRED_SKILL_FILES = {
    "skills/clock-diagram-design/SKILL.md",
    "skills/clock-json-schema/SKILL.md",
    "skills/clock-layout-algorithms/SKILL.md",
    "skills/component-library-design/SKILL.md",
    "skills/drawclock-project-navigation/SKILL.md",
    "skills/svg-artifact-design/SKILL.md",
    "skills/svg-portability/SKILL.md",
    "skills/drawclock-project-navigation/scripts/validate_skills.py",
    "skills/clock-layout-algorithms/scripts/layout_statistics.py",
}


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_manifest(root: pathlib.Path) -> None:
    manifest_path = root / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("files")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("source manifest has no files")
    actual_paths = {
        path.relative_to(root).as_posix()
        for base in (root / "src", root / "skills", root / "licenses")
        for path in base.rglob("*")
        if path.is_file()
    }
    required_paths = {
        "runtime/runtime-manifest.json",
    }
    actual_paths.update(
        relative for relative in required_paths if (root / relative).is_file()
    )
    library_dir = root / "drawio-lib" / "drawclock"
    library_paths = {
        path.relative_to(root).as_posix()
        for path in library_dir.rglob("*.xml")
        if path.is_file()
    }
    if not library_paths:
        raise ValueError("release component library directory is empty")
    actual_paths.update(library_paths)
    actual_paths.update(
        path.relative_to(root).as_posix()
        for path in (
            root / "example/draw.json",
            *(root / "example/auto-layout").glob("*.json"),
        )
        if path.is_file()
    )
    missing_skills = sorted(
        relative for relative in REQUIRED_SKILL_FILES if not (root / relative).is_file()
    )
    if missing_skills:
        raise ValueError(f"release project skills are missing: {missing_skills}")
    legacy_paths = (root / "requirements-offline.txt", root / "vendor" / "wheels")
    if any(path.exists() for path in legacy_paths):
        raise ValueError("release still contains legacy Python runtime dependencies")
    if not (root / "licenses/NotoSansCJK-OFL-1.1.txt").is_file():
        raise ValueError("release is missing the embedded heading outline license")
    if set(expected) != actual_paths:
        missing = sorted(set(expected) - actual_paths)
        extra = sorted(actual_paths - set(expected))
        raise ValueError(f"source manifest paths differ: missing={missing} extra={extra}")
    for relative, expected_hash in expected.items():
        path = root / relative
        if not path.is_file() or _sha256(path) != expected_hash:
            raise ValueError(f"source manifest hash mismatch: {relative}")


def validate_packaged_skills(root: pathlib.Path) -> None:
    validator = root / "skills/drawclock-project-navigation/scripts/validate_skills.py"
    completed = subprocess.run(
        [sys.executable, str(validator), str(root / "skills")],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stdout + completed.stderr).strip()
        raise ValueError(f"release project skills failed validation: {detail}")


def _venv_python(venv: pathlib.Path) -> pathlib.Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_source_release.py <extracted-package-root>", file=sys.stderr)
        return 2
    root = pathlib.Path(sys.argv[1]).resolve()
    validate_source_manifest(root)
    validate_packaged_skills(root)
    with tempfile.TemporaryDirectory(prefix="drawclock-source-smoke-") as temp:
        venv = pathlib.Path(temp) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = _venv_python(venv)
        output = pathlib.Path(temp) / "source-smoke.svg"
        subprocess.run(
            [
                str(python),
                "-I",
                "-S",
                str(root / "src"),
                "-i",
                str(root / "example" / "draw.json"),
                "-l",
                str(root / "drawio-lib" / "drawclock"),
                "-o",
                str(output),
            ],
            cwd=temp,
            check=True,
        )
        svg = ET.fromstring(output.read_text(encoding="utf-8"))
        components = [
            element for element in svg.iter()
            if "component" in element.get("class", "").split()
        ]
        if not svg.tag.endswith("svg") or not components:
            raise SystemExit("offline source smoke did not produce a populated SVG")
        forbidden = {"foreignObject", "script", "iframe", "audio", "video", "canvas"}
        if any(element.tag.rsplit("}", 1)[-1] in forbidden for element in svg.iter()):
            raise SystemExit("offline source smoke produced browser-only SVG content")

        statistics_output = pathlib.Path(temp) / "layout-statistics.json"
        subprocess.run(
            [
                str(python),
                "-I",
                "-S",
                str(root / "skills/clock-layout-algorithms/scripts/layout_statistics.py"),
                "-i",
                str(root / "example/auto-layout/23-middle-column-low-use-sources.json"),
                "-l",
                str(root / "drawio-lib/drawclock"),
                "-o",
                str(statistics_output),
            ],
            cwd=temp,
            check=True,
        )
        statistics = json.loads(statistics_output.read_text(encoding="utf-8"))[
            "statistics"
        ]
        if len(statistics["nodes"]) != 29 or statistics["totals"]["edges"] != 28:
            raise SystemExit("packaged layout statistics do not cover every node and edge")
        required_edge_fields = {
            "manhattan_length_px", "bends", "crossing_points",
            "crossing_pair_incidents", "crossed_edge_count", "branch_siblings",
        }
        if any(
            not required_edge_fields.issubset(edge)
            for edge in statistics["edges"].values()
        ):
            raise SystemExit("packaged layout statistics are missing edge quality fields")
    print("offline source deployment passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
