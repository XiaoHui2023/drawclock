from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_layout import LayoutDocument, VertexLayout
from layout_preview import (
    HTML_LABEL_CONTENT_OFFSET_X,
    HTML_LABEL_CONTENT_OFFSET_Y,
    build_preview_svg,
)
from drawio_lib.components.label_overflow import (
    DRAWIO_HTML_LABEL_OFFSET_X,
    DRAWIO_HTML_LABEL_OFFSET_Y,
)
from drawio_lib.components.registry import ALL


def _css_offset(label: str) -> tuple[float, float]:
    match = re.search(
        r"position:absolute;left:([-\d.]+)px;top:([-\d.]+)px;",
        label,
    )
    assert match is not None, "component label is missing its pinned graphic layer"
    return float(match.group(1)), float(match.group(2))


def _visible_drift(
    *, content_x: float, content_y: float, graphic_dx: float, graphic_dy: float,
    geometry_x: float, geometry_y: float,
) -> tuple[float, float]:
    return (
        content_x + graphic_dx - geometry_x,
        content_y + graphic_dy - geometry_y,
    )


@pytest.mark.parametrize("spec", ALL, ids=lambda spec: spec.module.TITLE)
def test_native_preview_visible_graphic_origin_equals_geometry_origin(spec) -> None:
    """The final compositor, not just style points, must have zero net drift."""
    mod = spec.module
    label = mod.label_html()
    graphic_dx, graphic_dy = _css_offset(label)
    vertex = VertexLayout(
        name=mod.TITLE,
        cell_id="v1",
        drawclock_type=mod.TITLE,
        x=113.25,
        y=207.5,
        width=mod.W,
        height=mod.H,
        style=mod.cell_style(),
        object_attrs={"label": label},
    )
    svg = build_preview_svg(LayoutDocument(version=1, vertices=[vertex], edges=[]))
    foreign = re.search(r'<foreignObject x="([^\"]+)" y="([^\"]+)"', svg)
    assert foreign is not None
    content_x, content_y = (float(value) for value in foreign.groups())

    drift_x, drift_y = _visible_drift(
        content_x=content_x,
        content_y=content_y,
        graphic_dx=graphic_dx,
        graphic_dy=graphic_dy,
        geometry_x=vertex.x,
        geometry_y=vertex.y,
    )
    assert drift_x == pytest.approx(0.0, abs=1e-9)
    assert drift_y == pytest.approx(0.0, abs=1e-9)


def test_native_preview_outer_and_inner_offsets_are_exact_inverses() -> None:
    """Fault-injection sentinel: either side drifting must fail this gate."""
    assert HTML_LABEL_CONTENT_OFFSET_X == DRAWIO_HTML_LABEL_OFFSET_X
    assert HTML_LABEL_CONTENT_OFFSET_Y == DRAWIO_HTML_LABEL_OFFSET_Y


def test_fault_injection_uncompensated_compositor_reports_visible_drift() -> None:
    """Historical failure replay: style ports stay correct while graphics drift."""
    drift = _visible_drift(
        content_x=100.0,
        content_y=200.0,
        graphic_dx=-DRAWIO_HTML_LABEL_OFFSET_X,
        graphic_dy=-DRAWIO_HTML_LABEL_OFFSET_Y,
        geometry_x=100.0,
        geometry_y=200.0,
    )
    assert drift == (-2.0, -7.0)
