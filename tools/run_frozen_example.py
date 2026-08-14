"""Exercise the release executable through its only public operation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
DRAW_EXAMPLE = ROOT / "example" / "draw.json"
LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
DENSE = ROOT / "example" / "auto-layout" / "05-dense-cross-root.json"
STRESS = ROOT / "example" / "auto-layout" / "08-stress-512-clocks.json"
ASYMMETRIC = ROOT / "example" / "auto-layout" / "20-asymmetric-merge-route-bulge.json"
COLUMN_PREFERENCE = ROOT / "example" / "auto-layout" / "21-layout-column-preference.json"
SVG_NS = "http://www.w3.org/2000/svg"


def _binary_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    return ROOT / "dist" / ("drawclock.exe" if sys.platform == "win32" else "drawclock")


def _run(binary: Path, args: list[str], *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    isolated_path = ROOT / "example" / "out" / "empty-path"
    isolated_path.mkdir(parents=True, exist_ok=True)
    env["PATH"] = str(isolated_path)
    completed = subprocess.run(
        [str(binary), *args], cwd=ROOT, env=env, text=True,
        encoding="utf-8", errors="replace", capture_output=True, check=False,
    )
    if (completed.returncode == 0) != expect_success:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(1)
    return completed


def _edge_count(config: dict[str, dict[str, object]]) -> int:
    count = 0
    for item in config.values():
        source = item.get("source")
        count += len(source) if isinstance(source, dict) else int(source is not None)
    return count


def _assert_svg(
    path: Path, *, nodes: int, edges: int, max_total_bends: int | None = None,
) -> None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    if root.tag != f"{{{SVG_NS}}}svg":
        raise SystemExit(f"not SVG: {path}")
    rendered_edges = [
        element for element in list(root)
        if element.get("class") == "edge"
    ]
    rendered_nodes = root.findall(f"{{{SVG_NS}}}foreignObject")
    if len(rendered_nodes) < nodes or len(rendered_edges) != edges:
        raise SystemExit(
            f"unexpected SVG topology: {path} nodes={len(rendered_nodes)} edges={len(rendered_edges)}"
        )
    view_box = [float(value) for value in root.get("viewBox", "").split()]
    if len(view_box) != 4 or view_box[2] <= 0 or view_box[3] <= 0:
        raise SystemExit(f"invalid SVG bounds: {path}")
    total_bends = sum(
        max(0, len(element.get("points", "").split()) - 2)
        for element in rendered_edges
    )
    if max_total_bends is not None and total_bends > max_total_bends:
        raise SystemExit(
            f"avoidable frozen SVG bends: {path} "
            f"total={total_bends} maximum={max_total_bends}"
        )


def _draw(
    binary: Path, source: Path, output: Path, *extra: str,
    max_total_bends: int | None = None,
) -> None:
    _run(binary, ["-i", str(source), "-l", str(LIBRARY), "-o", str(output), *extra])
    config = json.loads(source.read_text(encoding="utf-8"))
    _assert_svg(
        output, nodes=len(config), edges=_edge_count(config),
        max_total_bends=max_total_bends,
    )


def _assert_named_nodes_same_x(path: Path, names: tuple[str, ...]) -> None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    x_by_name: dict[str, float] = {}
    for element in root.findall(f"{{{SVG_NS}}}foreignObject"):
        text_content = "".join(element.itertext())
        for name in names:
            if name in text_content:
                x_by_name[name] = float(element.get("x", "nan"))
    if set(x_by_name) != set(names) or len(set(x_by_name.values())) != 1:
        raise SystemExit(f"layout_column nodes are not co-column: {x_by_name}")


def main() -> int:
    global ROOT, LIBRARY, DRAW_EXAMPLE, LINEAR, DENSE, STRESS, ASYMMETRIC
    global COLUMN_PREFERENCE
    binary = _binary_path()
    package_root = binary.parent
    if (package_root / "runtime" / "runtime-manifest.json").is_file():
        ROOT = package_root
        LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
        DRAW_EXAMPLE = ROOT / "example" / "draw.json"
        LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
        DENSE = ROOT / "example" / "auto-layout" / "05-dense-cross-root.json"
        STRESS = ROOT / "example" / "auto-layout" / "08-stress-512-clocks.json"
        ASYMMETRIC = ROOT / "example" / "auto-layout" / "20-asymmetric-merge-route-bulge.json"
        COLUMN_PREFERENCE = ROOT / "example" / "auto-layout" / "21-layout-column-preference.json"
    runtime = binary.parent / "runtime"
    required = (
        binary, LIBRARY, DRAW_EXAMPLE, LINEAR, DENSE, STRESS, ASYMMETRIC,
        COLUMN_PREFERENCE,
        runtime / "runtime-manifest.json",
        runtime / ("node/node.exe" if sys.platform == "win32" else "node/bin/node"),
        runtime / "elk" / "elk_layout.mjs",
        runtime / "elk" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("missing release inputs:\n" + "\n".join(missing), file=sys.stderr)
        return 1

    out = ROOT / "example" / "out"
    out.mkdir(parents=True, exist_ok=True)
    _draw(binary, DRAW_EXAMPLE, out / "draw-example-frozen.svg")
    _draw(binary, LINEAR, out / "arbitrary-suffix.png", "--crossing-style", "gap")
    _draw(binary, DENSE, out / "dense-frozen.svg")
    _draw(binary, STRESS, out / "stress-512-frozen.svg")
    _draw(
        binary, ASYMMETRIC, out / "asymmetric-frozen.svg",
        max_total_bends=2,
    )
    column_output = out / "column-preference-frozen.svg"
    _draw(binary, COLUMN_PREFERENCE, column_output)
    _assert_named_nodes_same_x(column_output, ("sel_00", "sel_01", "sel_02"))

    formats = {
        "json": '{"osc":{"kind":"source"}}',
        "jsonc": '{// source\n"osc":{"kind":"source"}}',
        "json5": "{'osc':{kind:'source'}}",
        "toml": '[osc]\nkind="source"\n',
        "yaml": "osc:\n  kind: source\n",
        "yml": "osc:\n  kind: source\n",
        "ini": "[osc]\nkind=source\n",
        "conf": "[osc]\nkind=source\n",
        "config": "[osc]\nkind=source\n",
    }
    for suffix, content in formats.items():
        config_path = out / f"frozen-input.{suffix}"
        image_path = out / f"frozen-input-{suffix}.svg"
        config_path.write_text(content, encoding="utf-8")
        _run(binary, ["-i", str(config_path), "-l", str(LIBRARY), "-o", str(image_path)])
        _assert_svg(image_path, nodes=1, edges=0)

    for removed in ("draw", "extract", "reload", "run", "drawio-to-json"):
        _run(binary, [removed], expect_success=False)
    print("frozen draw workflow passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
