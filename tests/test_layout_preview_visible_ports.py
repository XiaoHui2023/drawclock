from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
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
    _estimated_text_width,
    _node_annotations,
    _arc_crossings,
    _wrap_annotation,
    build_preview_svg,
)
from svg_native import render_native_label, validate_static_svg
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
    graphic = re.search(
        r'<svg class="component-graphic" x="([^\"]+)" y="([^\"]+)"', svg
    )
    assert graphic is not None
    graphic_x, graphic_y = (float(value) for value in graphic.groups())
    drift_x, drift_y = _visible_drift(
        content_x=graphic_x,
        content_y=graphic_y,
        graphic_dx=0.0,
        graphic_dy=0.0,
        geometry_x=vertex.x,
        geometry_y=vertex.y,
    )
    assert drift_x == pytest.approx(0.0, abs=1e-9)
    assert drift_y == pytest.approx(0.0, abs=1e-9)
    assert graphic_x == vertex.x
    assert graphic_y == vertex.y
    assert "foreignObject" not in svg
    validate_static_svg(svg)


def test_preview_omits_the_input_filename_title() -> None:
    mod = ALL[0].module
    vertex = VertexLayout(
        name=mod.TITLE, cell_id="v1", drawclock_type=mod.TITLE,
        x=20, y=30, width=mod.W, height=mod.H, style=mod.cell_style(),
        object_attrs={"label": mod.label_html()},
    )
    svg = build_preview_svg(
        LayoutDocument(version=1, vertices=[vertex], edges=[]),
        title="input-file-stem",
    )
    assert "input-file-stem" not in svg


def test_description_renders_once_as_safe_plain_text_annotation() -> None:
    primary = VertexLayout(
        name="shared", cell_id="v1", drawclock_type="source",
        x=20, y=30, width=80, height=40, style="",
        object_attrs={
            "description": "公共参考<&>\n仅用于测试",
            "description_color": "rgba(255, 0, 128, 50%)",
        },
    )
    alias = VertexLayout(
        name="shared__alias", logical_name="shared", cell_id="v2",
        drawclock_type="source", x=20, y=100, width=80, height=40,
        style="", object_attrs={
            "description": "公共参考<&>\n仅用于测试",
            "description_color": "rgba(255, 0, 128, 50%)",
        },
    )

    svg = build_preview_svg(
        LayoutDocument(version=1, vertices=[primary, alias], edges=[])
    )

    assert svg.count('class="node-annotation" data-node-id="shared"') == 1
    assert 'data-description-color="#ff008080"' in svg
    assert svg.count('fill="#ff008080"') == 2
    assert 'node-annotation-link' not in svg
    annotation = svg.split('<g class="node-annotation"', 1)[1].split('</g>', 1)[0]
    assert '<path' not in annotation
    assert '<rect' not in annotation
    assert "stroke-dasharray" not in svg
    assert "公共参考&lt;&amp;&gt;" in svg
    assert "<foreignObject" not in svg
    validate_static_svg(svg)


def test_description_uses_the_stable_default_color() -> None:
    vertex = VertexLayout(
        name="source", cell_id="v1", drawclock_type="source",
        x=20, y=30, width=80, height=40, style="",
        object_attrs={"description": "default color"},
    )
    svg = build_preview_svg(LayoutDocument(version=1, vertices=[vertex], edges=[]))
    assert 'data-description-color="#4b5563"' in svg
    assert 'fill="#4b5563"' in svg


def test_crossing_renderer_treats_physical_aliases_as_one_logical_net() -> None:
    primary = VertexLayout(
        name="shared", cell_id="v1", drawclock_type="from",
        x=0, y=0, width=10, height=10, style="",
    )
    alias = VertexLayout(
        name="shared__alias", logical_name="shared", cell_id="v2",
        drawclock_type="from", x=0, y=20, width=10, height=10, style="",
    )
    left_target = VertexLayout(
        name="left_target", cell_id="v3", drawclock_type="clock",
        x=100, y=0, width=10, height=10, style="",
    )
    lower_target = VertexLayout(
        name="lower_target", cell_id="v4", drawclock_type="clock",
        x=100, y=20, width=10, height=10, style="",
    )
    document = LayoutDocument(
        version=1,
        vertices=[primary, alias, left_target, lower_target],
        edges=[
            EdgeLayout("e1", "v1", "v3", ""),
            EdgeLayout("e2", "v2", "v4", ""),
        ],
    )
    crossings = _arc_crossings(
        document,
        {
            "e1": [(0.0, 50.0), (100.0, 50.0)],
            "e2": [(50.0, 0.0), (50.0, 100.0)],
        },
    )
    assert crossings == {}


def test_direct_near_axis_route_snaps_at_serialization_boundary() -> None:
    source = VertexLayout(
        name="root", cell_id="v1", drawclock_type="source",
        x=0, y=0, width=10, height=10,
        style="exitX=1;exitY=0.50025;", object_attrs={},
    )
    target = VertexLayout(
        name="target", cell_id="v2", drawclock_type="gate",
        x=50, y=0, width=10, height=10,
        style="entryX=0;entryY=0.49975;", object_attrs={},
    )
    edge = EdgeLayout(
        "e1", "v1", "v2",
        "exitX=1;exitY=0.50025;entryX=0;entryY=0.49975;",
    )
    svg = build_preview_svg(
        LayoutDocument(version=1, vertices=[source, target], edges=[edge])
    )
    match = re.search(r'<polyline class="edge" points="([^"]+)"', svg)
    assert match is not None
    points = [tuple(map(float, item.split(","))) for item in match.group(1).split()]
    assert len(points) == 3
    assert points[0][1] == points[1][1]
    assert points[1][0] == points[2][0]
    assert points[2] == pytest.approx((50.0, 4.9975))


def test_annotation_wrap_preserves_empty_and_trailing_lines() -> None:
    assert _wrap_annotation("短") == ("短",)
    assert _wrap_annotation("一\r\n\r\n三\r") == ("一", "", "三", "")
    long_text = "A_very_long_unbroken_ASCII_annotation_" * 4
    lines = _wrap_annotation(long_text)
    assert "".join(lines) == long_text
    assert len(lines) > 1
    assert all(_estimated_text_width(line) <= 230.0 for line in lines)


def test_annotation_placement_fails_closed_when_no_safe_candidate() -> None:
    vertex = VertexLayout(
        name="blocked", cell_id="v1", drawclock_type="source",
        x=20, y=30, width=80, height=40, style="",
        object_attrs={"description": "必须失败"},
    )
    document = LayoutDocument(version=1, vertices=[vertex], edges=[])
    with pytest.raises(ValueError, match="no collision-free candidate: blocked"):
        _node_annotations(document, {}, reserved=((-500, -500, 500, 500),))


@pytest.mark.parametrize("spec", ALL, ids=lambda spec: spec.module.TITLE)
def test_every_component_label_has_a_portable_native_svg_render(spec) -> None:
    mod = spec.module
    rendered = render_native_label(
        mod.label_html(),
        x=10.0,
        y=20.0,
        width=mod.W,
        height=mod.H,
        content_offset_x=HTML_LABEL_CONTENT_OFFSET_X,
        content_offset_y=HTML_LABEL_CONTENT_OFFSET_Y,
    )
    assert 'class="component-graphic"' in rendered
    assert "foreignObject" not in rendered
    assert "http://www.w3.org/1999/xhtml" not in rendered


def test_static_svg_oracle_rejects_historical_foreign_object_escape() -> None:
    broken = (
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
        '<foreignObject width="10" height="10">'
        '<xhtml:div>hidden in librsvg</xhtml:div>'
        '</foreignObject></svg>'
    )
    with pytest.raises(ValueError, match="非静态通用 SVG"):
        validate_static_svg(broken)


@pytest.mark.parametrize(
    "payload",
    [
        '<image href="https://example.invalid/component.svg"/>',
        '<style>@import url(https://example.invalid/style.css);</style>',
        '<rect style="fill:url(https://example.invalid/fill.svg)"/>',
        '<rect onclick="alert(1)"/>',
    ],
)
def test_static_svg_oracle_rejects_external_or_active_content(payload: str) -> None:
    broken = f'<svg xmlns="http://www.w3.org/2000/svg">{payload}</svg>'
    with pytest.raises(ValueError):
        validate_static_svg(broken)


def test_label_converter_rejects_unhandled_geometry_css() -> None:
    label = (
        '<div style="position:relative;width:40px;height:40px;right:2px">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"/>'
        '</div>'
    )
    with pytest.raises(ValueError, match="不兼容的 HTML 样式: right"):
        render_native_label(
            label, x=0, y=0, width=40, height=40,
            content_offset_x=2, content_offset_y=7,
        )


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


def test_preview_viewbox_contains_routes_below_all_nodes() -> None:
    gate = next(spec.module for spec in ALL if spec.module.TITLE == "gate")
    source = VertexLayout(
        name="source", cell_id="v1", drawclock_type="gate",
        x=100.0, y=100.0, width=gate.W, height=gate.H,
        style=gate.cell_style(), object_attrs={"label": gate.label_html()},
    )
    target = VertexLayout(
        name="target", cell_id="v2", drawclock_type="gate",
        x=300.0, y=100.0, width=gate.W, height=gate.H,
        style=gate.cell_style(), object_attrs={"label": gate.label_html()},
    )
    edge = EdgeLayout(
        cell_id="e1", source_id="v1", target_id="v2",
        style="exitX=1;exitY=0.5;entryX=0;entryY=0.5;",
        waypoints=((180.0, 125.0), (180.0, 900.0), (260.0, 900.0), (260.0, 125.0)),
    )

    svg = build_preview_svg(
        LayoutDocument(version=1, vertices=[source, target], edges=[edge])
    )
    viewbox = re.search(r'viewBox="([^"]+)"', svg)
    assert viewbox is not None
    _, min_y, _, height = (float(value) for value in viewbox.group(1).split())
    assert min_y + height >= 945.0


def test_terminal_frequency_table_has_one_aligned_row_per_sink() -> None:
    style = "points=[[0,0.5,0,0,0],[1,0.5,0,0,0]];"
    vertices = [
        VertexLayout("root", "v0", "generic", 0, 80, 40, 40, style),
        VertexLayout(
            "clk_a", "v1", "generic", 200, 20, 40, 40, style,
            object_attrs={
                "func_freq": "800 MHz", "scan_freq": "50 MHz",
                "bist_freq": "100 MHz",
            },
        ),
        VertexLayout(
            "clk_b", "v2", "generic", 200, 100, 40, 40, style,
            object_attrs={"func_freq": "400 MHz", "bist_freq": "80 MHz"},
        ),
        VertexLayout(
            "clk_c", "v3", "generic", 200, 180, 40, 40, style,
            object_attrs={},
        ),
    ]
    edge_style = "exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
    edges = [
        EdgeLayout(f"e{index}", "v0", f"v{index}", edge_style)
        for index in range(1, 4)
    ]

    svg = build_preview_svg(
        LayoutDocument(version=1, vertices=vertices, edges=edges)
    )
    root = ET.fromstring(svg)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    headings = [
        element for element in root.iter()
        if element.attrib.get("class") == "frequency-heading"
    ]
    values = root.findall(".//svg:text[@class='frequency-value']", ns)

    assert [heading.attrib.get("aria-label", heading.text) for heading in headings] == [
        "工作频率", "SCAN", "BIST",
    ]
    assert [heading.attrib["data-frequency-field"] for heading in headings] == [
        "func_freq", "scan_freq", "bist_freq",
    ]
    assert all(heading.attrib["fill"] == "#20252b" for heading in headings)
    assert headings[0].attrib["data-heading-render"] == "outline"
    assert len(headings[0].findall("svg:path", ns)) == 4
    assert all(value.attrib["fill"] == "#d02020" for value in values)
    assert {(value.attrib["data-node-id"], value.text) for value in values} == {
        ("clk_a", "800 MHz"), ("clk_a", "50 MHz"),
        ("clk_a", "100 MHz"), ("clk_b", "400 MHz"),
        ("clk_b", "80 MHz"),
    }
    row_y = {
        node: {float(value.attrib["y"]) for value in values
               if value.attrib["data-node-id"] == node}
        for node in ("clk_a", "clk_b")
    }
    assert all(len(ys) == 1 for ys in row_y.values())
    assert row_y["clk_a"] != row_y["clk_b"]
    assert all(float(value.attrib["x"]) > 240 for value in values)

    min_x, min_y, width, height = (
        float(value) for value in root.attrib["viewBox"].split()
    )
    heading_centers = [
        float(heading.attrib.get("x", headings[index].attrib.get("x", 0)))
        for index, heading in enumerate(headings[1:], 1)
    ]
    assert min_x + width > max(heading_centers)
    assert min_y < min(float(heading.attrib["y"]) for heading in headings[1:])
    assert min_y + height > max(float(value.attrib["y"]) for value in values)


def test_frequency_text_is_xml_escaped_and_long_value_expands_canvas() -> None:
    vertex = VertexLayout(
        "clk", "v1", "generic", 10, 20, 40, 40,
        "points=[[0,0.5,0,0,0]];",
        object_attrs={"func_freq": "A&B <nominal> " + "9" * 80},
    )
    svg = build_preview_svg(LayoutDocument(version=1, vertices=[vertex], edges=[]))
    root = ET.fromstring(svg)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    value = root.find(".//svg:text[@class='frequency-value']", ns)
    assert value is not None
    assert value.text == "A&B <nominal> " + "9" * 80
    assert "A&amp;B &lt;nominal&gt;" in svg
    assert float(root.attrib["width"]) > 700


@pytest.mark.parametrize(
    "attrs,expected_fields,expected_labels",
    [
        ({"func_freq": "100 MHz"}, ["func_freq"], ["工作频率"]),
        ({"scan_freq": "20 MHz"}, ["scan_freq"], ["SCAN"]),
        ({"bist_freq": "10 MHz"}, ["bist_freq"], ["BIST"]),
        (
            {"scan_freq": "20 MHz", "bist_freq": "10 MHz"},
            ["scan_freq", "bist_freq"],
            ["SCAN", "BIST"],
        ),
        (
            {"func_freq": "100 MHz", "bist_freq": "10 MHz"},
            ["func_freq", "bist_freq"],
            ["工作频率", "BIST"],
        ),
    ],
)
def test_frequency_table_only_renders_nonempty_columns(
    attrs: dict[str, str],
    expected_fields: list[str],
    expected_labels: list[str],
) -> None:
    vertex = VertexLayout(
        "clk", "v1", "generic", 10, 20, 40, 40,
        "points=[[0,0.5,0,0,0]];", object_attrs=attrs,
    )
    root = ET.fromstring(build_preview_svg(
        LayoutDocument(version=1, vertices=[vertex], edges=[])
    ))
    headings = [
        element for element in root.iter()
        if element.attrib.get("class") == "frequency-heading"
    ]
    assert [element.attrib["data-frequency-field"] for element in headings] == expected_fields
    assert [element.attrib.get("aria-label", element.text) for element in headings] == expected_labels
    values = [
        element for element in root.iter()
        if element.attrib.get("class") == "frequency-value"
    ]
    assert [element.attrib["data-frequency-field"] for element in values] == expected_fields


def test_frequency_table_disappears_when_all_terminal_values_are_empty() -> None:
    style = "points=[[0,0.5,0,0,0]];"
    empty = VertexLayout(
        "clk", "v1", "generic", 10, 20, 40, 40, style,
        object_attrs={"func_freq": "", "scan_freq": "", "bist_freq": ""},
    )
    populated = VertexLayout(
        "clk", "v1", "generic", 10, 20, 40, 40, style,
        object_attrs={"bist_freq": "10 MHz"},
    )
    empty_root = ET.fromstring(build_preview_svg(
        LayoutDocument(version=1, vertices=[empty], edges=[])
    ))
    populated_root = ET.fromstring(build_preview_svg(
        LayoutDocument(version=1, vertices=[populated], edges=[])
    ))
    assert not any(
        element.attrib.get("class") == "frequency-table"
        for element in empty_root.iter()
    )
    assert not any(
        element.attrib.get("class") in {"frequency-heading", "frequency-value"}
        for element in empty_root.iter()
    )
    assert float(empty_root.attrib["width"]) < float(populated_root.attrib["width"])


def test_preview_default_draws_real_arc_bridge_at_crossing() -> None:
    style = "points=[[0,0.5,0,0,0],[1,0.5,0,0,0]];"
    vertices = [
        VertexLayout("left", "v1", "x", 0, 80, 40, 40, style),
        VertexLayout("right", "v2", "x", 360, 80, 40, 40, style),
        VertexLayout("top", "v3", "x", 100, 0, 40, 40, style),
        VertexLayout("bottom", "v4", "x", 260, 180, 40, 40, style),
    ]
    edge_style = "exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
    edges = [
        EdgeLayout("e1", "v1", "v2", edge_style),
        EdgeLayout(
            "e2", "v3", "v4", edge_style,
            waypoints=((200, 20), (200, 200)),
        ),
    ]
    document = LayoutDocument(version=1, vertices=vertices, edges=edges)

    arc_svg = build_preview_svg(document)
    gap_svg = build_preview_svg(document, crossing_style="gap")

    assert re.search(r'<path class="edge" d="[^"]* A 4 4 ', arc_svg)
    assert 'class="edge-gap"' not in arc_svg
    assert 'class="edge-gap"' in gap_svg


def test_arc_bridge_uses_final_visible_coordinate_precision() -> None:
    style = "points=[[0,0.5,0,0,0],[1,0.5,0,0,0]];"
    vertices = [
        VertexLayout("left", "v1", "x", 0, 80.00000000000003, 40, 40, style),
        VertexLayout("right", "v2", "x", 360, 80, 40, 40, style),
        VertexLayout("top", "v3", "x", 100, 0, 40, 40, style),
        VertexLayout("bottom", "v4", "x", 260, 180, 40, 40, style),
    ]
    edge_style = "exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
    document = LayoutDocument(
        version=1, vertices=vertices,
        edges=[
            EdgeLayout("e1", "v1", "v2", edge_style),
            EdgeLayout(
                "e2", "v3", "v4", edge_style,
                waypoints=((200, 20), (200, 200)),
            ),
        ],
    )

    svg = build_preview_svg(document)

    assert re.search(r'<path class="edge" d="[^\"]* A 4 4 ', svg)
