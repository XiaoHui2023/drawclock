from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from drawio_library import (
    bake_label_placeholders,
    load_library_shapes,
    reload_object_attrs,
)
from drawio_ports import (
    edge_port_style,
    finalize_edge_style,
    merge_port_attachment,
    port_anchors,
    reload_edge_style,
)


def test_bake_label_replaces_name() -> None:
    baked = bake_label_placeholders(
        "<div>%name%</div>",
        {"name": "clk0"},
    )
    assert "clk0" in baked
    assert "%" not in baked


def test_reload_object_attrs_keeps_stored_fields_only() -> None:
    lib = ROOT / "drawio-lib" / "drawclock.xml"
    out = reload_object_attrs("pll", {"name": "pll0"}, library_path=lib)
    assert out["pll_kind"] == "SC"
    assert "%pll_kind%" in out["label"]
    kept = reload_object_attrs(
        "pll",
        {"name": "pll0", "pll_kind": "LC"},
        library_path=lib,
    )
    assert kept["pll_kind"] == "LC"


def test_bake_label_replaces_pll_kind_with_default() -> None:
    baked = bake_label_placeholders("<span>%pll_kind%</span>", {"name": "p0"})
    assert baked == "<span>SC</span>"
    baked_lc = bake_label_placeholders(
        "<span>%pll_kind%</span>",
        {"name": "p0", "pll_kind": "LC"},
    )
    assert baked_lc == "<span>LC</span>"


def test_bake_label_shrinks_div_r_ratio_font_for_long_values() -> None:
    template = (
        '<span style="font-size:11px;line-height:1;">÷</span>'
        '<span style="font-size:8px;line-height:1;">%ratio%</span>'
    )
    baked = bake_label_placeholders(template, {"name": "d0", "ratio": "1234"})
    assert "font-size:7px" in baked.split("÷</span>")[1]
    short = bake_label_placeholders(template, {"name": "d0", "ratio": "2"})
    assert "font-size:9px" in short.split("÷</span>")[1]


def test_bake_label_mux_sel_empty_strips_stub() -> None:
    from drawio_lib.components.label_html import mux_sel_signal_block

    template = mux_sel_signal_block(
        anchor_x=20,
        anchor_y=6,
        design_cell_w=40,
        design_cell_h=80,
    )
    baked = bake_label_placeholders(template, {"name": "m0", "sel": ""})
    assert "%sel%" not in baked
    assert "dc-mux-sel" not in baked


def test_bake_label_mux_sel_replaces_text() -> None:
    from drawio_lib.components.label_html import mux_sel_signal_block

    template = mux_sel_signal_block(
        anchor_x=20,
        anchor_y=6,
        design_cell_w=40,
        design_cell_h=80,
    )
    baked = bake_label_placeholders(template, {"name": "m0", "sel": "clk_sel"})
    assert "clk_sel" in baked
    assert "%sel%" not in baked
    assert "dc-mux-sel" in baked


def test_edge_port_style_uses_library_points() -> None:
    shapes = load_library_shapes(ROOT / "drawio-lib" / "drawclock.xml")
    pll = shapes["pll"]
    from_shape = shapes["from"]
    gate = shapes["gate"]
    style = edge_port_style(from_shape.style, "from", gate.style, "gate")
    right = port_anchors(from_shape.style, "from")["right"]
    assert f"exitX={right[0]}" in style.replace(" ", "")
    left = port_anchors(gate.style, "gate")["left"]
    assert f"entryX={left[0]}" in style.replace(" ", "")
    assert "exitPerimeter=0" in style
    assert "entryPerimeter=0" in style
    assert "edgeStyle=none" in style
    assert "orthogonalEdgeStyle" not in style


def test_finalize_edge_style_adds_perimeter_off() -> None:
    bare = "exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
    fixed = finalize_edge_style(bare)
    assert "exitPerimeter=0" in fixed
    assert "entryPerimeter=0" in fixed


def test_reload_edge_style_disconnects_removed_port() -> None:
    shapes = load_library_shapes(ROOT / "drawio-lib" / "drawclock.xml")
    mux3 = shapes["mux3"]
    mux2 = shapes["mux2"]
    pll = shapes["pll"]
    in2 = port_anchors(mux3.style, "mux3")["in2"]
    outcome = reload_edge_style(
        pll.style,
        pll.style,
        "pll",
        mux3.style,
        mux2.style,
        "mux3",
        f"exitX=1;exitY=0.5;entryX={in2[0]};entryY={in2[1]};edgeStyle=none;html=1;",
    )
    assert outcome.connected is False


def test_reload_edge_style_preserves_orthogonal_routing() -> None:
    shapes = load_library_shapes(ROOT / "drawio-lib" / "drawclock.xml")
    pll = shapes["pll"]
    gate = shapes["gate"]
    right = port_anchors(pll.style, "pll")["right"]
    left = port_anchors(gate.style, "gate")["left"]
    stored = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;"
        "exitX=0.9;exitY=0.5;entryX=0.1;entryY=0.5;strokeColor=#ff0000;"
    )
    outcome = reload_edge_style(
        pll.style,
        pll.style,
        "pll",
        gate.style,
        gate.style,
        "gate",
        stored,
    )
    assert outcome.connected is True
    assert "orthogonalEdgeStyle" in outcome.style
    assert "edgeStyle=none" not in outcome.style
    assert "strokeColor=#ff0000" in outcome.style
    assert f"exitX={right[0]}" in outcome.style.replace(" ", "") or f"exitX={right[0]:g}" in outcome.style
    assert f"entryX={left[0]}" in outcome.style.replace(" ", "") or f"entryX={left[0]:g}" in outcome.style


def test_merge_port_attachment_keeps_routing_keys() -> None:
    stored = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;exitX=1;exitY=0.25;entryX=0;entryY=0.75;"
    merged = merge_port_attachment(stored, (0.8, 0.4), (0.2, 0.6))
    assert "orthogonalEdgeStyle" in merged
    assert "exitX=0.8" in merged
    assert "entryY=0.6" in merged
    assert "exitPerimeter=0" in merged
