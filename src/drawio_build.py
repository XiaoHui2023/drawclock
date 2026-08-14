from __future__ import annotations

from drawio_layout import EdgeLayout, LayoutDocument, VertexLayout
from drawio_library import (
    LABEL_PLACEHOLDER_RE,
    bake_label_placeholders,
    canonical_object_attrs,
    canonical_vertex_style,
)
from drawio_ports import resolve_edge_style
from drawio_graph import edge_attachment


def xml_attr(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_drawio_xml(layout: LayoutDocument) -> str:
    lines = [
        "<mxfile>",
        "  <diagram>",
        "    <mxGraphModel>",
        "      <root>",
        '        <mxCell id="0"/>',
        '        <mxCell id="1" parent="0"/>',
    ]
    by_id = {vertex.cell_id: vertex for vertex in layout.vertices}
    for vertex in layout.vertices:
        lines.append("        " + _vertex_xml(vertex))
    for index, (x, y) in enumerate(junction_points(layout), 1):
        lines.append("        " + _junction_xml(index, x, y))
    for edge in layout.edges:
        lines.append("        " + _edge_xml(edge, by_id))
    lines.extend(
        [
            "      </root>",
            "    </mxGraphModel>",
            "  </diagram>",
            "</mxfile>",
        ]
    )
    return "\n".join(lines) + "\n"


def junction_points(layout: LayoutDocument) -> list[tuple[float, float]]:
    """Find same-source-port shared-prefix splits for decorative junction dots."""
    by_id = {vertex.cell_id: vertex for vertex in layout.vertices}
    groups: dict[tuple[str, tuple[float, float]], list[list[tuple[float, float]]]] = {}
    for edge in layout.edges:
        source = by_id.get(edge.source_id)
        target = by_id.get(edge.target_id)
        if source is None or target is None:
            continue
        exit_xy = edge_attachment(edge.style, end="exit")
        entry_xy = edge_attachment(edge.style, end="entry")
        if exit_xy is None or entry_xy is None:
            continue
        start = (
            source.x + source.width * exit_xy[0],
            source.y + source.height * exit_xy[1],
        )
        end = (
            target.x + target.width * entry_xy[0],
            target.y + target.height * entry_xy[1],
        )
        points = _simplify_points([start, *edge.waypoints, end])
        groups.setdefault((edge.source_id, exit_xy), []).append(points)

    junctions: set[tuple[float, float]] = set()
    for paths in groups.values():
        for index, first in enumerate(paths):
            for second in paths[index + 1 :]:
                split = _shared_prefix_split(first, second)
                if split is not None and split != first[0]:
                    junctions.add((round(split[0], 4), round(split[1], 4)))
    return sorted(junctions, key=lambda point: (point[0], point[1]))


def _shared_prefix_split(
    first: list[tuple[float, float]],
    second: list[tuple[float, float]],
) -> tuple[float, float] | None:
    if not first or not second or first[0] != second[0]:
        return None
    i = j = 0
    current = first[0]
    while i + 1 < len(first) and j + 1 < len(second):
        a_end = first[i + 1]
        b_end = second[j + 1]
        a_dir = _direction(current, a_end)
        b_dir = _direction(current, b_end)
        if a_dir != b_dir:
            return current
        a_distance = abs(a_end[0] - current[0]) + abs(a_end[1] - current[1])
        b_distance = abs(b_end[0] - current[0]) + abs(b_end[1] - current[1])
        if a_distance < b_distance:
            return a_end
        if b_distance < a_distance:
            return b_end
        current = a_end
        i += 1
        j += 1
        if current != b_end:
            return current
    return None


def _direction(a: tuple[float, float], b: tuple[float, float]) -> tuple[int, int]:
    return (
        0 if a[0] == b[0] else (1 if b[0] > a[0] else -1),
        0 if a[1] == b[1] else (1 if b[1] > a[1] else -1),
    )


def _simplify_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for point in points:
        if out and point == out[-1]:
            continue
        if len(out) >= 2 and (
            out[-2][0] == out[-1][0] == point[0]
            or out[-2][1] == out[-1][1] == point[1]
        ):
            out[-1] = point
        else:
            out.append(point)
    return out


def _junction_xml(index: int, x: float, y: float) -> str:
    return (
        f'<mxCell id="junction-{index}" '
        'style="ellipse;aspect=fixed;fillColor=#000000;strokeColor=#000000;connectable=0;" '
        'vertex="1" parent="1">'
        f'<mxGeometry x="{_fmt(x - 3)}" y="{_fmt(y - 3)}" width="6" height="6" as="geometry"/>'
        '</mxCell>'
    )


def _vertex_xml(vertex: VertexLayout) -> str:
    attrs = dict(vertex.object_attrs)
    attrs["name"] = vertex.logical_name or vertex.name
    attrs = canonical_object_attrs(vertex.drawclock_type, attrs)
    label = attrs.get("label", "")
    if label and LABEL_PLACEHOLDER_RE.search(label):
        attrs["label"] = bake_label_placeholders(label, attrs)
    if attrs.get("label") and not LABEL_PLACEHOLDER_RE.search(attrs["label"]):
        attrs["placeholders"] = "0"
    elif "placeholders" not in attrs:
        attrs["placeholders"] = "1"
    attrs["id"] = vertex.cell_id
    attr_order = ["name", "label", "placeholders", "id"]
    remaining = [k for k in sorted(attrs) if k not in attr_order]
    ordered_keys = [k for k in attr_order if k in attrs] + remaining
    attr_parts = [f'{key}="{xml_attr(attrs[key])}"' for key in ordered_keys]
    geom = (
        f'<mxGeometry x="{_fmt(vertex.x)}" y="{_fmt(vertex.y)}" '
        f'width="{_fmt(vertex.width)}" height="{_fmt(vertex.height)}" as="geometry"/>'
    )
    style_raw = canonical_vertex_style(vertex.drawclock_type, vertex.style)
    if attrs.get("placeholders") == "0":
        style_raw = style_raw.replace("placeholders=1;", "placeholders=0;")
    style = xml_attr(style_raw)
    return (
        f"<object {' '.join(attr_parts)}>"
        f'<mxCell style="{style}" vertex="1" parent="1">'
        f"{geom}"
        "</mxCell>"
        "</object>"
    )


def _edge_xml(edge: EdgeLayout, by_id: dict[str, VertexLayout]) -> str:
    src = by_id.get(edge.source_id)
    tgt = by_id.get(edge.target_id)
    if src is not None and tgt is not None:
        style_raw = resolve_edge_style(
            src.style,
            src.drawclock_type,
            tgt.style,
            tgt.drawclock_type,
            edge.style,
        )
    else:
        style_raw = edge.style
    style = xml_attr(style_raw)
    rel = "1" if edge.relative else "0"
    geom_inner = ""
    if edge.waypoints:
        points = "".join(
            f'<mxPoint x="{_fmt(x)}" y="{_fmt(y)}" as="point"/>' for x, y in edge.waypoints
        )
        geom_inner = f"<Array as=\"points\">{points}</Array>"
    geom = f'<mxGeometry relative="{rel}" as="geometry">{geom_inner}</mxGeometry>'
    return (
        f'<mxCell id="{xml_attr(edge.cell_id)}" style="{style}" edge="1" parent="1" '
        f'source="{xml_attr(edge.source_id)}" target="{xml_attr(edge.target_id)}">'
        f"{geom}"
        "</mxCell>"
    )


def _fmt(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)
