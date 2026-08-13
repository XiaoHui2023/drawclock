from __future__ import annotations

import json
import math
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from auto_layout import (
    LogicalEdge,
    Segment,
    _overlap_length,
    _proper_cross,
    _ranks,
    _segment_hits_rect,
    build_logical_edges,
    load_clock_tree,
    load_component_hints,
    resolve_nodes,
)
from drawio_decode import extract_mxfile_xml, iter_diagram_models
from drawio_graph import edge_attachment, parse_models
from drawio_layout import LayoutDocument, layout_from_diagram
from drawio_library import load_library_shapes
from drawio_ports import abs_port_xy, infer_port_from_attachment, port_anchors
from visual_geometry import vertex_visual_box


QUALITY_SCHEMA_VERSION = 6  # Test-only Agent artifact inspection schema.


def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def _style_value(style: str, key: str) -> str | None:
    prefix = f"{key}="
    for part in style.split(";"):
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def _grid_error(value: float, grid: float) -> float:
    return abs(value - round(value / grid) * grid)


def _rect_overlap(a: Any, b: Any, tolerance: float) -> bool:
    return (
        max(a.x, b.x) < min(a.x + a.width, b.x + b.width) - tolerance
        and max(a.y, b.y) < min(a.y + a.height, b.y + b.height) - tolerance
    )


def _points_for_edge(edge: Any, source: Any, target: Any) -> list[tuple[float, float]]:
    exit_xy = edge_attachment(edge.style, end="exit")
    entry_xy = edge_attachment(edge.style, end="entry")
    if exit_xy is None or entry_xy is None:
        return []
    start = (source.x + source.width * exit_xy[0], source.y + source.height * exit_xy[1])
    end = (target.x + target.width * entry_xy[0], target.y + target.height * entry_xy[1])
    return [start, *edge.waypoints, end]


def _canonical_orthogonal_points(
    points: list[tuple[float, float]], tolerance: float
) -> list[tuple[float, float]]:
    """Remove representation noise without repairing a genuinely sloped route."""
    if not points:
        return []
    result = [points[0]]
    for x, y in points[1:]:
        px, py = result[-1]
        if abs(x - px) <= tolerance:
            x = px
        if abs(y - py) <= tolerance:
            y = py
        result.append((x, y))
    return result


def _edge_key(source: str, source_port: str, target: str, target_port: str) -> str:
    return f"{source}:{source_port}->{target}:{target_port}"


def _inversion_count(values: list[tuple[float, float]]) -> int:
    return sum(
        (a_source - b_source) * (a_target - b_target) < 0
        for index, (a_source, a_target) in enumerate(values)
        for b_source, b_target in values[index + 1 :]
    )


def inspect_layout_quality(
    config: dict[str, dict[str, Any]],
    document: LayoutDocument,
    *,
    library_path: str | Path,
    component_hints: dict[str, str] | None = None,
    grid: float = 10.0,
    tolerance: float = 0.5,
    runtime_ms: float = 0.0,
    exact_pair_oracle: bool = False,
    routing_clearance: float = 18.0,
) -> dict[str, Any]:
    if grid <= 0:
        raise ValueError("grid must be greater than zero")
    if tolerance < 0:
        raise ValueError("tolerance must not be negative")
    if routing_clearance < 0:
        raise ValueError("routing_clearance must not be negative")

    shapes = load_library_shapes(library_path)
    resolved = resolve_nodes(
        config, shapes, component_hints or {}, library_path=library_path
    )
    logical_edges = build_logical_edges(config, resolved, library_path)
    ranks = _ranks(resolved, logical_edges)
    vertices_by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    vertices_by_name = {vertex.name: vertex for vertex in document.vertices}
    visual_boxes = {
        vertex.name: vertex_visual_box(vertex) for vertex in document.vertices
    }

    duplicate_node_names = sorted(
        name for name, count in Counter(vertex.name for vertex in document.vertices).items() if count > 1
    )
    missing_nodes = sorted(set(config) - set(vertices_by_name))
    extra_nodes = sorted(set(vertices_by_name) - set(config))
    type_mismatches: list[str] = []
    size_mismatches: list[str] = []
    grid_violations: list[str] = []
    port_alignment_errors: list[float] = []
    for name in sorted(set(config) & set(vertices_by_name)):
        vertex = vertices_by_name[name]
        expected = resolved[name].shape
        if vertex.drawclock_type != expected.title:
            type_mismatches.append(name)
        if not (_close(vertex.width, expected.w, tolerance) and _close(vertex.height, expected.h, tolerance)):
            size_mismatches.append(name)
        error = max(_grid_error(vertex.x, grid), _grid_error(vertex.y, grid))
        if error > tolerance:
            grid_violations.append(name)

    rank_spreads: dict[str, float] = {}
    # Compare like geometry with like geometry.  Different component types can
    # have different transparent left insets even when their connection axes
    # are aligned, so a raw mixed-shape left-edge comparison is a false reject.
    rank_shape_groups = sorted({
        (ranks[name], vertices_by_name[name].drawclock_type)
        for name in ranks if name in vertices_by_name
    })
    for rank, shape_type in rank_shape_groups:
        xs = [
            vertices_by_name[name].x for name in ranks
            if ranks[name] == rank
            and name in vertices_by_name
            and vertices_by_name[name].drawclock_type == shape_type
        ]
        rank_spreads[f"{rank}:{shape_type}"] = max(xs) - min(xs) if xs else 0.0
    rank_x_spread_max = max(rank_spreads.values(), default=0.0)

    expected_counter = Counter(edge.key for edge in logical_edges)
    logical_fanout = Counter(
        (edge.source, edge.source_port) for edge in logical_edges
    )
    logical_indegree = Counter(edge.target for edge in logical_edges)
    observed_counter: Counter[str] = Counter()
    dangling_edges: list[str] = []
    unresolved_port_edges: list[str] = []
    non_orthogonal_segments: list[str] = []
    zero_length_segments: list[str] = []
    redundant_waypoints: list[str] = []
    backtracking_edges: list[str] = []
    all_segments: list[Segment] = []
    edge_segments: dict[str, list[Segment]] = {}
    edge_points: dict[str, list[tuple[float, float]]] = {}
    crossing_capable: dict[str, bool] = {}
    bends_total = 0
    bends_max = 0
    manhattan_length = 0.0
    route_inefficiencies: list[float] = []
    vertical_lengths: list[float] = []
    micro_segments: list[str] = []
    source_lead_non_horizontal: list[str] = []
    target_lead_non_horizontal: list[str] = []
    source_lead_inside_visual: list[str] = []
    target_lead_inside_visual: list[str] = []
    source_lead_clearance_short: list[str] = []
    target_lead_clearance_short: list[str] = []
    first_stub_x_by_net: dict[tuple[str, str], set[float]] = defaultdict(set)
    edge_bends_by_key: dict[str, int] = {}
    observed_edge_ports: dict[str, tuple[str, str, str, str]] = {}
    local_axis_offsets: list[float] = []
    straight_local_edges = 0
    chain_axis_doglegs: list[str] = []

    for edge in document.edges:
        source = vertices_by_id.get(edge.source_id)
        target = vertices_by_id.get(edge.target_id)
        if source is None or target is None:
            dangling_edges.append(edge.cell_id)
            continue
        source_port = infer_port_from_attachment(source.style, edge.style, end="exit")
        target_port = infer_port_from_attachment(target.style, edge.style, end="entry")
        exit_xy = edge_attachment(edge.style, end="exit")
        entry_xy = edge_attachment(edge.style, end="entry")
        if source_port is None or target_port is None or exit_xy is None or entry_xy is None:
            unresolved_port_edges.append(edge.cell_id)
            continue
        expected_exit = port_anchors(source.style, source.drawclock_type)[source_port]
        expected_entry = port_anchors(target.style, target.drawclock_type)[target_port]
        port_alignment_errors.extend(
            [
                source.width * abs(exit_xy[0] - expected_exit[0]),
                source.height * abs(exit_xy[1] - expected_exit[1]),
                target.width * abs(entry_xy[0] - expected_entry[0]),
                target.height * abs(entry_xy[1] - expected_entry[1]),
            ]
        )
        key = _edge_key(source.name, source_port, target.name, target_port)
        observed_counter[key] += 1
        observed_edge_ports[edge.cell_id] = (source.name, source_port, target.name, target_port)
        points = _canonical_orthogonal_points(
            _points_for_edge(edge, source, target), tolerance
        )
        if not points:
            unresolved_port_edges.append(edge.cell_id)
            continue
        axis_offset = abs(points[-1][1] - points[0][1])
        if logical_fanout[(source.name, source_port)] == 1:
            local_axis_offsets.append(axis_offset)
            straight_local_edges += int(axis_offset <= tolerance)
            if logical_indegree[target.name] == 1 and axis_offset > tolerance:
                chain_axis_doglegs.append(edge.cell_id)
        redundant = False
        if len(points) >= 2 and abs(points[1][1] - points[0][1]) > tolerance:
            source_lead_non_horizontal.append(edge.cell_id)
        if len(points) >= 2 and abs(points[-1][1] - points[-2][1]) > tolerance:
            target_lead_non_horizontal.append(edge.cell_id)
        first_vertical = next(
            (
                (a, b)
                for a, b in zip(points, points[1:])
                if abs(a[0] - b[0]) <= tolerance
                and abs(a[1] - b[1]) > tolerance
            ),
            None,
        )
        last_vertical = next(
            (
                (a, b)
                for a, b in reversed(list(zip(points, points[1:])))
                if abs(a[0] - b[0]) <= tolerance
                and abs(a[1] - b[1]) > tolerance
            ),
            None,
        )
        if (
            first_vertical is not None
            and first_vertical[0][0]
            < visual_boxes[source.name].right - tolerance
        ):
            source_lead_inside_visual.append(edge.cell_id)
        if (
            first_vertical is not None
            and first_vertical[0][0]
            < visual_boxes[source.name].right + routing_clearance - tolerance
        ):
            source_lead_clearance_short.append(edge.cell_id)
        if (
            last_vertical is not None
            and last_vertical[0][0]
            > visual_boxes[target.name].left + tolerance
        ):
            target_lead_inside_visual.append(edge.cell_id)
        if (
            last_vertical is not None
            and last_vertical[0][0]
            > visual_boxes[target.name].left - routing_clearance + tolerance
        ):
            target_lead_clearance_short.append(edge.cell_id)
        # A fan-out trunk is the first vertical distribution segment after a
        # source port.  A straight, already-aligned child has no trunk of its
        # own and must not be misclassified as fragmentation.
        first_vertical_x = next(
            (
                a[0]
                for a, b in zip(points, points[1:])
                if abs(a[0] - b[0]) <= tolerance
                and abs(a[1] - b[1]) > tolerance
            ),
            None,
        )
        if first_vertical_x is not None:
            first_stub_x_by_net[(source.name, source_port)].add(
                round(first_vertical_x, 3)
            )
        for index, (a, b) in enumerate(zip(points, points[1:])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            segment_length = abs(dx) + abs(dy)
            if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
                zero_length_segments.append(f"{edge.cell_id}:{index}")
                redundant = True
            elif abs(dx) > tolerance and abs(dy) > tolerance:
                non_orthogonal_segments.append(f"{edge.cell_id}:{index}")
            elif 0 < segment_length < 1.0:
                micro_segments.append(f"{edge.cell_id}:{index}")
            if abs(dx) <= tolerance and abs(dy) > tolerance:
                vertical_lengths.append(abs(dy))
            manhattan_length += abs(dx) + abs(dy)
        for index in range(1, len(points) - 1):
            a, b, c = points[index - 1 : index + 2]
            if (
                (abs(a[0] - b[0]) <= 1e-9 and abs(b[0] - c[0]) <= 1e-9)
                or (abs(a[1] - b[1]) <= 1e-9 and abs(b[1] - c[1]) <= 1e-9)
            ):
                redundant = True
        if redundant:
            redundant_waypoints.append(edge.cell_id)
        if any(b[0] < a[0] - tolerance for a, b in zip(points, points[1:])):
            backtracking_edges.append(edge.cell_id)
        bends = max(0, len(points) - 2)
        bends_total += bends
        bends_max = max(bends_max, bends)
        edge_bends_by_key[key] = bends
        direct = abs(points[-1][0] - points[0][0]) + abs(points[-1][1] - points[0][1])
        routed = sum(
            abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:])
        )
        route_inefficiencies.append(routed / direct if direct > tolerance else 1.0)
        logical = LogicalEdge(source.name, target.name, source_port, target_port)
        segments = [
            Segment(key, (source.name, source_port), a, b)
            for a, b in zip(points, points[1:])
            if not (_close(a[0], b[0], tolerance) and _close(a[1], b[1], tolerance))
        ]
        edge_segments[edge.cell_id] = segments
        edge_points[edge.cell_id] = points
        all_segments.extend(segments)
        crossing_capable[edge.cell_id] = _style_value(edge.style, "jumpStyle") in {"arc", "gap", "sharp"}

    missing_edges = sorted((expected_counter - observed_counter).elements())
    extra_edges = sorted((observed_counter - expected_counter).elements())
    duplicate_edges = sorted(key for key, count in observed_counter.items() if count > expected_counter[key])

    spatial_size = 256.0
    node_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, vertex in enumerate(document.vertices):
        box = visual_boxes[vertex.name].inflated(routing_clearance)
        x0 = math.floor(box[0] / spatial_size)
        x1 = math.floor(box[2] / spatial_size)
        y0 = math.floor(box[1] / spatial_size)
        y1 = math.floor(box[3] / spatial_size)
        for bx in range(x0, x1 + 1):
            for by in range(y0, y1 + 1):
                node_buckets[(bx, by)].append(index)

    overlap_pairs: set[tuple[int, int]] = set()
    for indices in node_buckets.values():
        for offset, first in enumerate(indices):
            for second in indices[offset + 1 :]:
                overlap_pairs.add(tuple(sorted((first, second))))
    node_overlaps = sorted(
        f"{document.vertices[first].name}<->{document.vertices[second].name}"
        for first, second in overlap_pairs
        if _rect_overlap(document.vertices[first], document.vertices[second], tolerance)
    )

    edge_node_intersections: list[str] = []
    edge_label_intersections: list[str] = []
    for edge_id, segments in edge_segments.items():
        endpoints = observed_edge_ports[edge_id]
        for segment in segments:
            min_x, max_x = sorted((segment.a[0], segment.b[0]))
            min_y, max_y = sorted((segment.a[1], segment.b[1]))
            candidates: set[int] = set()
            for bx in range(math.floor(min_x / spatial_size), math.floor(max_x / spatial_size) + 1):
                for by in range(math.floor(min_y / spatial_size), math.floor(max_y / spatial_size) + 1):
                    candidates.update(node_buckets.get((bx, by), ()))
            for index in candidates:
                vertex = document.vertices[index]
                if vertex.name in (endpoints[0], endpoints[2]):
                    continue
                box = visual_boxes[vertex.name]
                rect = (box.left, box.top, box.right, box.bottom)
                if _segment_hits_rect(segment.a, segment.b, rect):
                    edge_node_intersections.append(f"{edge_id}->{vertex.name}")
                    body = (
                        vertex.x,
                        vertex.y,
                        vertex.x + vertex.width,
                        vertex.y + vertex.height,
                    )
                    if not _segment_hits_rect(segment.a, segment.b, body):
                        edge_label_intersections.append(
                            f"{edge_id}->{vertex.name}"
                        )

    # An outer corridor is not intrinsically wrong: an obstacle can require
    # it.  It becomes a hard failure only when the already allocated x
    # channels admit a strictly shorter collision-free orthogonal route closer
    # to the endpoint band.  This catches the historical global-bottom-lane
    # failure without applying a graph-size or absolute-distance threshold.
    outer_detour_edges: list[str] = []
    avoidable_outer_detours: list[str] = []
    outer_excursions: list[float] = []
    rank_nodes: dict[int, list[Any]] = defaultdict(list)
    for name, rank in ranks.items():
        if name in vertices_by_name:
            rank_nodes[rank].append(vertices_by_name[name])
    node_top = min((vertex.y for vertex in document.vertices), default=0.0)
    node_bottom = max(
        (vertex.y + vertex.height for vertex in document.vertices), default=0.0
    )
    for edge_id, points in edge_points.items():
        if len(points) < 4:
            continue
        source_name, source_port, target_name, _ = observed_edge_ports[edge_id]
        endpoint_low, endpoint_high = sorted((points[0][1], points[-1][1]))
        route_low = min(point[1] for point in points)
        route_high = max(point[1] for point in points)
        actual_outer = max(
            0.0, endpoint_low - route_low, route_high - endpoint_high
        )
        if actual_outer <= tolerance:
            continue
        outer_detour_edges.append(edge_id)
        outer_excursions.append(actual_outer)
        source_rank, target_rank = ranks[source_name], ranks[target_name]
        if target_rank <= source_rank + 1:
            continue
        x1, x2 = points[1][0], points[-2][0]
        reversed_channels = x2 < x1 - tolerance
        channel_pairs = {(x1, x2)}
        if reversed_channels:
            midpoint_x = (points[0][0] + points[-1][0]) / 2
            channel_pairs.update({
                (x1, x1), (x2, x2), (midpoint_x, midpoint_x)
            })
        obstacles = [
            vertex.name
            for rank in range(source_rank + 1, target_rank)
            for vertex in rank_nodes[rank]
            if vertex.name not in (source_name, target_name)
        ]
        candidate_lanes = {points[0][1], points[-1][1]}
        for name in obstacles:
            box = visual_boxes[name]
            candidate_lanes.add(box.top - routing_clearance)
            candidate_lanes.add(box.bottom + routing_clearance)
        actual_length = sum(
            abs(b[0] - a[0]) + abs(b[1] - a[1])
            for a, b in zip(points, points[1:])
        )
        source_net = (source_name, source_port)
        other_segments = [
            segment
            for other_id, segments in edge_segments.items()
            if other_id != edge_id
            for segment in segments
            if segment.source_net != source_net
        ]

        def interaction_cost(segments: list[Segment]) -> tuple[int, int]:
            overlaps = sum(
                _overlap_length(segment, other) >= grid
                for segment in segments
                for other in other_segments
            )
            crossings = sum(
                _proper_cross(segment, other)
                for segment in segments
                for other in other_segments
            )
            return overlaps, crossings

        actual_interactions = interaction_cost(edge_segments[edge_id])
        best_local: tuple[int, int, float, float] | None = None
        for candidate_x1, candidate_x2 in channel_pairs:
            for lane in candidate_lanes:
                candidate = _canonical_orthogonal_points(
                    [points[0], (candidate_x1, points[0][1]),
                     (candidate_x1, lane), (candidate_x2, lane),
                     (candidate_x2, points[-1][1]), points[-1]],
                    tolerance,
                )
                candidate_segments = [
                    Segment("candidate", source_net, a, b)
                    for a, b in zip(candidate, candidate[1:])
                    if not (
                        _close(a[0], b[0], tolerance)
                        and _close(a[1], b[1], tolerance)
                    )
                ]
                if any(
                    _segment_hits_rect(
                        segment.a,
                        segment.b,
                        (
                            visual_boxes[name].left,
                            visual_boxes[name].top,
                            visual_boxes[name].right,
                            visual_boxes[name].bottom,
                        ),
                    )
                    for segment in candidate_segments
                    for name in obstacles
                ):
                    continue
                local_outer = max(
                    0.0, endpoint_low - lane, lane - endpoint_high
                )
                local_length = sum(
                    abs(b[0] - a[0]) + abs(b[1] - a[1])
                    for a, b in zip(candidate, candidate[1:])
                )
                local_overlaps, local_crossings = interaction_cost(
                    candidate_segments
                )
                score = (
                    local_overlaps,
                    local_crossings,
                    local_outer,
                    local_length,
                )
                if best_local is None or score < best_local:
                    best_local = score
        escaped_node_bounds = (
            route_low < node_top - tolerance
            or route_high > node_bottom + tolerance
        )
        if (
            escaped_node_bounds
            and best_local is not None
            and best_local[0] <= actual_interactions[0]
            and best_local[1] <= actual_interactions[1]
            and best_local[2] < actual_outer - tolerance
            and best_local[3] < actual_length - tolerance
        ):
            avoidable_outer_detours.append(edge_id)

    crossings: list[tuple[str, str]] = []
    crossing_pair_intersections = 0
    crossing_points: set[tuple[float, float]] = set()
    source_crossing_points: set[tuple[float, float]] = set()
    same_net_junctions: list[tuple[str, str]] = []
    same_net_junction_intersections = 0
    ambiguous_overlaps: list[tuple[str, str]] = []
    untreated_crossings: list[tuple[str, str]] = []
    segment_owner = {
        id(segment): edge_id for edge_id, segments in edge_segments.items() for segment in segments
    }
    root_names = {
        name for name in resolved if logical_indegree[name] == 0
    }
    if exact_pair_oracle:
        for index, a in enumerate(all_segments):
            for b in all_segments[index + 1 :]:
                edge_a, edge_b = segment_owner[id(a)], segment_owner[id(b)]
                if edge_a == edge_b:
                    continue
                if _proper_cross(a, b):
                    pair = tuple(sorted((edge_a, edge_b)))
                    if a.source_net == b.source_net:
                        same_net_junctions.append(pair)
                    else:
                        crossings.append(pair)
                        vertical, horizontal = (a, b) if a.a[0] == a.b[0] else (b, a)
                        point = (round(vertical.a[0], 3), round(horizontal.a[1], 3))
                        crossing_points.add(point)
                        if (
                            observed_edge_ports[edge_a][0] in root_names
                            or observed_edge_ports[edge_b][0] in root_names
                        ):
                            source_crossing_points.add(point)
                if _overlap_length(a, b) >= grid and a.source_net != b.source_net:
                    ambiguous_overlaps.append(tuple(sorted((edge_a, edge_b))))
    else:
        # Shared trunks create many logical segments with identical geometry.
        # Collapse those segments before the sweep, then expand only actual
        # crossing owner pairs.  This preserves the exact report while making
        # the Agent-side checker depend on visible geometry rather than fanout
        # multiplicity.
        grouped: dict[
            tuple[str, float, float, float, tuple[str, str]],
            tuple[Segment, set[str]],
        ] = {}
        for segment in all_segments:
            if segment.a[0] == segment.b[0]:
                lo, hi = sorted((segment.a[1], segment.b[1]))
                key = ("v", segment.a[0], lo, hi, segment.source_net)
            else:
                lo, hi = sorted((segment.a[0], segment.b[0]))
                key = ("h", segment.a[1], lo, hi, segment.source_net)
            if key not in grouped:
                grouped[key] = (segment, set())
            grouped[key][1].add(segment_owner[id(segment)])
        verticals = [value for key, value in grouped.items() if key[0] == "v"]
        horizontals = [value for key, value in grouped.items() if key[0] == "h"]
        horizontal_by_y: dict[
            float, list[tuple[float, float, Segment, set[str]]]
        ] = defaultdict(list)
        for segment, owners in horizontals:
            x0, x1 = sorted((segment.a[0], segment.b[0]))
            horizontal_by_y[segment.a[1]].append((x0, x1, segment, owners))
        horizontal_ys = sorted(horizontal_by_y)
        for intervals in horizontal_by_y.values():
            intervals.sort(key=lambda item: item[0])
        for vertical, vertical_owners in verticals:
            x = vertical.a[0]
            y0, y1 = sorted((vertical.a[1], vertical.b[1]))
            lo = bisect_right(horizontal_ys, y0)
            hi = bisect_left(horizontal_ys, y1)
            for y in horizontal_ys[lo:hi]:
                for x0, x1, horizontal, horizontal_owners in horizontal_by_y[y]:
                    if x0 >= x:
                        break
                    if x >= x1:
                        continue
                    pair_count = (
                        len(vertical_owners) * len(horizontal_owners)
                        - len(vertical_owners & horizontal_owners)
                    )
                    if vertical.source_net == horizontal.source_net:
                        same_net_junction_intersections += pair_count
                    elif pair_count:
                        crossing_pair_intersections += pair_count
                        point = (round(x, 3), round(y, 3))
                        crossing_points.add(point)
                        if any(
                            observed_edge_ports[edge_id][0] in root_names
                            for edge_id in vertical_owners | horizontal_owners
                        ):
                            source_crossing_points.add(point)
                        untreated_crossings.extend(
                            tuple(sorted((edge_a, edge_b)))
                            for edge_a in vertical_owners
                            if not crossing_capable.get(edge_a)
                            for edge_b in horizontal_owners
                            if edge_a != edge_b and not crossing_capable.get(edge_b)
                        )

        parallel: dict[
            tuple[str, float], list[tuple[Segment, set[str]]]
        ] = defaultdict(list)
        for segment, owners in verticals:
            parallel[("v", segment.a[0])].append((segment, owners))
        for segment, owners in horizontals:
            parallel[("h", segment.a[1])].append((segment, owners))
        for group in parallel.values():
            intervals = []
            for segment, owners in group:
                values = (segment.a[1], segment.b[1]) if segment.a[0] == segment.b[0] else (segment.a[0], segment.b[0])
                lo, hi = sorted(values)
                intervals.append((lo, hi, segment, owners))
            intervals.sort(key=lambda item: item[0])
            active: list[tuple[float, Segment, set[str]]] = []
            for lo, hi, segment, owners in intervals:
                active = [(end, other, other_owners) for end, other, other_owners in active if end - lo >= grid]
                for end, other, other_owners in active:
                    if segment.source_net == other.source_net:
                        continue
                    ambiguous_overlaps.extend(
                        tuple(sorted((edge_a, edge_b)))
                        for edge_a in owners
                        for edge_b in other_owners
                        if edge_a != edge_b
                    )
                active.append((hi, segment, owners))
    crossings = sorted(set(crossings))
    same_net_junctions = sorted(set(same_net_junctions))
    ambiguous_overlaps = sorted(set(ambiguous_overlaps))
    if exact_pair_oracle:
        crossing_pair_intersections = len(crossings)
        same_net_junction_intersections = len(same_net_junctions)
        untreated_crossings = [
            pair for pair in crossings
            if not (crossing_capable.get(pair[0]) or crossing_capable.get(pair[1]))
        ]
    untreated_crossings = sorted(set(untreated_crossings))

    # Independently search the artifact's own visibility channels for a
    # monotone H-V-H route.  A route is rejected only when that simpler route
    # is obstacle-free and dominates the stored route without adding a
    # different-net overlap or crossing.  This makes bend/crossing quality
    # structural instead of tying it to a pixel threshold or fixture name.
    avoidable_bend_edges: list[str] = []
    avoidable_crossing_edges: list[str] = []
    zigzag_edges: list[str] = []
    segment_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, segment in enumerate(all_segments):
        min_x, max_x = sorted((segment.a[0], segment.b[0]))
        min_y, max_y = sorted((segment.a[1], segment.b[1]))
        for bx in range(
            math.floor(min_x / spatial_size),
            math.floor(max_x / spatial_size) + 1,
        ):
            for by in range(
                math.floor(min_y / spatial_size),
                math.floor(max_y / spatial_size) + 1,
            ):
                segment_buckets[(bx, by)].append(index)

    def nearby_segment_indices(segments: list[Segment]) -> set[int]:
        result: set[int] = set()
        for segment in segments:
            min_x, max_x = sorted((segment.a[0], segment.b[0]))
            min_y, max_y = sorted((segment.a[1], segment.b[1]))
            for bx in range(
                math.floor(min_x / spatial_size),
                math.floor(max_x / spatial_size) + 1,
            ):
                for by in range(
                    math.floor(min_y / spatial_size),
                    math.floor(max_y / spatial_size) + 1,
                ):
                    result.update(segment_buckets.get((bx, by), ()))
        return result

    for edge_id, points in edge_points.items():
        actual_bends = max(0, len(points) - 2)
        if actual_bends < 4:
            continue
        source_name, source_port, target_name, _ = observed_edge_ports[edge_id]
        net = (source_name, source_port)
        own_segments = edge_segments[edge_id]

        def route_cost(segments: list[Segment], bends: int) -> tuple[int, int, int, int, float]:
            nearby_node_indices: set[int] = set()
            for segment in segments:
                min_x, max_x = sorted((segment.a[0], segment.b[0]))
                min_y, max_y = sorted((segment.a[1], segment.b[1]))
                for bx in range(
                    math.floor(min_x / spatial_size),
                    math.floor(max_x / spatial_size) + 1,
                ):
                    for by in range(
                        math.floor(min_y / spatial_size),
                        math.floor(max_y / spatial_size) + 1,
                    ):
                        nearby_node_indices.update(
                            node_buckets.get((bx, by), ())
                        )
            hits = sum(
                _segment_hits_rect(
                    segment.a,
                    segment.b,
                    box.inflated(routing_clearance),
                )
                for segment in segments
                for index in nearby_node_indices
                for name in (document.vertices[index].name,)
                for box in (visual_boxes[name],)
                if name not in (source_name, target_name)
            )
            other_segments = [
                all_segments[index]
                for index in nearby_segment_indices(segments)
                if all_segments[index].edge_key != own_segments[0].edge_key
                and all_segments[index].source_net != net
            ] if own_segments else []
            overlaps = sum(
                _overlap_length(segment, other) >= 10.0
                for segment in segments
                for other in other_segments
            )
            crossing_count = sum(
                _proper_cross(segment, other)
                for segment in segments
                for other in other_segments
            )
            length = sum(
                abs(segment.b[0] - segment.a[0])
                + abs(segment.b[1] - segment.a[1])
                for segment in segments
            )
            return hits, overlaps, crossing_count, bends, length

        actual_cost = route_cost(own_segments, actual_bends)
        source_right = visual_boxes[source_name].right
        target_left = visual_boxes[target_name].left
        candidate_xs = {
            point[0]
            for point in points[1:-1]
            if source_right - tolerance <= point[0] <= target_left + tolerance
        }
        if source_right <= target_left:
            candidate_xs.add((source_right + target_left) / 2.0)
        best_cost: tuple[int, int, int, int, float] | None = None
        for x in candidate_xs:
            candidate_points = _canonical_orthogonal_points(
                [points[0], (x, points[0][1]), (x, points[-1][1]), points[-1]],
                tolerance,
            )
            candidate_points = [
                point
                for index, point in enumerate(candidate_points)
                if index == 0
                or not (
                    _close(point[0], candidate_points[index - 1][0], tolerance)
                    and _close(point[1], candidate_points[index - 1][1], tolerance)
                )
            ]
            candidate_segments = [
                Segment(edge_id, net, a, b)
                for a, b in zip(candidate_points, candidate_points[1:])
                if not (
                    _close(a[0], b[0], tolerance)
                    and _close(a[1], b[1], tolerance)
                )
            ]
            candidate_bends = max(0, len(candidate_points) - 2)
            cost = route_cost(candidate_segments, candidate_bends)
            if cost[0] == 0 and (best_cost is None or cost < best_cost):
                best_cost = cost
        if best_cost is None:
            continue
        if (
            best_cost[1] <= actual_cost[1]
            and best_cost[2] <= actual_cost[2]
            and best_cost[3] < actual_cost[3]
        ):
            avoidable_bend_edges.append(edge_id)
            if actual_bends >= 4:
                zigzag_edges.append(edge_id)
        if (
            best_cost[1] <= actual_cost[1]
            and best_cost[2] < actual_cost[2]
            and best_cost[3] <= actual_cost[3]
        ):
            avoidable_crossing_edges.append(edge_id)

    direction_violations = sorted(
        edge_id
        for edge_id, (source_name, _, target_name, _) in observed_edge_ports.items()
        if vertices_by_name[source_name].x >= vertices_by_name[target_name].x - tolerance
    )

    mux_inputs: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for source_name, source_port, target_name, target_port in observed_edge_ports.values():
        target = vertices_by_name[target_name]
        if not target_port.startswith("in"):
            continue
        source = vertices_by_name[source_name]
        source_y = abs_port_xy(
            source.x, source.y, source.width, source.height,
            source.style, source.drawclock_type, source_port,
        )[1]
        target_y = abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, target_port,
        )[1]
        mux_inputs[target_name].append((source_y, target_y))
    mux_input_order_inversions = sum(_inversion_count(values) for values in mux_inputs.values())

    # Traceability is measured over complete source-to-terminal paths, not only
    # over individual edges.  The graph is validated as a DAG upstream.
    incoming: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for logical in logical_edges:
        incoming[logical.target].append((logical.source, logical.key))
    path_bend_memo: dict[str, int] = {}

    def path_bends(name: str) -> int:
        if name in path_bend_memo:
            return path_bend_memo[name]
        parents = incoming.get(name, [])
        value = max(
            (path_bends(parent) + edge_bends_by_key.get(key, 0) for parent, key in parents),
            default=0,
        )
        path_bend_memo[name] = value
        return value

    terminal_path_bends = [
        path_bends(name) for name, item in config.items() if item.get("kind") == "clock"
    ]
    # Multiple local trunks are justified only when target axes have natural
    # geometric clusters.  This is evaluated from the final artifact and
    # library boxes, independently of the production router's bookkeeping.
    target_axes_by_net: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for source_name, source_port, target_name, target_port in observed_edge_ports.values():
        target = vertices_by_name[target_name]
        target_y = abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, target_port,
        )[1]
        target_axes_by_net[(source_name, source_port)].append(
            (target_y, target.height)
        )
    justified_trunk_counts: dict[tuple[str, str], int] = {}
    for net, targets in target_axes_by_net.items():
        ordered_targets = sorted(targets)
        axes = [axis for axis, _ in ordered_targets]
        gaps = [right - left for left, right in zip(axes, axes[1:])]
        positive_gaps = [gap for gap in gaps if gap > tolerance]
        ordinary_pitch = float(median(positive_gaps)) if positive_gaps else 0.0
        ordinary_height = float(median(height for _, height in ordered_targets))
        split_threshold = max(
            2 * ordinary_pitch,
            ordinary_height + 2 * routing_clearance + grid,
        )
        justified_trunk_counts[net] = 1 + sum(
            gap > split_threshold for gap in gaps
        )
    fanout_trunk_clusters = {
        f"{name}:{port}": len(xs)
        for (name, port), xs in first_stub_x_by_net.items()
        if logical_fanout[(name, port)] > 1 and len(xs) > 1
    }
    fragmented_fanouts = {
        f"{name}:{port}": len(xs)
        for (name, port), xs in first_stub_x_by_net.items()
        if logical_fanout[(name, port)] > 1
        and len(xs) > justified_trunk_counts.get((name, port), 1)
    }

    # A sink-layer order inversion is an avoidable crossing: terminal nodes
    # have no successors constraining their vertical order, so swapping them
    # can remove the inversion without changing topology or port correctness.
    logical_outdegree = Counter(edge.source for edge in logical_edges)
    terminal_edges: list[tuple[str, float, float, tuple[str, str]]] = []
    rightmost_rank = max(ranks.values(), default=0)
    for edge_id, (source_name, source_port, target_name, target_port) in observed_edge_ports.items():
        if (
            logical_outdegree[target_name] != 0
            or ranks.get(target_name) != rightmost_rank
        ):
            continue
        source = vertices_by_name[source_name]
        target = vertices_by_name[target_name]
        source_y = abs_port_xy(
            source.x, source.y, source.width, source.height,
            source.style, source.drawclock_type, source_port,
        )[1]
        target_y = abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, target_port,
        )[1]
        terminal_edges.append((edge_id, source_y, target_y, (source_name, source_port)))
    terminal_order_inversions = sum(
        source_net_a != source_net_b
        and (source_y_a - source_y_b) * (target_y_a - target_y_b) < -(tolerance ** 2)
        for index, (_, source_y_a, target_y_a, source_net_a) in enumerate(terminal_edges)
        for _, source_y_b, target_y_b, source_net_b in terminal_edges[index + 1:]
    )
    terminal_edge_ids = {edge_id for edge_id, *_ in terminal_edges}
    avoidable_terminal_crossings = sum(
        left in terminal_edge_ids and right in terminal_edge_ids
        for left, right in crossings
    )
    logical_indegree_by_name = Counter(edge.target for edge in logical_edges)
    root_names = {
        name for name in config if logical_indegree_by_name[name] == 0
    }
    direct_axes_by_root: dict[str, list[float]] = defaultdict(list)
    for source_name, _, target_name, target_port in observed_edge_ports.values():
        if source_name not in root_names:
            continue
        target = vertices_by_name[target_name]
        direct_axes_by_root[source_name].append(abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, target_port,
        )[1])
    root_consumer_interleavings = {
        root: sum(
            low + tolerance < axis < high - tolerance
            for other_root, other_axes in direct_axes_by_root.items()
            if other_root != root
            for axis in other_axes
        )
        for root, axes in direct_axes_by_root.items()
        if len(axes) > 1
        for low, high in [(min(axes), max(axes))]
    }

    vertical_gaps: list[float] = []
    for rank in sorted(set(ranks.values())):
        items = sorted(
            (visual_boxes[name] for name in ranks if ranks[name] == rank and name in vertices_by_name),
            key=lambda item: item.top,
        )
        vertical_gaps.extend(b.top - a.bottom for a, b in zip(items, items[1:]))
    gap_mean = sum(vertical_gaps) / len(vertical_gaps) if vertical_gaps else 0.0
    gap_cv = (
        math.sqrt(sum((gap - gap_mean) ** 2 for gap in vertical_gaps) / len(vertical_gaps)) / gap_mean
        if vertical_gaps and gap_mean > tolerance
        else 0.0
    )

    alignment_failures = (
        duplicate_node_names + missing_nodes + extra_nodes + type_mismatches + size_mismatches
        + grid_violations + (["rank-x-spread"] if rank_x_spread_max > tolerance else [])
        + (["port-anchor-error"] if max(port_alignment_errors, default=0.0) > tolerance else [])
    )
    line_failures = (
        dangling_edges + unresolved_port_edges + missing_edges + extra_edges + duplicate_edges
        + non_orthogonal_segments + zero_length_segments + redundant_waypoints
        + micro_segments + source_lead_non_horizontal + target_lead_non_horizontal
        + [f"source-lead-inside-visual:{edge_id}" for edge_id in source_lead_inside_visual]
        + [f"target-lead-inside-visual:{edge_id}" for edge_id in target_lead_inside_visual]
        + [f"source-lead-clearance-short:{edge_id}" for edge_id in source_lead_clearance_short]
        + [f"target-lead-clearance-short:{edge_id}" for edge_id in target_lead_clearance_short]
        + backtracking_edges + edge_node_intersections
        + [f"avoidable-bends:{edge_id}" for edge_id in avoidable_bend_edges]
        + [f"avoidable-crossing:{edge_id}" for edge_id in avoidable_crossing_edges]
        + [f"avoidable-outer-detour:{edge_id}" for edge_id in avoidable_outer_detours]
        + [f"overlap:{a}/{b}" for a, b in ambiguous_overlaps]
        + [f"unbridged:{a}/{b}" for a, b in untreated_crossings]
    )
    # A source-order inversion at a fixed-port mux is a readability cost, not
    # a correctness failure: crossings are explicitly permitted and the port
    # mapping remains exact.
    rank_levels = sorted(set(ranks.values()))
    inter_rank_gaps: list[dict[str, float | int]] = []
    for left_rank, right_rank in zip(rank_levels, rank_levels[1:]):
        left_edge = max(
            visual_boxes[name].right
            for name in ranks
            if ranks[name] == left_rank and name in vertices_by_name
        )
        right_edge = min(
            visual_boxes[name].left
            for name in ranks
            if ranks[name] == right_rank and name in vertices_by_name
        )
        lane_xs = sorted({
            round(segment.a[0], 6)
            for segment in all_segments
            if abs(segment.a[0] - segment.b[0]) <= tolerance
            and left_edge < segment.a[0] < right_edge
        })
        required = 2 * routing_clearance
        if lane_xs:
            required += lane_xs[-1] - lane_xs[0]
        actual = right_edge - left_edge
        inter_rank_gaps.append({
            "left_rank": left_rank,
            "right_rank": right_rank,
            "actual_px": round(actual, 3),
            "required_by_routes_px": round(required, 3),
            "avoidable_px": round(max(0.0, actual - required), 3),
        })
    avoidable_inter_rank_gap = sum(
        float(item["avoidable_px"]) for item in inter_rank_gaps
    )
    order_failures = (
        node_overlaps
        + direction_violations
        + (["avoidable-terminal-crossing"] if avoidable_terminal_crossings else [])
    )
    hard_failures = sorted(set(alignment_failures + line_failures + order_failures))

    min_x = min((box.left for box in visual_boxes.values()), default=0.0)
    min_y = min((box.top for box in visual_boxes.values()), default=0.0)
    max_x = max((box.right for box in visual_boxes.values()), default=0.0)
    max_y = max((box.bottom for box in visual_boxes.values()), default=0.0)
    bounding_area = max(0.0, max_x - min_x) * max(0.0, max_y - min_y)
    visible_area = sum(
        (box.right - box.left) * (box.bottom - box.top)
        for box in visual_boxes.values()
    )
    return {
        "quality_schema_version": QUALITY_SCHEMA_VERSION,
        "passed": not hard_failures,
        "hard_failures": hard_failures,
        "alignment": {
            "passed": not alignment_failures,
            "missing_nodes": missing_nodes,
            "extra_nodes": extra_nodes,
            "duplicate_node_names": duplicate_node_names,
            "type_mismatches": type_mismatches,
            "size_mismatches": size_mismatches,
            "grid_violations": grid_violations,
            "rank_x_spread_max_px": round(rank_x_spread_max, 3),
            "rank_x_spreads_px": {key: round(value, 3) for key, value in rank_spreads.items()},
            "port_alignment_error_max_px": round(max(port_alignment_errors, default=0.0), 3),
        },
        "line_integrity": {
            "passed": not line_failures,
            "expected_edges": sum(expected_counter.values()),
            "observed_edges": len(document.edges),
            "missing_edges": missing_edges,
            "extra_edges": extra_edges,
            "duplicate_edges": duplicate_edges,
            "dangling_edges": dangling_edges,
            "unresolved_port_edges": sorted(set(unresolved_port_edges)),
            "non_orthogonal_segments": non_orthogonal_segments,
            "micro_segments": micro_segments,
            "source_lead_non_horizontal": sorted(set(source_lead_non_horizontal)),
            "target_lead_non_horizontal": sorted(set(target_lead_non_horizontal)),
            "source_lead_inside_visual": sorted(set(source_lead_inside_visual)),
            "target_lead_inside_visual": sorted(set(target_lead_inside_visual)),
            "source_lead_clearance_short": sorted(set(source_lead_clearance_short)),
            "target_lead_clearance_short": sorted(set(target_lead_clearance_short)),
            "zero_length_segments": zero_length_segments,
            "redundant_waypoint_edges": sorted(set(redundant_waypoints)),
            "backtracking_edges": sorted(set(backtracking_edges)),
            "edge_node_intersections": sorted(set(edge_node_intersections)),
            "edge_label_intersections": sorted(set(edge_label_intersections)),
            "avoidable_outer_detours": sorted(set(avoidable_outer_detours)),
            "avoidable_bend_edges": sorted(set(avoidable_bend_edges)),
            "avoidable_crossing_edges": sorted(set(avoidable_crossing_edges)),
            "zigzag_edges": sorted(set(zigzag_edges)),
            "ambiguous_overlaps": [list(pair) for pair in ambiguous_overlaps],
            "crossings": crossing_pair_intersections,
            "distinct_crossing_points": len(crossing_points),
            "source_induced_crossing_points": len(source_crossing_points),
            "same_net_junctions": same_net_junction_intersections,
            "untreated_crossings": [list(pair) for pair in untreated_crossings],
            "bends_total": bends_total,
            "bends_max_per_edge": bends_max,
            "manhattan_length_px": round(manhattan_length, 2),
        },
        "readability": {
            "crossings_per_100_edges": round(100 * len(crossing_points) / max(1, len(document.edges)), 3),
            "route_inefficiency_mean": round(sum(route_inefficiencies) / max(1, len(route_inefficiencies)), 4),
            "route_inefficiency_max": round(max(route_inefficiencies, default=1.0), 4),
            "vertical_segment_max_px": round(max(vertical_lengths, default=0.0), 3),
            "vertical_segments_over_300px": sum(length > 300 for length in vertical_lengths),
            "outer_detour_edges": sorted(set(outer_detour_edges)),
            "outer_excursion_max_px": round(max(outer_excursions, default=0.0), 3),
            "straight_local_edge_ratio": round(
                straight_local_edges / max(1, len(local_axis_offsets)), 4
            ),
            "local_axis_offset_mean_px": round(
                sum(local_axis_offsets) / max(1, len(local_axis_offsets)), 3
            ),
            "local_axis_offset_max_px": round(
                max(local_axis_offsets, default=0.0), 3
            ),
            "chain_axis_dogleg_edges": sorted(set(chain_axis_doglegs)),
            "fragmented_fanout_sources": fragmented_fanouts,
            "fanout_trunk_clusters": fanout_trunk_clusters,
            "root_consumer_interleavings": root_consumer_interleavings,
            "terminal_path_bends_mean": round(sum(terminal_path_bends) / max(1, len(terminal_path_bends)), 3),
            "terminal_path_bends_max": max(terminal_path_bends, default=0),
        },
        "layout_order": {
            "passed": not order_failures,
            "node_overlaps": node_overlaps,
            "direction_violations": direction_violations,
            "mux_input_order_inversions": mux_input_order_inversions,
            "terminal_order_inversions": terminal_order_inversions,
            "avoidable_terminal_crossings": avoidable_terminal_crossings,
            "vertical_gap_min_px": round(min(vertical_gaps), 3) if vertical_gaps else None,
            "vertical_gap_cv": round(gap_cv, 4),
            "visible_footprint_area_px2": round(visible_area, 2),
            "visible_whitespace_area_px2": round(max(0.0, bounding_area - visible_area), 2),
            "visible_fill_ratio": round(visible_area / bounding_area, 6) if bounding_area else 1.0,
            "inter_rank_gaps": inter_rank_gaps,
            "avoidable_inter_rank_gap_total_px": round(avoidable_inter_rank_gap, 3),
            "width_px": round(max_x - min_x, 2),
            "height_px": round(max_y - min_y, 2),
        },
        "runtime_ms": round(runtime_ms, 3),
    }


def inspect_drawio_quality(
    config_path: str | Path,
    drawio_path: str | Path,
    *,
    library_path: str | Path,
    hints_path: str | Path | None = None,
    grid: float = 10.0,
    tolerance: float = 0.5,
) -> dict[str, Any]:
    started = time.perf_counter()
    config = load_clock_tree(config_path)
    hints = load_component_hints(hints_path)
    mxfile = extract_mxfile_xml(str(drawio_path))
    models = iter_diagram_models(mxfile)
    if not models:
        raise ValueError(f"draw.io file contains no diagram model: {drawio_path}")
    # Inspect the artifact exactly as stored. Reload-time port repair must not
    # hide a malformed generated connector from the quality gate.
    document = layout_from_diagram(parse_models(models), resolve_ports=False)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return inspect_layout_quality(
        config,
        document,
        library_path=library_path,
        component_hints=hints,
        grid=grid,
        tolerance=tolerance,
        runtime_ms=elapsed_ms,
    )


def write_quality_report(report: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
