"""Generate example/demo.drawio from drawio-lib/drawclock.xml with orthogonal routing."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drawio_build import xml_attr  # noqa: E402
from drawio_library import (  # noqa: E402
    DEFAULT_LIBRARY_PATH,
    LibraryShape,
    bake_label_placeholders,
    load_library_shapes,
)
from drawio_ports import (  # noqa: E402
    chain_edge_route,
    mux_fanin_edge_style,
    port_anchors,
    y_for_port,
)

OUT = ROOT / "example" / "demo.drawio"

ROW_CY = 110
ROW_DY = 200
X0 = 40
MUX_X = 240
PLL_X = 40
STUB_X_OFFSET = 36

DEVICE_LIB: dict[str, str] = {
    "pll_main": "pll",
    "gate0": "gate",
    "div0": "div",
    "inv0": "inv",
    "dto0": "dto",
    "clk_sys": "clock",
    "pll_m2a": "pll",
    "pll_m2b": "pll",
    "pll_m3a": "pll",
    "pll_m3b": "pll",
    "pll_m3c": "pll",
    "pll_m4a": "pll",
    "pll_m4b": "pll",
    "pll_m4c": "pll",
    "pll_m4d": "pll",
    "pll_m5a": "pll",
    "pll_m5b": "pll",
    "pll_m5c": "pll",
    "pll_m5d": "pll",
    "pll_m5e": "pll",
    "pll_m6a": "pll",
    "pll_m6b": "pll",
    "pll_m6c": "pll",
    "pll_m6d": "pll",
    "pll_m6e": "pll",
    "pll_m6f": "pll",
    "mux2": "mux2",
    "mux3": "mux3",
    "mux4": "mux4",
    "mux5": "mux5",
    "mux6": "mux6",
    "clk_m2": "clock",
    "clk_m3": "clock",
    "clk_m4": "clock",
    "clk_m5": "clock",
    "clk_m6": "clock",
}

OBJECT_EXTRA: dict[str, dict[str, str]] = {
    "clk_sys": {"freq": "100"},
    "clk_m2": {"freq": "200"},
    "clk_m3": {"freq": "300"},
    "clk_m4": {"freq": "400"},
    "clk_m5": {"freq": "500"},
    "clk_m6": {"freq": "600"},
    "mux2": {"in0_label": "a", "in1_label": "b"},
}


@dataclass
class Placed:
    name: str
    lib: str
    x: float
    y: float
    shape: LibraryShape
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class EdgeSpec:
    src: str
    tgt: str
    style: str
    waypoints: tuple[tuple[float, float], ...] = ()


def _top_for_port(bus_y: float, shape: LibraryShape, lib: str, port: str) -> float:
    return y_for_port(shape.h, shape.style, lib, port, bus_y)


def _connect(
    edges: list[EdgeSpec],
    placed: dict[str, Placed],
    src: str,
    tgt: str,
    *,
    src_port: str = "right",
    tgt_port: str = "left",
) -> None:
    a, b = placed[src], placed[tgt]
    style, wpts = chain_edge_route(
        a.x,
        a.y,
        a.shape.w,
        a.shape.h,
        a.shape.style,
        a.lib,
        b.x,
        b.y,
        b.shape.w,
        b.shape.h,
        b.shape.style,
        b.lib,
        src_port=src_port,
        tgt_port=tgt_port,
    )
    edges.append(EdgeSpec(src, tgt, style, wpts))


def _place_chain(
    shapes: dict[str, LibraryShape],
    names: list[str],
    *,
    row_cy: float,
    x0: float,
) -> tuple[list[Placed], list[EdgeSpec]]:
    wire_shape = shapes["wire"]
    placed_list: list[Placed] = []
    placed: dict[str, Placed] = {}
    edges: list[EdgeSpec] = []
    x = float(x0)

    for index, name in enumerate(names):
        lib = DEVICE_LIB[name]
        shape = shapes[lib]
        if index > 0:
            prev = placed_list[-1]
            wire_x = prev.x + prev.shape.w
            wire_y = _top_for_port(row_cy, wire_shape, "wire", "left")
            wire = Placed(
                f"w_{prev.name}_{name}",
                "wire",
                wire_x,
                wire_y,
                wire_shape,
            )
            placed_list.append(wire)
            placed[wire.name] = wire
            _connect(edges, placed, prev.name, wire.name)
            x = wire_x + wire_shape.w

        out_port = "left" if lib == "clock" else "right"
        dev_y = _top_for_port(row_cy, shape, lib, out_port)
        dev = Placed(name, lib, x, dev_y, shape, dict(OBJECT_EXTRA.get(name, {})))
        placed_list.append(dev)
        placed[name] = dev
        if index > 0:
            _connect(edges, placed, placed_list[-2].name, name)
        x = dev.x + dev.shape.w

    return placed_list, edges


def _place_mux_row(
    shapes: dict[str, LibraryShape],
    mux_name: str,
    pll_names: list[str],
    clk_name: str,
    *,
    row_cy: float,
) -> tuple[list[Placed], list[EdgeSpec]]:
    mux_lib = DEVICE_LIB[mux_name]
    mux_shape = shapes[mux_lib]
    mux_y = _top_for_port(row_cy, mux_shape, mux_lib, "out")
    mux = Placed(mux_name, mux_lib, MUX_X, mux_y, mux_shape, dict(OBJECT_EXTRA.get(mux_name, {})))
    placed_list: list[Placed] = [mux]
    placed: dict[str, Placed] = {mux_name: mux}
    edges: list[EdgeSpec] = []
    pll_shape = shapes["pll"]
    stub_x = MUX_X - STUB_X_OFFSET

    for index, pll_name in enumerate(pll_names):
        in_frac = port_anchors(mux_shape.style, mux_lib)[f"in{index}"][1]
        target_y = mux_y + mux_shape.h * in_frac
        pll_y = y_for_port(pll_shape.h, pll_shape.style, "pll", "right", target_y)
        pll = Placed(pll_name, "pll", PLL_X, pll_y, pll_shape)
        placed_list.append(pll)
        placed[pll_name] = pll
        style, wpts = mux_fanin_edge_style(
            pll.x,
            pll.y,
            pll.shape.w,
            pll.shape.h,
            pll.shape.style,
            pll.lib,
            mux.x,
            mux.y,
            mux.shape.w,
            mux.shape.h,
            mux.shape.style,
            mux.lib,
            index,
            stub_x=stub_x,
        )
        edges.append(EdgeSpec(pll_name, mux_name, style, wpts))

    wire_shape = shapes["wire"]
    wire_x = mux.x + mux.shape.w
    wire_y = _top_for_port(row_cy, wire_shape, "wire", "left")
    wire_name = f"w_{mux_name}_clk"
    wire = Placed(wire_name, "wire", wire_x, wire_y, wire_shape)
    placed_list.append(wire)
    placed[wire_name] = wire
    _connect(edges, placed, mux_name, wire_name, src_port="out", tgt_port="left")

    clk_shape = shapes["clock"]
    clk_x = wire_x + wire_shape.w
    clk_y = _top_for_port(row_cy, clk_shape, "clock", "left")
    clk = Placed(clk_name, "clock", clk_x, clk_y, clk_shape, dict(OBJECT_EXTRA.get(clk_name, {})))
    placed_list.append(clk)
    placed[clk_name] = clk
    _connect(edges, placed, wire_name, clk_name)

    return placed_list, edges


def _object_xml(cell_id: int, item: Placed) -> str:
    attrs: dict[str, str] = {
        "name": item.name,
        "placeholders": "0",
        "id": str(cell_id),
    }
    attrs.update(item.extra)
    attrs["label"] = bake_label_placeholders(item.shape.label, attrs)
    ordered_keys = ["name", "label", "placeholders", "id"] + sorted(
        k for k in attrs if k not in ("name", "label", "placeholders", "id")
    )
    attr_s = " ".join(f'{key}="{xml_attr(attrs[key])}"' for key in ordered_keys)
    return (
        f"        <object {attr_s}>\n"
        f'          <mxCell style="{xml_attr(item.shape.style)}" vertex="1" parent="1">\n'
        f'            <mxGeometry x="{int(item.x)}" y="{int(item.y)}" width="{item.shape.w}" '
        f'height="{item.shape.h}" as="geometry"/>\n'
        f"          </mxCell>\n"
        f"        </object>"
    )


def _edge_xml(edge_id: int, edge: EdgeSpec, name_to_id: dict[str, int]) -> str:
    points_xml = ""
    if edge.waypoints:
        pts = "".join(
            f'<mxPoint x="{int(x)}" y="{int(y)}" as="point"/>'
            for x, y in edge.waypoints
        )
        points_xml = f"<Array as=\"points\">{pts}</Array>"
    return (
        f'        <mxCell id="{edge_id}" '
        f'style="{edge.style}" '
        f'edge="1" parent="1" source="{name_to_id[edge.src]}" target="{name_to_id[edge.tgt]}">\n'
        f'          <mxGeometry relative="1" as="geometry">{points_xml}</mxGeometry>\n'
        f"        </mxCell>"
    )


def build(shapes: dict[str, LibraryShape]) -> str:
    all_placed: list[Placed] = []
    all_edges: list[EdgeSpec] = []

    row1, e1 = _place_chain(
        shapes,
        ["pll_main", "gate0", "div0", "inv0", "dto0", "clk_sys"],
        row_cy=ROW_CY,
        x0=X0,
    )
    all_placed.extend(row1)
    all_edges.extend(e1)

    for row_i, (mux, plls, clk) in enumerate(
        [
            ("mux2", ["pll_m2a", "pll_m2b"], "clk_m2"),
            ("mux3", ["pll_m3a", "pll_m3b", "pll_m3c"], "clk_m3"),
            ("mux4", ["pll_m4a", "pll_m4b", "pll_m4c", "pll_m4d"], "clk_m4"),
            ("mux5", ["pll_m5a", "pll_m5b", "pll_m5c", "pll_m5d", "pll_m5e"], "clk_m5"),
            (
                "mux6",
                ["pll_m6a", "pll_m6b", "pll_m6c", "pll_m6d", "pll_m6e", "pll_m6f"],
                "clk_m6",
            ),
        ]
    ):
        row, edges = _place_mux_row(
            shapes, mux, plls, clk, row_cy=ROW_CY + (row_i + 1) * ROW_DY
        )
        all_placed.extend(row)
        all_edges.extend(edges)

    lines = [
        "<mxfile>",
        "  <diagram>",
        "    <mxGraphModel>",
        "      <root>",
        '        <mxCell id="0"/>',
        '        <mxCell id="1" parent="0"/>',
    ]
    name_to_id: dict[str, int] = {}
    next_id = 10
    for item in all_placed:
        name_to_id[item.name] = next_id
        lines.append(_object_xml(next_id, item))
        next_id += 1
    for edge in all_edges:
        lines.append(_edge_xml(next_id, edge, name_to_id))
        next_id += 1
    lines.extend(
        [
            "      </root>",
            "    </mxGraphModel>",
            "  </diagram>",
            "</mxfile>",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(shapes), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
