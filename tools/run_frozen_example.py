"""Run the drawclock example workflow through a frozen executable."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drawio_decode import (  # noqa: E402
    compress_diagram_payload,
    decompress_diagram_payload,
    extract_mxfile_xml,
    iter_diagram_models,
)
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
FIG1 = ROOT / "example" / "fig1.drawio"
FIG2 = ROOT / "example" / "fig2.drawio"
AUTO_LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
AUTO_DENSE = ROOT / "example" / "auto-layout" / "05-dense-cross-root.json"
STRESS_512 = ROOT / "example" / "auto-layout" / "08-stress-512-clocks.json"
ASYMMETRIC_MERGE = (
    ROOT / "example" / "auto-layout" / "20-asymmetric-merge-route-bulge.json"
)
DRAW_EXAMPLE = ROOT / "example" / "draw.json"
SVG_NS = "http://www.w3.org/2000/svg"


def _binary_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    name = "drawclock.exe" if sys.platform == "win32" else "drawclock"
    return ROOT / "dist" / name


def _run(
    binary: Path, args: list[str], cwd: Path, *, isolated_runtime: bool = False
) -> None:
    cmd = [str(binary), *args]
    env = None
    if isolated_runtime:
        env = os.environ.copy()
        empty_path = cwd / "example" / "out" / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        env["PATH"] = str(empty_path)
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
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


def _assert_svg_image(
    path: Path, *, expected_nodes: int, expected_edges: int
) -> tuple[int, int]:
    try:
        root = ET.parse(path).getroot()
        width = math.ceil(float(root.attrib["width"]))
        height = math.ceil(float(root.attrib["height"]))
        viewbox = tuple(float(value) for value in root.attrib["viewBox"].split())
        if len(viewbox) != 4:
            raise ValueError("viewBox must contain four numbers")
    except (ET.ParseError, KeyError, ValueError) as exc:
        raise AssertionError(f"invalid frozen SVG {path}: {exc}") from exc
    nodes = root.findall(f".//{{{SVG_NS}}}foreignObject")
    edges = [
        element for element in root.findall(f".//{{{SVG_NS}}}polyline")
        if element.attrib.get("class") == "edge"
    ]
    edge_paths = [
        element for element in root.findall(f".//{{{SVG_NS}}}path")
        if element.attrib.get("class") == "edge"
    ]
    edges.extend(edge_paths)
    if len(nodes) != expected_nodes or len(edges) != expected_edges:
        raise AssertionError(
            f"unexpected SVG topology: nodes={len(nodes)}, edges={len(edges)}"
        )
    for edge in edges:
        if edge.tag.endswith("path"):
            if not edge.attrib.get("d", "").startswith("M "):
                raise AssertionError("SVG edge path is missing its start point")
            continue
        points = edge.attrib.get("points", "").split()
        if len(points) < 2:
            raise AssertionError("SVG edge has fewer than two endpoints")
        for point in points:
            x, y = point.split(",", 1)
            px, py = float(x), float(y)
            min_x, min_y, box_width, box_height = viewbox
            if not (
                min_x <= px <= min_x + box_width
                and min_y <= py <= min_y + box_height
            ):
                raise AssertionError(
                    f"SVG edge point outside viewBox: {px},{py} not in {viewbox}"
                )
    if width <= 0 or height <= 0:
        raise AssertionError(f"invalid SVG dimensions: {width}x{height}")
    return width, height


def _svg_edge_points(element: ET.Element) -> list[tuple[float, float]]:
    if element.tag.endswith("polyline"):
        return [
            tuple(float(value) for value in token.split(",", 1))
            for token in element.attrib.get("points", "").split()
        ]
    return [
        (float(x), float(y))
        for x, y in re.findall(
            r"[ML]\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
            element.attrib.get("d", ""),
        )
    ]


def _assert_asymmetric_merge_routes(path: Path) -> None:
    root = ET.parse(path).getroot()
    mux = next(
        child
        for child in root
        if child.tag == f"{{{SVG_NS}}}foreignObject"
        and any(text.strip() == "sel" for text in child.itertext())
    )
    mux_left = float(mux.attrib["x"])
    mux_right = mux_left + float(mux.attrib["width"])
    mux_top = float(mux.attrib["y"])
    mux_bottom = mux_top + float(mux.attrib["height"])
    routes = []
    for child in root:
        if child.attrib.get("class") != "edge":
            continue
        points = _svg_edge_points(child)
        if (
            points
            and mux_left <= points[-1][0] <= mux_right
            and mux_top <= points[-1][1] <= mux_bottom
        ):
            routes.append(points)
    if len(routes) != 2:
        raise AssertionError(f"expected two mux input routes, found {len(routes)}")

    def directions(points: list[tuple[float, float]]) -> list[str]:
        result: list[str] = []
        for a, b in zip(points, points[1:]):
            direction = "h" if abs(a[1] - b[1]) <= 0.01 else "v"
            if not result or result[-1] != direction:
                result.append(direction)
        return result

    if any(len(directions(points)) - 1 > 2 for points in routes):
        raise AssertionError("asymmetric mux input contains an avoidable bulge")
    for a0, a1 in zip(routes[0], routes[0][1:]):
        for b0, b1 in zip(routes[1], routes[1][1:]):
            a_vertical = abs(a0[0] - a1[0]) <= 0.01
            b_vertical = abs(b0[0] - b1[0]) <= 0.01
            if a_vertical == b_vertical:
                continue
            vertical0, vertical1, horizontal0, horizontal1 = (
                (a0, a1, b0, b1)
                if a_vertical
                else (b0, b1, a0, a1)
            )
            x = vertical0[0]
            y = horizontal0[1]
            if (
                min(vertical0[1], vertical1[1]) < y < max(vertical0[1], vertical1[1])
                and min(horizontal0[0], horizontal1[0]) < x < max(horizontal0[0], horizontal1[0])
            ):
                raise AssertionError("asymmetric mux input routes cross")


def main() -> int:
    binary = _binary_path()
    if not binary.is_file():
        print(f"frozen executable not found: {binary}", file=sys.stderr)
        return 1
    runtime = binary.parent / "runtime"
    node = runtime / "node" / ("node.exe" if sys.platform == "win32" else "bin/node")
    runtime_files = (
        runtime / "runtime-manifest.json",
        node,
        runtime / "elk" / "elk_layout.mjs",
        runtime / "elk" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js",
    )
    for required_runtime in runtime_files:
        if not required_runtime.is_file():
            print(f"bundled runtime missing: {required_runtime}", file=sys.stderr)
            return 1
    for required in (
        LIBRARY,
        FIG1,
        FIG2,
        AUTO_LINEAR,
        AUTO_DENSE,
        ASYMMETRIC_MERGE,
        DRAW_EXAMPLE,
    ):
        if not required.is_file():
            print(f"example input missing: {required}", file=sys.stderr)
            return 1

    out_dir = ROOT / "example" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    clock_tree = out_dir / "clock-tree-frozen-smoke.json"
    fig1_reloaded = out_dir / "fig1-frozen-smoke.drawio"
    fig2_reloaded = out_dir / "fig2-frozen-smoke.drawio"
    generated_svg = out_dir / "linear-frozen-smoke.svg"
    draw_example_svg = out_dir / "draw-example-frozen-smoke.svg"
    arbitrary_suffix_svg = out_dir / "draw-example-frozen-smoke.output"
    fanout_config = out_dir / "fanout-frozen-smoke.json"
    fanout_svg = out_dir / "fanout-frozen-smoke.svg"
    stress_svg = out_dir / "stress-512-frozen-smoke.svg"
    asymmetric_merge_svg = out_dir / "asymmetric-merge-frozen-smoke.svg"
    default_arc_svg = out_dir / "default-arc-frozen-smoke.svg"

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
    for image_output in (draw_example_svg, arbitrary_suffix_svg):
        _run(
            binary,
            [
                "draw", "-i", str(DRAW_EXAMPLE), "-l", str(LIBRARY),
                "-o", str(image_output), "--crossing-style", "gap",
            ],
            ROOT,
            isolated_runtime=True,
        )
    _assert_svg_image(
        draw_example_svg, expected_nodes=10, expected_edges=9
    )
    _assert_svg_image(arbitrary_suffix_svg, expected_nodes=10, expected_edges=9)
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

    for output in (generated_svg,):
        _run(
            binary,
            [
                "draw",
                "-i",
                str(AUTO_LINEAR),
                "-l",
                str(LIBRARY),
                "-o",
                str(output),
                "--crossing-style",
                "gap",
            ],
            ROOT,
            isolated_runtime=True,
        )
    linear_config = json.loads(AUTO_LINEAR.read_text(encoding="utf-8"))
    _assert_svg_image(
        generated_svg,
        expected_nodes=len(linear_config),
        expected_edges=sum("source" in item for item in linear_config.values()),
    )

    example_svg_text = draw_example_svg.read_text(encoding="utf-8")
    for name in (
        "osc", "external_clk", "clock_select", "pll_main", "divider",
        "tuner", "inverter", "clock_cell", "clock_gate", "core_clock",
    ):
        if name not in example_svg_text:
            print(f"frozen draw example omitted {name}", file=sys.stderr)
            return 1
    _run(
        binary,
        ["draw", "-i", str(AUTO_DENSE), "-l", str(LIBRARY), "-o", str(default_arc_svg)],
        ROOT,
        isolated_runtime=True,
    )
    if "A 4 4" not in default_arc_svg.read_text(encoding="utf-8"):
        print("frozen draw default crossing style is not arc", file=sys.stderr)
        return 1
    for arbitrary_name in (
        "result-png-frozen-smoke.png",
        "result-drawio-frozen-smoke.drawio",
        "result-none-frozen-smoke.output",
    ):
        arbitrary_output = out_dir / arbitrary_name
        _run(
            binary,
            [
                "draw", "-i", str(AUTO_LINEAR), "-l", str(LIBRARY),
                "-o", str(arbitrary_output),
            ],
            ROOT,
            isolated_runtime=True,
        )
        _assert_svg_image(
            arbitrary_output,
            expected_nodes=len(linear_config),
            expected_edges=sum("source" in item for item in linear_config.values()),
        )

    format_samples = {
        "json": '{"晶振":{"kind":"source","source_kind":"source"}}',
        "jsonc": '{// source\n"晶振":{"kind":"source","source_kind":"source"}}',
        "json5": "{'晶振':{kind:'source',source_kind:'source'}}",
        "toml": '["晶振"]\nkind="source"\nsource_kind="source"\n',
        "yaml": "晶振:\n  kind: source\n  source_kind: source\n",
        "yml": "晶振:\n  kind: source\n  source_kind: source\n",
        "ini": "[晶振]\nkind=source\nsource_kind=source\n",
        "conf": "[晶振]\nkind=source\nsource_kind=source\n",
        "config": "[晶振]\nkind=source\nsource_kind=source\n",
    }
    for suffix, content in format_samples.items():
        config_path = out_dir / f"topology-{suffix}-frozen-smoke.{suffix}"
        image_path = out_dir / f"topology-{suffix}-frozen-smoke.svg"
        config_path.write_text(content, encoding="utf-8")
        _run(
            binary,
            [
                "draw",
                "-i",
                str(config_path),
                "-l",
                str(LIBRARY),
                "-o",
                str(image_path),
            ],
            ROOT,
        )

    fanout = {"root": {"kind": "source"}}
    fanout.update(
        {
            f"clock_{index:02d}": {"kind": "clock", "source": "root"}
            for index in range(20)
        }
    )
    fanout_config.write_text(json.dumps(fanout, indent=2), encoding="utf-8")
    _run(
        binary,
        [
            "draw", "-i", str(fanout_config), "-l", str(LIBRARY),
            "-o", str(fanout_svg),
        ],
        ROOT,
        isolated_runtime=True,
    )
    _assert_svg_image(fanout_svg, expected_nodes=21, expected_edges=20)
    asymmetric_config = json.loads(ASYMMETRIC_MERGE.read_text(encoding="utf-8"))
    _run(
        binary,
        [
            "draw", "-i", str(ASYMMETRIC_MERGE), "-l", str(LIBRARY),
            "-o", str(asymmetric_merge_svg),
        ],
        ROOT,
        isolated_runtime=True,
    )
    _assert_svg_image(
        asymmetric_merge_svg,
        expected_nodes=len(asymmetric_config),
        expected_edges=sum(
            len(item["source"]) if isinstance(item.get("source"), dict) else 1
            for item in asymmetric_config.values()
            if "source" in item
        ),
    )
    _assert_asymmetric_merge_routes(asymmetric_merge_svg)
    _run(
        binary,
        [
            "draw", "-i", str(STRESS_512), "-l", str(LIBRARY),
            "-o", str(stress_svg),
        ],
        ROOT,
        isolated_runtime=True,
    )
    _assert_svg_image(stress_svg, expected_nodes=1046, expected_edges=1300)

    library_text = LIBRARY.read_text(encoding="utf-8").strip()
    library_entries = json.loads(
        library_text[len("<mxlibrary>") : -len("</mxlibrary>")]
    )
    for entry in library_entries:
        if entry.get("title") == "gate":
            entry["title"] = "custom_gate_symbol"
            entry["w"] = 83
            entry["h"] = 91
            graph_xml = decompress_diagram_payload(entry["xml"])
            graph_xml = graph_xml.replace(
                "drawclockType=gate;", "drawclockType=custom_gate_symbol;"
            )
            entry["xml"] = compress_diagram_payload(graph_xml)
            break
    custom_library = out_dir / "custom-library-frozen-smoke.xml"
    custom_library.write_text(
        "<mxlibrary>" + json.dumps(library_entries) + "</mxlibrary>",
        encoding="utf-8",
    )
    custom_output = out_dir / "custom-library-frozen-smoke.svg"
    custom_config = out_dir / "custom-library-frozen-smoke.json"
    custom_topology = json.loads(AUTO_LINEAR.read_text(encoding="utf-8"))
    custom_topology["gate_main"]["kind"] = "custom_gate_symbol"
    custom_config.write_text(json.dumps(custom_topology), encoding="utf-8")
    _run(
        binary,
        [
            "draw",
            "-i",
            str(custom_config),
            "-l",
            str(custom_library),
            "-o",
            str(custom_output),
        ],
        ROOT,
    )
    custom_root = ET.parse(custom_output).getroot()
    children = list(custom_root)
    custom_gate = next(
        (
            child
            for child in children
            if child.tag == f"{{{SVG_NS}}}foreignObject"
            and "gate_main" in "".join(child.itertext())
        ),
        None,
    )
    if custom_gate is None:
        print("frozen draw omitted supplied-library component", file=sys.stderr)
        return 1
    if (
        custom_gate.get("width") != "85"
        or custom_gate.get("height") != "98"
    ):
        print("frozen draw ignored supplied-library geometry", file=sys.stderr)
        return 1

    print("frozen example passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
