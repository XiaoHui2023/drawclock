from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from drawio_layout import LayoutDocument, VertexLayout, layout_to_dict, layout_from_dict
from elk_layout import generate_elk_layout
from layout_preview import _node_annotations, _frequency_table, build_preview_svg
from presentation import ANCHORS, DrawingOptions
from validate_config import validate_config


LIBRARY = Path(__file__).resolve().parents[1] / "drawio-lib/drawclock"
NS = {"s": "http://www.w3.org/2000/svg"}


def annotated_document(options=None):
    return LayoutDocument(1, [
        VertexLayout("short", "a", "gate", 300, 150, 40, 55, "", {"description": "short"}),
        VertexLayout("second", "b", "gate", 300, 400, 80, 55, "", {"description": "a longer description"}),
    ], [], options or DrawingOptions())


def test_default_descriptions_share_a_column_left_edge():
    notes = _node_annotations(annotated_document(), {})
    assert len(notes) == 2
    assert notes[0].x == notes[1].x
    assert 260 < notes[0].x <= 300
    assert notes[0].width == notes[1].width
    assert all(note.align == "left" and note.anchor == "top-left" for note in notes)


@pytest.mark.parametrize("anchor", ANCHORS)
def test_all_description_anchors_stay_in_selected_direction(anchor):
    document = annotated_document(DrawingOptions(description_anchor=anchor))
    document.vertices = document.vertices[:1]
    note, = _node_annotations(document, {})
    assert note.anchor == anchor
    if anchor.startswith("top"):
        assert note.y + note.height < 150
    elif anchor.startswith("bottom"):
        assert note.y > 205
    elif anchor == "left":
        assert note.x + note.width < 300
    else:
        assert note.x > 340


def test_node_overrides_are_independent_and_offsets_are_actual_translations():
    base = annotated_document()
    before = _node_annotations(base, {})[0]
    shifted = annotated_document(DrawingOptions(description_align="center", description_offset_x=13, description_offset_y=-17))
    after = _node_annotations(shifted, {})[0]
    assert (after.x, after.y) == (before.x + 13, before.y - 17)
    shifted.vertices[0].object_attrs.update(description_align="right", description_offset_x="0")
    override = _node_annotations(shifted, {})[0]
    assert override.align == "right" and override.x == before.x
    assert override.y == before.y - 17
    root = ET.fromstring(build_preview_svg(shifted))
    text = root.find(".//s:g[@class='node-annotation'][@data-node-id='short']/s:text", NS)
    assert text.get("text-anchor") == "end"


@pytest.mark.parametrize("values", [
    {"description_align": "start"}, {"description_anchor": "center"},
    {"description_offset_x": True}, {"description_offset_y": float("nan")},
    {"description_offset_x": float("inf")}, {"horizontal_spacing": -1},
    {"horizontal_spacing": False}, {"frequency_headers": "one"},
    {"description_offset_x": 10 ** 400},
])
def test_invalid_global_options_fail_early(values):
    with pytest.raises(ValueError):
        DrawingOptions(**values)


@pytest.mark.parametrize("values", [
    {"frequencies": "100 MHz"}, {"frequencies": [True]},
    {"frequencies": [float("inf")]}, {"frequencies": [["100"]]},
    {"frequencies": [1], "func_freq": 1}, {"description_offset_x": True},
    {"description_anchor": "invalid"}, {"description_align": "invalid"},
])
def test_invalid_node_options_fail_config_validation(values):
    with pytest.raises(ValueError):
        validate_config({"node": {"kind": "gate", **values}}, library_path=LIBRARY)


def frequency_config():
    return {"root": {"kind": "gate"}, "sink": {"kind": "clock", "source": "root",
            "frequencies": ["100\nMHz", "50 MHz", "10 MHz", "1 MHz"]}}


@pytest.mark.parametrize("alignment,anchor", [("left", "start"), ("center", "middle"), ("right", "end")])
def test_array_frequency_table_multiline_alignment_and_widths(alignment, anchor):
    options = DrawingOptions(frequency_align=alignment, frequency_headers=("Very long\nheading", "B", "C", "D"))
    document, _ = generate_elk_layout(frequency_config(), library_path=LIBRARY, options=options)
    root = ET.fromstring(build_preview_svg(document))
    headings = root.findall(".//s:text[@class='frequency-heading']", NS)
    values = root.findall(".//s:text[@class='frequency-value']", NS)
    assert len(headings) == len(values) == 4
    assert [value.get("aria-label") for value in values] == frequency_config()["sink"]["frequencies"]
    assert [value.get("data-frequency-field") for value in values] == [f"frequencies[{i}]" for i in range(4)]
    assert all(value.get("text-anchor") == anchor for value in headings + values)
    assert [span.text for span in headings[0].findall("s:tspan", NS)] == ["Very long", "heading"]
    table = _frequency_table(document)
    assert table.column_widths[0] > table.column_widths[1]
    for index in range(3):
        assert table.column_centers[index + 1] - table.column_centers[index] >= (table.column_widths[index] + table.column_widths[index + 1]) / 2 + 19.99
    assert layout_from_dict(layout_to_dict(document)).options == options


def test_frequency_header_count_mismatch_is_not_silently_dropped():
    document, _ = generate_elk_layout(frequency_config(), library_path=LIBRARY, options=DrawingOptions(frequency_headers=("a",)))
    with pytest.raises(ValueError, match="count must match"):
        build_preview_svg(document)


def test_horizontal_spacing_survives_routing_compaction():
    gaps = []
    for spacing in (100.0, 240.0):
        document, _ = generate_elk_layout(frequency_config(), library_path=LIBRARY, options=DrawingOptions(horizontal_spacing=spacing))
        nodes = {v.name: v for v in document.vertices}
        gap = nodes["sink"].x - nodes["root"].x - nodes["root"].width
        assert gap >= spacing
        gaps.append(gap)
    assert gaps[1] > gaps[0]


def test_reserved_description_space_preserves_serialized_orthogonal_axes():
    config = {"root": {"kind": "gate", "description": "Root description"},
              "sink": {"kind": "clock", "source": "root", "description": "Sink description"}}
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    root = ET.fromstring(build_preview_svg(document))
    routes = root.findall("s:polyline[@class='edge']", NS)
    assert routes
    for route in routes:
        points = [tuple(map(float, point.split(","))) for point in route.get("points").split()]
        for start, end in zip(points, points[1:]):
            assert start[0] == end[0] or start[1] == end[1], (start, end)
