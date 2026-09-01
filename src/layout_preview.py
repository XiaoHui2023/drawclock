from __future__ import annotations

from bisect import bisect_left, bisect_right, insort
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from drawio_layout import LayoutDocument, VertexLayout
from drawio_ports import abs_port_xy, edge_attachment, port_anchors
from svg_native import render_native_label, validate_static_svg

# draw.io places an html=1 label's content origin 2 px right and 7 px below
# mxGeometry.  The component library deliberately applies the inverse offset
# to its graphic layer.  Native SVG previews must reproduce the outer offset,
# otherwise the visible symbol and the mathematically routed ports diverge.
HTML_LABEL_CONTENT_OFFSET_X = 2.0
HTML_LABEL_CONTENT_OFFSET_Y = 7.0

FREQUENCY_COLUMNS = (
    ("func_freq", "工作频率"),
    ("scan_freq", "SCAN"),
    ("bist_freq", "BIST"),
)
FREQUENCY_FONT_SIZE = 12.0
FREQUENCY_COLUMN_GAP = 20.0
FREQUENCY_TABLE_GAP = 34.0
# Four fixed heading glyph outlines from Noto Sans CJK SC Regular 2.004
# (SIL OFL 1.1).  Keeping only outlines makes the final SVG independent of
# viewer fonts while adding no runtime dependency.  See licenses/.
FREQUENCY_CJK_GLYPHS = (
    "M52 72V-3H951V72H539V650H900V727H104V650H456V72Z",
    "M526 828C476 681 395 536 305 442C322 430 351 404 363 391C414 447 463 520 506 601H575V-79H651V164H952V235H651V387H939V456H651V601H962V673H542C563 717 582 763 598 809ZM285 836C229 684 135 534 36 437C50 420 72 379 80 362C114 397 147 437 179 481V-78H254V599C293 667 329 741 357 814Z",
    "M701 501C699 151 688 35 446-30C459-43 477-67 483-83C743-9 762 129 764 501ZM728 84C795 34 881-38 923-82L968-34C925 9 837 78 770 126ZM428 386C376 178 261 42 49-25C64-40 81-65 88-83C315-3 438 144 493 371ZM133 397C113 323 80 248 37 197C54 189 81 172 93 162C135 217 174 301 196 383ZM544 609V137H608V550H854V139H922V609H742L782 714H950V781H518V714H709C699 680 686 640 672 609ZM114 753V529H39V461H248V158H316V461H502V529H334V652H479V716H334V841H266V529H176V753Z",
    "M829 643C794 603 732 548 687 515L742 478C788 510 846 558 892 605ZM56 337 94 277C160 309 242 353 319 394L304 451C213 407 118 363 56 337ZM85 599C139 565 205 515 236 481L290 527C256 561 190 609 136 640ZM677 408C746 366 832 306 874 266L930 311C886 351 797 410 730 448ZM51 202V132H460V-80H540V132H950V202H540V284H460V202ZM435 828C450 805 468 776 481 750H71V681H438C408 633 374 592 361 579C346 561 331 550 317 547C324 530 334 498 338 483C353 489 375 494 490 503C442 454 399 415 379 399C345 371 319 352 297 349C305 330 315 297 318 284C339 293 374 298 636 324C648 304 658 286 664 270L724 297C703 343 652 415 607 466L551 443C568 424 585 401 600 379L423 364C511 434 599 522 679 615L618 650C597 622 573 594 550 567L421 560C454 595 487 637 516 681H941V750H569C555 779 531 818 508 847Z",
)


@dataclass(frozen=True)
class FrequencyTable:
    terminals: tuple[tuple[VertexLayout, float], ...]
    column_centers: tuple[float, ...]
    header_y: float
    min_x: float
    min_y: float
    max_x: float
    max_y: float


def _estimated_text_width(text: str) -> float:
    """Conservative SVG text width without depending on an installed font."""
    return sum(12.0 if ord(char) > 0x7F else 7.2 for char in text)


def _frequency_table(document: LayoutDocument) -> FrequencyTable | None:
    outgoing_ids = {edge.source_id for edge in document.edges}
    terminals = [
        vertex for vertex in document.vertices if vertex.cell_id not in outgoing_ids
    ]
    if not terminals:
        return None

    incoming_by_target = defaultdict(list)
    for edge in document.edges:
        incoming_by_target[edge.target_id].append(edge)

    rows: list[tuple[VertexLayout, float]] = []
    for vertex in terminals:
        incoming = incoming_by_target.get(vertex.cell_id, [])
        axes: list[float] = []
        for edge in incoming:
            entry_xy = edge_attachment(edge.style, end="entry")
            if entry_xy is not None:
                axes.append(vertex.y + vertex.height * entry_xy[1])
        row_axis = sum(axes) / len(axes) if axes else vertex.y + vertex.height / 2
        rows.append((vertex, row_axis))
    rows.sort(key=lambda row: (row[1], row[0].name))

    table_left = max(
        vertex.x + vertex.width + HTML_LABEL_CONTENT_OFFSET_X
        for vertex, _ in rows
    ) + FREQUENCY_TABLE_GAP
    column_widths: list[float] = []
    for field, heading in FREQUENCY_COLUMNS:
        widest = max(
            [_estimated_text_width(heading)]
            + [
                _estimated_text_width(vertex.object_attrs.get(field, ""))
                for vertex, _ in rows
            ]
        )
        column_widths.append(max(58.0, widest + 12.0))
    centers: list[float] = []
    cursor = table_left
    for width in column_widths:
        centers.append(cursor + width / 2)
        cursor += width + FREQUENCY_COLUMN_GAP
    max_x = cursor - FREQUENCY_COLUMN_GAP
    first_axis = rows[0][1]
    header_y = first_axis - 28.0
    return FrequencyTable(
        terminals=tuple(rows),
        column_centers=tuple(centers),
        header_y=header_y,
        min_x=table_left,
        min_y=header_y - FREQUENCY_FONT_SIZE,
        max_x=max_x,
        max_y=max(row_axis + FREQUENCY_FONT_SIZE / 2 for _, row_axis in rows),
    )


def _render_frequency_table(table: FrequencyTable) -> list[str]:
    lines = ['<g class="frequency-table">']
    for (field, heading), center_x in zip(
        FREQUENCY_COLUMNS, table.column_centers
    ):
        if heading == "工作频率":
            start_x = center_x - 2 * FREQUENCY_FONT_SIZE
            lines.append(
                f'<g class="frequency-heading" data-frequency-field="{field}" '
                'data-heading-render="outline" aria-label="工作频率" '
                f'transform="translate({_svg_num(start_x)} {_svg_num(table.header_y)}) '
                f'scale({_svg_num(FREQUENCY_FONT_SIZE / 1000)} '
                f'{_svg_num(-FREQUENCY_FONT_SIZE / 1000)})" fill="#20252b">'
            )
            lines.append('<title>工作频率</title>')
            for index, path in enumerate(FREQUENCY_CJK_GLYPHS):
                lines.append(
                    f'<path transform="translate({index * 1000} 0)" d="{path}"/>'
                )
            lines.append("</g>")
            continue
        lines.append(
            f'<text class="frequency-heading" data-frequency-field="{field}" '
            f'x="{_svg_num(center_x)}" y="{_svg_num(table.header_y)}" '
            'text-anchor="middle" font-family="Noto Sans CJK SC,Microsoft YaHei,WenQuanYi Micro Hei,sans-serif" '
            f'font-size="{_svg_num(FREQUENCY_FONT_SIZE)}" fill="#20252b">'
            f'{_escape(heading)}</text>'
        )
    for vertex, row_axis in table.terminals:
        logical_name = vertex.logical_name or vertex.name
        for (field, _), center_x in zip(
            FREQUENCY_COLUMNS, table.column_centers
        ):
            value = vertex.object_attrs.get(field, "")
            if not value:
                continue
            lines.append(
                f'<text class="frequency-value" data-node-id="{_escape(logical_name)}" '
                f'data-frequency-field="{field}" x="{_svg_num(center_x)}" '
                f'y="{_svg_num(row_axis + FREQUENCY_FONT_SIZE * 0.35)}" '
                'text-anchor="middle" font-family="Arial,Noto Sans CJK SC,sans-serif" '
                f'font-size="{_svg_num(FREQUENCY_FONT_SIZE)}" fill="#d02020">'
                f'{_escape(value)}</text>'
            )
    lines.append("</g>")
    return lines


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
    horizontal_by_id: dict[int, tuple[str, int, float, tuple[str, tuple[float, float] | None]]] = {}
    events: list[tuple[float, int, int]] = []
    verticals: list[tuple[str, int, float, float, float, tuple[str, tuple[float, float] | None]]] = []
    serial = 0
    for edge in document.edges:
        points = edge_points[edge.cell_id]
        for segment_index, (a, b) in enumerate(zip(points, points[1:])):
            if a[1] == b[1] and a[0] != b[0]:
                x0, x1 = sorted((a[0], b[0]))
                horizontal_by_id[serial] = (
                    edge.cell_id, segment_index, a[1], nets[edge.cell_id]
                )
                # At the same x, remove endings before a vertical query and
                # add beginnings afterwards so endpoint touches are excluded.
                events.append((x0, 2, serial))
                events.append((x1, 0, serial))
                serial += 1
            elif a[0] == b[0] and a[1] != b[1]:
                y0, y1 = sorted((a[1], b[1]))
                verticals.append((
                    edge.cell_id, segment_index, a[0], y0, y1,
                    nets[edge.cell_id],
                ))
    for index, vertical in enumerate(verticals):
        events.append((vertical[2], 1, index))
    events.sort(key=lambda event: (event[0], event[1]))

    active_by_y: dict[float, set[int]] = defaultdict(set)
    active_ys: list[float] = []
    jump_sets: dict[str, dict[int, set[float]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for x, event_type, identifier in events:
        if event_type == 0:
            y = horizontal_by_id[identifier][2]
            active_by_y[y].remove(identifier)
            if not active_by_y[y]:
                del active_by_y[y]
                active_ys.pop(bisect_left(active_ys, y))
            continue
        if event_type == 2:
            y = horizontal_by_id[identifier][2]
            if y not in active_by_y:
                insort(active_ys, y)
            active_by_y[y].add(identifier)
            continue
        vertical_edge, _, _, y0, y1, vertical_net = verticals[identifier]
        for y in active_ys[bisect_right(active_ys, y0):bisect_left(active_ys, y1)]:
            for horizontal_id in active_by_y[y]:
                horizontal_edge, segment_index, _, horizontal_net = horizontal_by_id[horizontal_id]
                if horizontal_edge == vertical_edge or horizontal_net == vertical_net:
                    continue
                jump_sets[horizontal_edge][segment_index].add(x)
    return {
        edge_id: {
            segment_index: sorted(xs)
            for segment_index, xs in segments.items()
        }
        for edge_id, segments in jump_sets.items()
    }


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


def junction_points(document: LayoutDocument) -> list[tuple[float, float]]:
    """Return visible split points of same-source-port shared prefixes."""
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    groups: dict[
        tuple[str, tuple[float, float]],
        list[list[tuple[float, float]]],
    ] = {}
    for edge in document.edges:
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
    first_index = second_index = 0
    current = first[0]
    while first_index + 1 < len(first) and second_index + 1 < len(second):
        first_end = first[first_index + 1]
        second_end = second[second_index + 1]
        first_direction = _direction(current, first_end)
        second_direction = _direction(current, second_end)
        if first_direction != second_direction:
            return current
        first_distance = abs(first_end[0] - current[0]) + abs(first_end[1] - current[1])
        second_distance = abs(second_end[0] - current[0]) + abs(second_end[1] - current[1])
        if first_distance < second_distance:
            return first_end
        if second_distance < first_distance:
            return second_end
        current = first_end
        first_index += 1
        second_index += 1
        if current != second_end:
            return current
    return None


def _direction(
    start: tuple[float, float], end: tuple[float, float]
) -> tuple[int, int]:
    return (
        0 if start[0] == end[0] else (1 if end[0] > start[0] else -1),
        0 if start[1] == end[1] else (1 if end[1] > start[1] else -1),
    )


def _simplify_points(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    compact: list[tuple[float, float]] = []
    for point in points:
        if compact and point == compact[-1]:
            continue
        compact.append(point)
        while len(compact) >= 3:
            first, middle, last = compact[-3:]
            if (
                first[0] == middle[0] == last[0]
                or first[1] == middle[1] == last[1]
            ):
                compact.pop(-2)
            else:
                break
    return compact


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
    junctions = junction_points(document)
    for x, y in junctions:
        all_x.extend((x - 3.0, x + 3.0))
        all_y.extend((y - 3.0, y + 3.0))
    frequency_table = _frequency_table(document)
    if frequency_table is not None:
        all_x.extend((frequency_table.min_x, frequency_table.max_x))
        all_y.extend((frequency_table.min_y, frequency_table.max_y))
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
    for x, y in junctions:
        lines.append(
            f'<circle cx="{_svg_num(x)}" cy="{_svg_num(y)}" '
            'r="3" fill="#000000"/>'
        )
    for vertex in document.vertices:
        label = vertex.object_attrs.get("label", "")
        if label:
            rendered = render_native_label(
                label,
                x=vertex.x,
                y=vertex.y,
                width=vertex.width,
                height=vertex.height,
                content_offset_x=HTML_LABEL_CONTENT_OFFSET_X,
                content_offset_y=HTML_LABEL_CONTENT_OFFSET_Y,
            )
            logical_name = _escape(vertex.logical_name or vertex.name)
            lines.append(rendered.replace(
                '<g class="component">',
                f'<g class="component" data-node-id="{logical_name}">',
                1,
            ))
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
                f'{_escape(vertex.logical_name or vertex.name)}</text>'
            )
    if frequency_table is not None:
        lines.extend(_render_frequency_table(frequency_table))
    lines.append("</svg>")
    result = "\n".join(lines) + "\n"
    validate_static_svg(result)
    return result


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
