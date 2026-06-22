from __future__ import annotations

import importlib
import re
import sys
from math import isclose
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_lib.components.label_overflow import (
    DRAWIO_HTML_LABEL_OFFSET_X,
    DRAWIO_HTML_LABEL_OFFSET_Y,
    graphic_layer_pin_css,
)
from drawio_lib.components.registry import ALL
from drawio_lib.components.simple_shapes import (
    DTO_CHIP_LEFT,
    DTO_CHIP_W,
    div_hex_side_port_x,
    dto_chip_port_cells,
)


def _lead_ys(svg: str, x: float, tol: float = 1.5) -> list[float]:
    ys: list[float] = []
    for pattern in (
        r'<line[^>]+x1="([^"]+)"[^>]+y1="([^"]+)"[^>]+x2="([^"]+)"[^>]+y2="([^"]+)"',
        r'<line[^>]+y1="([^"]+)"[^>]+x1="([^"]+)"[^>]+y2="([^"]+)"[^>]+x2="([^"]+)"',
    ):
        for m in re.finditer(pattern, svg):
            if pattern.startswith(r"<line[^>]+x1"):
                x1, y1, x2, y2 = (float(v) for v in m.groups())
            else:
                y1, x1, y2, x2 = (float(v) for v in m.groups())
            for y in (y1, y2):
                if min(x1, x2) - tol <= x <= max(x1, x2) + tol:
                    ys.append(y)
    return ys


def _port_cys(preview: str) -> list[tuple[float, float]]:
    return [
        (float(m.group(1)), float(m.group(2)))
        for m in re.finditer(r'<circle cx="([^"]+)" cy="([^"]+)" r="2\.5"', preview)
    ]


@pytest.mark.parametrize("spec", ALL, ids=lambda s: s.module.TITLE)
def test_preview_stub_y_matches_graphic_lead(spec) -> None:
    mod = spec.module
    if not hasattr(mod, "preview_svg"):
        pytest.skip("no preview_svg")
    preview = mod.preview_svg()
    body = ""
    if hasattr(mod, "G") and hasattr(mod, "body_svg"):
        body = mod.body_svg(mod.G)
    elif hasattr(mod, "_body_g"):
        body = mod.body_svg(mod._body_g)  # type: ignore[attr-defined]

    for cx, cy in _port_cys(preview):
        leads = _lead_ys(body + preview, cx)
        if not leads:
            continue
        best = min(leads, key=lambda y: abs(y - cy))
        assert abs(cy - best) <= 0.6, (
            f"{mod.TITLE}: port ({cx:.1f},{cy:.1f}) vs lead y={best:.1f}"
        )


def test_label_html_pins_graphic_layer_with_drawio_offset() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    pin = graphic_layer_pin_css(view_w=gate.W, view_h=gate.H)
    assert pin in gate.label_html()
    assert f"left:{-DRAWIO_HTML_LABEL_OFFSET_X}px" in pin
    assert f"top:{-DRAWIO_HTML_LABEL_OFFSET_Y}px" in pin


def test_drawio_export_label_offset_is_stable() -> None:
    """Regression: draw.io html=1 wrapper offset used to misalign ports vs graphics."""
    svg_path = ROOT / "test.drawio.svg"
    if not svg_path.is_file():
        pytest.skip("test.drawio.svg not present")
    text = svg_path.read_text(encoding="utf-8")
    rects = re.findall(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"[^/]*/>',
        text,
    )
    pads = re.findall(r"padding-top: (\d+)px; margin-left: (\d+)px", text)
    dys = {int(pt) - int(ry) for (rx, ry, rw, rh), (pt, ml) in zip(rects, pads, strict=False)}
    dxs = {int(ml) - int(rx) for (rx, ry, rw, rh), (pt, ml) in zip(rects, pads, strict=False)}
    assert DRAWIO_HTML_LABEL_OFFSET_Y in dys
    assert DRAWIO_HTML_LABEL_OFFSET_X in dxs


@pytest.mark.parametrize("module_name", ["dto", "dto_n"])
def test_dto_ports_on_chip_outline(module_name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    mid = mod.G.body_mid_y
    left_port, right_port = dto_chip_port_cells(mid_y=mid, pad=0)
    left_x, right_x = left_port[0], right_port[0]
    pts = mod._parse_points(mod.cell_style())
    assert len(pts) == 2
    assert isclose(pts[0][0], left_x / mod.W, abs_tol=0.002)
    assert isclose(pts[1][0], right_x / mod.W, abs_tol=0.002)
    assert isclose(pts[0][1], mid / mod.H, abs_tol=0.002)
    assert isclose(pts[1][1], mid / mod.H, abs_tol=0.002)

    preview = mod.preview_svg()
    circles = _port_cys(preview)
    assert isclose(circles[0][0], left_x, abs_tol=0.6)
    assert isclose(circles[1][0], right_x, abs_tol=0.6)

    rect = re.search(
        rf'<rect x="{DTO_CHIP_LEFT}" y="\d+" width="{DTO_CHIP_W}"',
        preview,
    )
    assert rect is not None


@pytest.mark.parametrize("module_name", ["div", "div2", "div_n"])
def test_div_ports_on_hex_outline(module_name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    mid = mod.G.body_mid_y
    left_x = div_hex_side_port_x("left")
    right_x = div_hex_side_port_x("right")
    pts = mod._parse_points(mod.cell_style())
    assert len(pts) == 2
    assert isclose(pts[0][0], left_x / mod.W, abs_tol=0.002)
    assert isclose(pts[1][0], right_x / mod.W, abs_tol=0.002)

    preview = mod.preview_svg()
    circles = _port_cys(preview)
    assert isclose(circles[0][0], left_x, abs_tol=0.6)
    assert isclose(circles[1][0], right_x, abs_tol=0.6)
