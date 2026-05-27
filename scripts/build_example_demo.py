"""Generate example/fig1.drawio and example/fig2.drawio (cross-sheet wires + direct chains)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RELOAD = ROOT / "reload"
for path in (SRC, RELOAD):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from drawio_build import xml_attr  # noqa: E402
from drawio_decode import compress_diagram_payload  # noqa: E402
from drawio_library import (  # noqa: E402
    DEFAULT_LIBRARY_PATH,
    LibraryShape,
    bake_label_placeholders,
    load_library_shapes,
)
from drawio_ports import (  # noqa: E402
    EDGE_DRAW_STYLE,
    abs_port_xy,
    chain_edge_route,
    port_anchors,
    y_for_port,
)

FIG1 = ROOT / "example" / "fig1.drawio"
FIG2 = ROOT / "example" / "fig2.drawio"

ROW_CY = 110
X0 = 40
STUB_X_OFFSET = 36
BUS_WIRE_NAME = "bus_xtal"


@dataclass
class Placed:
    key: str
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


def _connect_elbow(
    edges: list[EdgeSpec],
    placed: dict[str, Placed],
    src: str,
    tgt: str,
    *,
    src_port: str = "right",
    tgt_port: str = "left",
    bend_x: float | None = None,
) -> None:
    """Orthogonal edge with two mxPoint waypoints."""
    a, b = placed[src], placed[tgt]
    exit_xy = port_anchors(a.shape.style, a.lib)[src_port]
    entry_xy = port_anchors(b.shape.style, b.lib)[tgt_port]
    ex, ey = abs_port_xy(
        a.x, a.y, a.shape.w, a.shape.h, a.shape.style, a.lib, src_port
    )
    ix, iy = abs_port_xy(
        b.x, b.y, b.shape.w, b.shape.h, b.shape.style, b.lib, tgt_port
    )
    style = (
        f"{EDGE_DRAW_STYLE}"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};"
    )
    mid_x = bend_x if bend_x is not None else (ex + ix) / 2
    edges.append(EdgeSpec(src, tgt, style, ((mid_x, ey), (mid_x, iy))))


def _connect_pll_main_fanout(
    edges: list[EdgeSpec],
    placed: dict[str, Placed],
    tgt: str,
    *,
    stub_x: float,
) -> None:
    """pll_main 一分二：与用户手改 fig2 边 25/26 相同，2 个航点 + 竖汇流柱。

    见 ~/.cursor/skills/drawio-edge-waypoints/SKILL.md、example/refs/pll_main_fanout_waypoints.json
    """
    a, b = placed["pll_main"], placed[tgt]
    exit_xy = port_anchors(a.shape.style, a.lib)["right"]
    entry_xy = port_anchors(b.shape.style, b.lib)["left"]
    _, ey = abs_port_xy(
        a.x, a.y, a.shape.w, a.shape.h, a.shape.style, a.lib, "right"
    )
    _, iy = abs_port_xy(
        b.x, b.y, b.shape.w, b.shape.h, b.shape.style, b.lib, "left"
    )
    style = (
        f"{EDGE_DRAW_STYLE}"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};"
    )
    edges.append(
        EdgeSpec("pll_main", tgt, style, ((stub_x, ey), (stub_x, iy)))
    )


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
    if edge.waypoints:
        pts = "".join(
            f'<mxPoint x="{int(x)}" y="{int(y)}"/>'
            for x, y in edge.waypoints
        )
        geom = (
            f'<mxGeometry as="geometry"><Array as="points">{pts}</Array></mxGeometry>'
        )
    else:
        geom = '<mxGeometry relative="1" as="geometry"/>'
    return (
        f'        <mxCell id="{edge_id}" '
        f'style="{edge.style}" '
        f'edge="1" parent="1" source="{name_to_id[edge.src]}" target="{name_to_id[edge.tgt]}">\n'
        f"          {geom}\n"
        f"        </mxCell>"
    )


def _assemble(diagram_name: str, placed: list[Placed], edges: list[EdgeSpec]) -> str:
    lines = [
        "      <root>",
        '        <mxCell id="0"/>',
        '        <mxCell id="1" parent="0"/>',
    ]
    name_to_id: dict[str, int] = {}
    next_id = 10
    for item in placed:
        name_to_id[item.key] = next_id
        lines.append(_object_xml(next_id, item))
        next_id += 1
    for edge in edges:
        lines.append(_edge_xml(next_id, edge, name_to_id))
        next_id += 1
    lines.append("      </root>")
    model_xml = (
        "<mxGraphModel>\n"
        + "\n".join(lines)
        + "\n    </mxGraphModel>"
    )
    payload = compress_diagram_payload(model_xml)
    return (
        "<mxfile>\n"
        f'  <diagram id="{xml_attr(diagram_name)}" name="{xml_attr(diagram_name)}">'
        f"{payload}</diagram>\n"
        "</mxfile>\n"
    )


def build_fig1(shapes: dict[str, LibraryShape]) -> str:
    """图 1：仅 xtal 输出接到跨图 wire（右端悬空）。"""
    source_shape = shapes["source"]
    wire_shape = shapes["wire"]
    placed: dict[str, Placed] = {}
    edges: list[EdgeSpec] = []

    row_src = 60
    row_wire = 120
    src = Placed(
        "xtal",
        "xtal",
        "source",
        X0,
        _top_for_port(row_src, source_shape, "source", "right"),
        source_shape,
    )
    placed["xtal"] = src

    wire_x = src.x + src.shape.w + 16
    wire = Placed(
        "bus_wire",
        BUS_WIRE_NAME,
        "wire",
        wire_x,
        _top_for_port(row_wire, wire_shape, "wire", "left"),
        wire_shape,
    )
    placed["bus_wire"] = wire
    # 折线 + 航点：跨图出口（源与 wire 错行，航点 Y 不同）
    _connect_elbow(
        edges,
        placed,
        "xtal",
        "bus_wire",
        bend_x=wire_x - 20,
    )

    return _assemble("fig1", list(placed.values()), edges)


def build_fig2(shapes: dict[str, LibraryShape]) -> str:
    """图 2：跨图 wire 一分二；pll 一分二；下游直连；mux 标签 0/1。"""
    wire_shape = shapes["wire"]
    gate_shape = shapes["gate"]
    div_shape = shapes["div"]
    inv_shape = shapes["inv"]
    pll_shape = shapes["pll"]
    mux_shape = shapes["mux2"]
    clk_shape = shapes["clock"]
    placed: dict[str, Placed] = {}
    edges: list[EdgeSpec] = []

    row_wire_a = 80
    row_gate_a = 80
    row_wire_b = 200
    row_gate_b = 200
    row_mux = 340

    wire_a = Placed(
        "wire_a",
        BUS_WIRE_NAME,
        "wire",
        X0,
        _top_for_port(row_wire_a, wire_shape, "wire", "right"),
        wire_shape,
    )
    wire_b = Placed(
        "wire_b",
        BUS_WIRE_NAME,
        "wire",
        X0,
        _top_for_port(row_wire_b, wire_shape, "wire", "right"),
        wire_shape,
    )
    placed["wire_a"] = wire_a
    placed["wire_b"] = wire_b

    x_dev = X0 + wire_shape.w + 20
    gate0 = Placed(
        "gate0",
        "gate0",
        "gate",
        x_dev,
        _top_for_port(row_gate_a, gate_shape, "gate", "left"),
        gate_shape,
    )
    div0 = Placed(
        "div0",
        "div0",
        "div",
        x_dev,
        _top_for_port(row_gate_b, div_shape, "div", "left"),
        div_shape,
    )
    placed["gate0"] = gate0
    placed["div0"] = div0
    _connect(edges, placed, "wire_a", "gate0", tgt_port="left", src_port="right")
    _connect(edges, placed, "wire_b", "div0", tgt_port="left", src_port="right")

    pll = Placed(
        "pll_main",
        "pll_main",
        "pll",
        X0 - 120,
        _top_for_port((row_gate_a + row_gate_b) / 2, pll_shape, "pll", "right"),
        pll_shape,
    )
    placed["pll_main"] = pll
    stub_x = placed["gate0"].x - 10
    _connect_pll_main_fanout(edges, placed, "gate0", stub_x=stub_x)
    _connect_pll_main_fanout(edges, placed, "div0", stub_x=stub_x)

    x_mid = x_dev + gate_shape.w + 40
    inv0 = Placed(
        "inv0",
        "inv0",
        "inv",
        x_mid,
        _top_for_port(row_gate_a, inv_shape, "inv", "left"),
        inv_shape,
    )
    dto0 = Placed(
        "dto0",
        "dto0",
        "dto",
        x_mid,
        _top_for_port(row_gate_b, shapes["dto"], "dto", "left"),
        shapes["dto"],
    )
    placed["inv0"] = inv0
    placed["dto0"] = dto0
    _connect(edges, placed, "gate0", "inv0")
    _connect(edges, placed, "div0", "dto0")

    x_clk = x_dev + inv_shape.w + 40
    clk_a = Placed(
        "clk_a",
        "clk_a",
        "clock",
        x_clk,
        _top_for_port(row_gate_a, clk_shape, "clock", "left"),
        clk_shape,
        {"freq": "100k"},
    )
    clk_b = Placed(
        "clk_b",
        "clk_b",
        "clock",
        x_clk,
        _top_for_port(row_gate_b, clk_shape, "clock", "left"),
        clk_shape,
        {"freq": "50M"},
    )
    placed["clk_a"] = clk_a
    placed["clk_b"] = clk_b
    _connect(edges, placed, "inv0", "clk_a")
    _connect(edges, placed, "dto0", "clk_b")

    mux = Placed(
        "mux2",
        "mux2",
        "mux2",
        240,
        _top_for_port(row_mux, mux_shape, "mux2", "out"),
        mux_shape,
        {"in0_label": "0", "in1_label": "1"},
    )
    placed["mux2"] = mux
    pll_m2a = Placed(
        "pll_m2a",
        "pll_m2a",
        "pll",
        40,
        _top_for_port(row_mux - 30, pll_shape, "pll", "right"),
        pll_shape,
    )
    pll_m2b = Placed(
        "pll_m2b",
        "pll_m2b",
        "pll",
        40,
        _top_for_port(row_mux + 30, pll_shape, "pll", "right"),
        pll_shape,
    )
    placed["pll_m2a"] = pll_m2a
    placed["pll_m2b"] = pll_m2b
    for index, pll_key in enumerate(("pll_m2a", "pll_m2b")):
        _connect(
            edges,
            placed,
            pll_key,
            "mux2",
            src_port="right",
            tgt_port=f"in{index}",
        )

    clk_mux = Placed(
        "clk_mux",
        "clk_mux",
        "clock",
        mux.x + mux.shape.w + 40,
        _top_for_port(row_mux, clk_shape, "clock", "left"),
        clk_shape,
        {"freq": "200m"},
    )
    placed["clk_mux"] = clk_mux
    _connect(edges, placed, "mux2", "clk_mux", src_port="out")

    return _assemble("fig2", list(placed.values()), edges)


def main() -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    FIG1.parent.mkdir(parents=True, exist_ok=True)
    FIG1.write_text(build_fig1(shapes), encoding="utf-8")
    FIG2.write_text(build_fig2(shapes), encoding="utf-8")
    print(f"wrote {FIG1}")
    print(f"wrote {FIG2}")


if __name__ == "__main__":
    main()
