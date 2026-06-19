"""Run the drawclock example workflow through a frozen executable."""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drawio_decode import extract_mxfile_xml, iter_diagram_models  # noqa: E402
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
FIG1 = ROOT / "example" / "fig1.drawio"
FIG2 = ROOT / "example" / "fig2.drawio"


def _binary_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    name = "drawclock.exe" if sys.platform == "win32" else "drawclock"
    return ROOT / "dist" / name


def _run(binary: Path, args: list[str], cwd: Path) -> None:
    cmd = [str(binary), *args]
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        print(f"command failed: {' '.join(cmd)}", file=sys.stderr)
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(completed.returncode)


def _assert_clock_tree(config: dict[str, object]) -> None:
    kinds = {item["kind"] for item in config.values() if isinstance(item, dict)}
    if "from" in kinds:
        print("from kind must not appear in exported JSON", file=sys.stderr)
        raise SystemExit(1)

    checks: list[tuple[str, object]] = [
        ("pll_main.source", "xtal"),
        ("gate0.source", "pll_main"),
        ("div0.source", "pll_main"),
        ("mux2.source", {"0": "pll_m2a", "1": "pll_m2b"}),
        ("pll_m2a.source", "osc_mux"),
        ("pll_m2b.source", "osc_mux"),
        ("clk_a.source", "inv0"),
        ("clk_b.source", "dto0"),
        ("clk_mux.source", "mux2"),
    ]
    for path, expected in checks:
        node_name, field = path.split(".", 1)
        node = config.get(node_name)
        if not isinstance(node, dict):
            print(f"missing node {node_name!r}", file=sys.stderr)
            raise SystemExit(1)
        actual = node.get(field)
        if actual != expected:
            print(f"unexpected {path}: {actual!r} (expected {expected!r})", file=sys.stderr)
            raise SystemExit(1)
        if field == "source" and isinstance(actual, dict):
            continue
        if "target" in node:
            print(f"unexpected target field on {node_name}", file=sys.stderr)
            raise SystemExit(1)

    pll_main = config.get("pll_main")
    if isinstance(pll_main, dict) and "targets" in pll_main:
        print("pll_main must not contain targets", file=sys.stderr)
        raise SystemExit(1)


def _assert_reloaded(path: Path) -> None:
    if not path.is_file():
        print(f"reload output missing: {path}", file=sys.stderr)
        raise SystemExit(1)
    text = path.read_text(encoding="utf-8")
    if "<mxGraphModel" in text:
        print(f"reload output must stay compressed: {path}", file=sys.stderr)
        raise SystemExit(1)
    model_xml = ET.tostring(
        iter_diagram_models(extract_mxfile_xml(str(path)))[0],
        encoding="unicode",
    )
    for needle in ('label="', "exitPerimeter=0", "drawclockType="):
        if needle not in model_xml:
            print(f"reload output missing {needle!r}: {path}", file=sys.stderr)
            raise SystemExit(1)
    if "&lt;svg" not in model_xml and "<svg" not in model_xml:
        print(f"reload output missing embedded svg labels: {path}", file=sys.stderr)
        raise SystemExit(1)


def main() -> int:
    binary = _binary_path()
    if not binary.is_file():
        print(f"frozen executable not found: {binary}", file=sys.stderr)
        return 1
    for required in (LIBRARY, FIG1, FIG2):
        if not required.is_file():
            print(f"example input missing: {required}", file=sys.stderr)
            return 1

    out_dir = ROOT / "example" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    clock_tree = out_dir / "clock-tree-frozen-smoke.json"
    fig1_reloaded = out_dir / "fig1-frozen-smoke.drawio"
    fig2_reloaded = out_dir / "fig2-frozen-smoke.drawio"

    _run(
        binary,
        [
            "run",
            "-i",
            str(FIG1),
            str(FIG2),
            "-o",
            str(clock_tree),
            "-l",
            str(LIBRARY),
        ],
        ROOT,
    )
    config = json.loads(clock_tree.read_text(encoding="utf-8"))
    _assert_clock_tree(config)

    _run(
        binary,
        ["reload", "-i", str(FIG1), "-l", str(LIBRARY), "-o", str(fig1_reloaded)],
        ROOT,
    )
    _run(
        binary,
        ["reload", "-i", str(FIG2), "-l", str(LIBRARY), "-o", str(fig2_reloaded)],
        ROOT,
    )
    _assert_reloaded(fig1_reloaded)
    _assert_reloaded(fig2_reloaded)

    print("frozen example passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
