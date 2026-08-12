from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_layout import EdgeLayout, LayoutDocument, VertexLayout
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
    viewport_x, viewport_y = (float(value) for value in foreign.groups())
    content = re.search(
        r'style="position:relative;left:([-\d.]+)px;top:([-\d.]+)px;', svg
    )
    assert content is not None
    content_dx, content_dy = (float(value) for value in content.groups())

    drift_x, drift_y = _visible_drift(
        content_x=viewport_x + content_dx,
        content_y=viewport_y + content_dy,
        graphic_dx=graphic_dx,
        graphic_dy=graphic_dy,
        geometry_x=vertex.x,
        geometry_y=vertex.y,
    )
    assert drift_x == pytest.approx(0.0, abs=1e-9)
    assert drift_y == pytest.approx(0.0, abs=1e-9)
    assert viewport_x == vertex.x
    assert viewport_y == vertex.y


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


def test_edge_endpoint_serialization_preserves_clock_contact_coordinate() -> None:
    gate = next(spec.module for spec in ALL if spec.module.TITLE == "gate")
    clock = next(spec.module for spec in ALL if spec.module.TITLE == "clock")
    gate_port = gate._parse_points(gate.cell_style())[-1]
    clock_port = clock._parse_points(clock.cell_style())[0]
    source = VertexLayout(
        name="gate", cell_id="v1", drawclock_type="gate",
        x=1225.78, y=88.0016, width=gate.W, height=gate.H,
        style=gate.cell_style(), object_attrs={"label": gate.label_html()},
    )
    target = VertexLayout(
        name="clock", cell_id="v2", drawclock_type="clock",
        x=1405.78, y=82.0016, width=clock.W, height=clock.H,
        style=clock.cell_style(), object_attrs={"label": clock.label_html()},
    )
    edge = EdgeLayout(
        cell_id="e1", source_id="v1", target_id="v2",
        style=(
            f"exitX={gate_port[0]};exitY={gate_port[1]};"
            f"entryX={clock_port[0]};entryY={clock_port[1]};"
        ),
        waypoints=(),
    )
    svg = build_preview_svg(
        LayoutDocument(version=1, vertices=[source, target], edges=[edge])
    )
    edge_points = re.search(r'<polyline class="edge" points="[^"]+ ([^"]+)"', svg)
    assert edge_points is not None
    actual_x, actual_y = (float(value) for value in edge_points.group(1).split(","))

    assert actual_x == target.x + target.width * clock_port[0]
    assert actual_y == target.y + target.height * clock_port[1]
