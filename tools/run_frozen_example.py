"""Run the drawclock example workflow through a frozen executable."""

from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib
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
from pipeline import drawio_to_clock_tree  # noqa: E402
from layout_preview import SUPPORTED_IMAGE_SUFFIXES  # noqa: E402
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
FIG1 = ROOT / "example" / "fig1.drawio"
FIG2 = ROOT / "example" / "fig2.drawio"
AUTO_LINEAR = ROOT / "example" / "auto-layout" / "01-linear.json"
STRESS_512 = ROOT / "example" / "auto-layout" / "08-stress-512-clocks.json"
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
        env.pop("CHROME_PATH", None)
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


def _run_expect_failure(binary: Path, args: list[str], cwd: Path, needle: str) -> None:
    completed = subprocess.run(
        [str(binary), *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode == 0 or needle not in completed.stderr:
        print(f"command should fail with {needle!r}: {args}", file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(1)


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


def _paeth(left: int, up: int, upper_left: int) -> int:
    prediction = left + up - upper_left
    distances = (
        abs(prediction - left), abs(prediction - up), abs(prediction - upper_left)
    )
    return (left, up, upper_left)[distances.index(min(distances))]


def _png_metrics(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"invalid PNG signature: {path}")
    offset = 8
    width = height = bit_depth = color_type = 0
    compressed = bytearray()
    saw_iend = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise AssertionError("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        checksum_offset = offset + 8 + length
        if checksum_offset + 4 > len(data):
            raise AssertionError(f"truncated PNG chunk: {kind!r}")
        expected_crc = struct.unpack(">I", data[checksum_offset : checksum_offset + 4])[0]
        if zlib.crc32(kind + payload) != expected_crc:
            raise AssertionError(f"PNG chunk CRC mismatch: {kind!r}")
        offset += length + 12
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            saw_iend = True
            break
    if not saw_iend or offset != len(data):
        raise AssertionError("PNG does not end at a valid IEND chunk")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if bit_depth != 8 or channels is None or width <= 0 or height <= 0:
        raise AssertionError(
            f"unsupported PNG raster contract: {width}x{height}, "
            f"depth={bit_depth}, color={color_type}"
        )
    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    if len(raw) != (stride + 1) * height:
        raise AssertionError("PNG scanline length does not match IHDR")
    previous = bytearray(stride)
    non_white = 0
    cursor = 0
    for _row in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        for index, value in enumerate(scanline):
            left = scanline[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                scanline[index] = (value + left) & 0xFF
            elif filter_type == 2:
                scanline[index] = (value + up) & 0xFF
            elif filter_type == 3:
                scanline[index] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[index] = (value + _paeth(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise AssertionError(f"unsupported PNG filter: {filter_type}")
        for index in range(0, stride, channels):
            if color_type in (0, 4):
                rgb = (scanline[index],) * 3
                alpha = scanline[index + 1] if color_type == 4 else 255
            else:
                rgb = tuple(scanline[index : index + 3])
                alpha = scanline[index + 3] if color_type == 6 else 255
            if alpha > 0 and min(rgb) < 250:
                non_white += 1
        previous = scanline
    return width, height, non_white


def _assert_png_image(path: Path, *, expected_size: tuple[int, int]) -> None:
    width, height, non_white = _png_metrics(path)
    if (width, height) != expected_size:
        raise AssertionError(
            f"PNG/SVG dimension mismatch: {width}x{height} != "
            f"{expected_size[0]}x{expected_size[1]}"
        )
    if non_white < 100:
        raise AssertionError(f"PNG is blank or nearly blank: {non_white} dark pixels")


def main() -> int:
    binary = _binary_path()
    if not binary.is_file():
        print(f"frozen executable not found: {binary}", file=sys.stderr)
        return 1
    runtime = binary.parent / "runtime"
    chrome = runtime / "headless-shell" / (
        "chrome-headless-shell.exe" if sys.platform == "win32"
        else "chrome-headless-shell"
    )
    node = runtime / "node" / ("node.exe" if sys.platform == "win32" else "bin/node")
    runtime_files = (
        runtime / "runtime-manifest.json",
        chrome,
        node,
        runtime / "elk" / "elk_layout.mjs",
        runtime / "elk" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js",
    )
    for required_runtime in runtime_files:
        if not required_runtime.is_file():
            print(f"bundled runtime missing: {required_runtime}", file=sys.stderr)
            return 1
    for required in (LIBRARY, FIG1, FIG2, AUTO_LINEAR, DRAW_EXAMPLE):
        if not required.is_file():
            print(f"example input missing: {required}", file=sys.stderr)
            return 1

    out_dir = ROOT / "example" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    clock_tree = out_dir / "clock-tree-frozen-smoke.json"
    fig1_reloaded = out_dir / "fig1-frozen-smoke.drawio"
    fig2_reloaded = out_dir / "fig2-frozen-smoke.drawio"
    generated_drawio = out_dir / "linear-frozen-smoke.drawio"
    generated_svg = out_dir / "linear-frozen-smoke.svg"
    generated_png = out_dir / "linear-frozen-smoke.png"
    draw_example_output = out_dir / "draw-example-frozen-smoke.drawio"
    draw_example_svg = out_dir / "draw-example-frozen-smoke.svg"
    draw_example_png = out_dir / "draw-example-frozen-smoke.png"
    fanout_config = out_dir / "fanout-frozen-smoke.json"
    fanout_svg = out_dir / "fanout-frozen-smoke.svg"
    stress_svg = out_dir / "stress-512-frozen-smoke.svg"

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
    if set(SUPPORTED_IMAGE_SUFFIXES) != {".svg", ".png"}:
        print(
            f"frozen image-format matrix is stale: {SUPPORTED_IMAGE_SUFFIXES}",
            file=sys.stderr,
        )
        return 1
    for image_output in (draw_example_svg, draw_example_png):
        _run(
            binary,
            [
                "draw", "-i", str(DRAW_EXAMPLE), "-l", str(LIBRARY),
                "-o", str(image_output), "--crossing-style", "gap",
            ],
            ROOT,
            isolated_runtime=True,
        )
    draw_svg_size = _assert_svg_image(
        draw_example_svg, expected_nodes=10, expected_edges=9
    )
    _assert_png_image(draw_example_png, expected_size=draw_svg_size)
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

    for output in (generated_drawio, generated_svg, generated_png):
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
    if drawio_to_clock_tree([generated_drawio], library_path=LIBRARY) != json.loads(
        AUTO_LINEAR.read_text(encoding="utf-8")
    ):
        print("frozen draw output did not round-trip", file=sys.stderr)
        return 1
    linear_config = json.loads(AUTO_LINEAR.read_text(encoding="utf-8"))
    linear_svg_size = _assert_svg_image(
        generated_svg,
        expected_nodes=len(linear_config),
        expected_edges=sum("source" in item for item in linear_config.values()),
    )
    _assert_png_image(generated_png, expected_size=linear_svg_size)

    _run(
        binary,
        [
            "draw",
            "-i",
            str(DRAW_EXAMPLE),
            "-l",
            str(LIBRARY),
            "-o",
            str(draw_example_output),
        ],
        ROOT,
    )
    draw_model = iter_diagram_models(extract_mxfile_xml(str(draw_example_output)))[0]
    default_edges = [cell for cell in draw_model.iter("mxCell") if cell.get("edge") == "1"]
    if not default_edges or any(
        "jumpStyle=arc;" not in cell.get("style", "") for cell in default_edges
    ):
        print("frozen draw default crossing style is not arc", file=sys.stderr)
        return 1
    actual_components = {
        obj.get("name"): (obj.find("mxCell").get("style", "") if obj.find("mxCell") is not None else "")
        for obj in draw_model.iter("object")
        if obj.get("name")
    }
    expected_components = {
        "osc": "source",
        "external_clk": "from",
        "clock_select": "mux2",
        "pll_main": "pll",
        "divider": "div",
        "tuner": "dto",
        "inverter": "inv",
        "clock_cell": "cell",
        "clock_gate": "gate",
        "core_clock": "clock",
    }
    for name, component in expected_components.items():
        if f"drawclockType={component};" not in actual_components.get(name, ""):
            print(f"frozen draw example omitted {name} as {component}", file=sys.stderr)
            return 1
    _run_expect_failure(
        binary,
        [
            "draw",
            "-i",
            str(AUTO_LINEAR),
            "-l",
            str(LIBRARY),
            "-o",
            str(out_dir / "unsupported-frozen-smoke.bmp"),
        ],
        ROOT,
        ".drawio, .svg, .png",
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
    custom_output = out_dir / "custom-library-frozen-smoke.drawio"
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
    model = iter_diagram_models(extract_mxfile_xml(str(custom_output)))[0]
    custom_gate = next(
        (obj for obj in model.iter("object") if obj.get("name") == "gate_main"),
        None,
    )
    if custom_gate is None:
        print("frozen draw omitted supplied-library component", file=sys.stderr)
        return 1
    cell = custom_gate.find("mxCell")
    if cell is None or "drawclockType=custom_gate_symbol;" not in cell.get("style", ""):
        print("frozen draw ignored supplied-library kind metadata", file=sys.stderr)
        return 1
    geometry = cell.find("mxGeometry")
    if geometry is None or (geometry.get("width"), geometry.get("height")) != ("83", "91"):
        print("frozen draw ignored supplied-library geometry", file=sys.stderr)
        return 1

    print("frozen example passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
