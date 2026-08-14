from __future__ import annotations

from pathlib import Path

from drawio_library import bake_label_placeholders, load_library_shapes
from drawio_ports import abs_port_xy, infer_port_from_attachment, port_anchors


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"


def test_bake_label_replaces_name_and_defaults() -> None:
    baked = bake_label_placeholders(
        "<div>%name% %pll_kind%</div>",
        {"name": "pll0"},
    )
    assert baked == "<div>pll0 SC</div>"


def test_port_coordinates_come_from_supplied_shape_style() -> None:
    gate = load_library_shapes(LIBRARY)["gate"]
    anchors = port_anchors(gate.style, "gate")
    assert "left" in anchors and "right" in anchors
    assert abs_port_xy(10, 20, gate.w, gate.h, gate.style, "gate", "right") == (
        10 + gate.w * anchors["right"][0],
        20 + gate.h * anchors["right"][1],
    )


def test_attachment_resolves_to_library_port() -> None:
    mux = load_library_shapes(LIBRARY)["mux2"]
    anchor = port_anchors(mux.style, "mux2")["in1"]
    style = f"entryX={anchor[0]};entryY={anchor[1]};"
    assert infer_port_from_attachment(mux.style, style, end="entry") == "in1"
