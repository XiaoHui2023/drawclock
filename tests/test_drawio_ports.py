from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drawio_library import (  # noqa: E402
    bake_label_placeholders,
    load_library_shapes,
    reload_object_attrs,
)
from drawio_ports import edge_port_style, finalize_edge_style, port_anchors  # noqa: E402


def test_bake_label_replaces_name_and_freq() -> None:
    baked = bake_label_placeholders(
        "<div>%name%</div><span>(%freq%hz)</span>",
        {"name": "clk0", "freq": "100"},
    )
    assert "clk0" in baked
    assert "(100hz)" in baked
    assert "%" not in baked


def test_reload_object_attrs_adds_pll_kind_default_for_legacy_pll() -> None:
    lib = ROOT / "drawio-lib" / "drawclock.xml"
    out = reload_object_attrs("pll", {"name": "pll0"}, library_path=lib)
    assert out["pll_kind"] == "SC"
    assert "%pll_kind%" not in out["label"]
    assert "SC</span>" in out["label"] or ">SC<" in out["label"]
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


def test_edge_port_style_uses_library_points() -> None:
    shapes = load_library_shapes(ROOT / "drawio-lib" / "drawclock.xml")
    pll = shapes["pll"]
    wire = shapes["wire"]
    style = edge_port_style(pll.style, "pll", wire.style, "wire")
    right = port_anchors(pll.style, "pll")["right"]
    assert f"exitX={right[0]}" in style.replace(" ", "")
    left = port_anchors(wire.style, "wire")["left"]
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
