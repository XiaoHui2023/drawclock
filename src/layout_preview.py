from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from drawio_graph import edge_attachment
from drawio_build import junction_points
from drawio_layout import LayoutDocument
from drawio_ports import abs_port_xy, port_anchors

# draw.io places an html=1 label's content origin 2 px right and 7 px below
# mxGeometry.  The component library deliberately applies the inverse offset
# to its graphic layer.  Native SVG previews must reproduce the outer offset,
# otherwise the visible symbol and the mathematically routed ports diverge.
HTML_LABEL_CONTENT_OFFSET_X = 2.0
HTML_LABEL_CONTENT_OFFSET_Y = 7.0


def _svg_num(value: float) -> str:
    """Serialize every layout coordinate without losing its 4-decimal contract."""
    return f"{float(value):.4f}".rstrip("0").rstrip(".") or "0"


def _proper_orthogonal_crossing(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> tuple[float, float] | None:
    a_horizontal = a[1] == b[1] and a[0] != b[0]
    c_horizontal = c[1] == d[1] and c[0] != d[0]
    if a_horizontal == c_horizontal:
        return None
    horizontal_a, horizontal_b, vertical_a, vertical_b = (
        (a, b, c, d) if a_horizontal else (c, d, a, b)
    )
    x = vertical_a[0]
    y = horizontal_a[1]
    h0, h1 = sorted((horizontal_a[0], horizontal_b[0]))
    v0, v1 = sorted((vertical_a[1], vertical_b[1]))
    if h0 < x < h1 and v0 < y < v1:
        return x, y
    return None


def _arc_crossings(
    document: LayoutDocument,
    edge_points: dict[str, list[tuple[float, float]]],
) -> dict[str, dict[int, list[float]]]:
    """Choose the horizontal wire as the deterministic bridge at each crossing."""
    nets: dict[str, tuple[str, tuple[float, float] | None]] = {}
    for edge in document.edges:
        nets[edge.cell_id] = (
            edge.source_id,
            edge_attachment(edge.style, end="exit"),
        )
    jumps: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for edge_index, first in enumerate(document.edges):
        first_points = edge_points[first.cell_id]
        for second in document.edges[edge_index + 1 :]:
            if nets[first.cell_id] == nets[second.cell_id]:
                continue
            second_points = edge_points[second.cell_id]
            for first_segment, (a, b) in enumerate(zip(first_points, first_points[1:])):
                for second_segment, (c, d) in enumerate(zip(second_points, second_points[1:])):
                    crossing = _proper_orthogonal_crossing(a, b, c, d)
                    if crossing is None:
                        continue
                    if a[1] == b[1]:
                        jumps[first.cell_id][first_segment].append(crossing[0])
                    else:
                        jumps[second.cell_id][second_segment].append(crossing[0])
    return jumps


def _edge_arc_path(
    points: list[tuple[float, float]],
    crossings: dict[int, list[float]],
    *,
    radius: float = 4.0,
) -> str:
    commands = [f"M {_svg_num(points[0][0])} {_svg_num(points[0][1])}"]
    for index, (start, end) in enumerate(zip(points, points[1:])):
        xs = crossings.get(index, [])
        if start[1] != end[1] or not xs:
            commands.append(f"L {_svg_num(end[0])} {_svg_num(end[1])}")
            continue
        direction = 1.0 if end[0] > start[0] else -1.0
        ordered = sorted(xs, reverse=direction < 0)
        last = start[0]
        for x in ordered:
            before = x - direction * radius
            after = x + direction * radius
            if direction * (before - last) <= 0 or direction * (end[0] - after) <= 0:
                continue
            commands.append(f"L {_svg_num(before)} {_svg_num(start[1])}")
            commands.append(
                f"A {_svg_num(radius)} {_svg_num(radius)} 0 0 0 "
                f"{_svg_num(after)} {_svg_num(start[1])}"
            )
            last = after
        commands.append(f"L {_svg_num(end[0])} {_svg_num(end[1])}")
    return " ".join(commands)


def build_preview_svg(
    document: LayoutDocument,
    *,
    title: str = "drawclock",
    crossing_style: str = "arc",
) -> str:
    if not document.vertices:
        raise ValueError("布局中没有器件")
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    edge_points: dict[str, list[tuple[float, float]]] = {}
    for edge in document.edges:
        source = by_id[edge.source_id]
        target = by_id[edge.target_id]
        exit_xy = edge_attachment(edge.style, end="exit")
        entry_xy = edge_attachment(edge.style, end="entry")
        if exit_xy is None:
            source_ports = port_anchors(source.style, source.drawclock_type)
            exit_xy = source_ports.get("right") or source_ports.get("out")
        if entry_xy is None:
            target_ports = port_anchors(target.style, target.drawclock_type)
            entry_xy = target_ports.get("left") or next(iter(target_ports.values()))
        assert exit_xy is not None and entry_xy is not None
        start = (
            source.x + source.width * exit_xy[0],
            source.y + source.height * exit_xy[1],
        )
        end = (
            target.x + target.width * entry_xy[0],
            target.y + target.height * entry_xy[1],
        )
        edge_points[edge.cell_id] = [start, *edge.waypoints, end]

    # The scalable router may reserve channels outside the node rectangle.
    # The viewport therefore derives from the complete rendered geometry,
    # never from nodes alone.
    all_x = [
        coordinate
        for vertex in document.vertices
        for coordinate in (vertex.x, vertex.x + vertex.width + HTML_LABEL_CONTENT_OFFSET_X)
    ]
    all_y = [
        coordinate
        for vertex in document.vertices
        for coordinate in (vertex.y, vertex.y + vertex.height + HTML_LABEL_CONTENT_OFFSET_Y)
    ]
    for points in edge_points.values():
        all_x.extend(x for x, _ in points)
        all_y.extend(y for _, y in points)
    for x, y in junction_points(document):
        all_x.extend((x - 3.0, x + 3.0))
        all_y.extend((y - 3.0, y + 3.0))
    pad = 45.0
    min_x = min(all_x) - pad
    min_y = min(all_y) - pad
    max_x = max(all_x) + pad
    max_y = max(all_y) + pad
    width = max_x - min_x
    height = max_y - min_y
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
            f'viewBox="{_svg_num(min_x)} {_svg_num(min_y)} '
            f'{_svg_num(width)} {_svg_num(height)}" '
            f'width="{_svg_num(width)}" height="{_svg_num(height)}">'
        ),
        "<style>.edge-gap{fill:none;stroke:#fff;stroke-width:6;stroke-linejoin:round}.edge{fill:none;stroke:#20252b;stroke-width:1.6;stroke-linejoin:round;stroke-linecap:square}</style>",
        f'<rect x="{_svg_num(min_x)}" y="{_svg_num(min_y)}" '
        f'width="{_svg_num(width)}" height="{_svg_num(height)}" fill="#ffffff"/>',
        f'<text x="{_svg_num(min_x + 8)}" y="{_svg_num(min_y + 18)}" '
        f'font-family="Arial,sans-serif" font-size="12" fill="#68707a">{_escape(title)}</text>',
    ]
    arc_crossings = (
        _arc_crossings(document, edge_points) if crossing_style == "arc" else {}
    )
    render_edges = sorted(
        document.edges,
        key=lambda edge: (bool(arc_crossings.get(edge.cell_id)), edge.cell_id),
    )
    for edge in render_edges:
        points = edge_points[edge.cell_id]
        serialized = " ".join(
            f"{_svg_num(x)},{_svg_num(y)}" for x, y in points
        )
        if crossing_style in {"gap", "sharp"}:
            lines.append(f'<polyline class="edge-gap" points="{serialized}"/>')
        jumps = arc_crossings.get(edge.cell_id)
        if jumps:
            path = _edge_arc_path(points, jumps)
            lines.append(f'<path class="edge" d="{path}"/>')
        else:
            lines.append(f'<polyline class="edge" points="{serialized}"/>')
    for x, y in junction_points(document):
        lines.append(
            f'<circle cx="{_svg_num(x)}" cy="{_svg_num(y)}" '
            'r="3" fill="#000000"/>'
        )
    for vertex in document.vertices:
        label = vertex.object_attrs.get("label", "")
        if label:
            # Keep the viewport on mxGeometry. Moving it would leave the
            # left-side contact outside the clip boundary. The HTML content
            # offset belongs inside the viewport and cancels the graphic's
            # inverse (-2,-7) offset exactly.
            lines.append(
                f'<foreignObject x="{_svg_num(vertex.x)}" y="{_svg_num(vertex.y)}" '
                f'width="{_svg_num(vertex.width + HTML_LABEL_CONTENT_OFFSET_X)}" '
                f'height="{_svg_num(vertex.height + HTML_LABEL_CONTENT_OFFSET_Y)}" overflow="visible">'
                '<div xmlns="http://www.w3.org/1999/xhtml" '
                f'style="position:relative;left:{HTML_LABEL_CONTENT_OFFSET_X:g}px;'
                f'top:{HTML_LABEL_CONTENT_OFFSET_Y:g}px;width:{vertex.width:g}px;'
                f'height:{vertex.height:g}px;overflow:visible">'
                f"{label}</div></foreignObject>"
            )
        else:
            lines.append(
                f'<rect x="{_svg_num(vertex.x)}" y="{_svg_num(vertex.y)}" '
                f'width="{_svg_num(vertex.width)}" height="{_svg_num(vertex.height)}" '
                'fill="#f8fafc" stroke="#20252b"/>'
            )
            lines.append(
                f'<text x="{_svg_num(vertex.x + vertex.width / 2)}" '
                f'y="{_svg_num(vertex.y + vertex.height / 2)}" '
                'text-anchor="middle" dominant-baseline="middle" font-family="Arial,sans-serif" font-size="9">'
                f'{_escape(vertex.name)}</text>'
            )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def write_preview_svg(
    document: LayoutDocument,
    output_path: str | Path,
    *,
    title: str = "drawclock",
    crossing_style: str = "arc",
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_preview_svg(document, title=title, crossing_style=crossing_style),
        encoding="utf-8",
    )
    return output


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
