from __future__ import annotations

import json
import math
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict, deque
from pathlib import Path
from statistics import median
from typing import Any

from auto_layout import (
    LogicalEdge,
    Segment,
    _overlap_length,
    _layout_column_groups,
    _proper_cross,
    _ranks,
    _segment_hits_rect,
    build_logical_edges,
    resolve_nodes,
)
from drawio_layout import LayoutDocument
from drawio_library import load_library_shapes
from drawio_ports import (
    abs_port_xy,
    edge_attachment,
    infer_port_from_attachment,
    port_anchors,
)
from visual_geometry import vertex_visual_box


QUALITY_SCHEMA_VERSION = 12  # Test-only Agent artifact inspection schema.


def _independent_latest_forward_ranks(
    names: list[str], logical_edges: list[LogicalEdge]
) -> dict[str, int]:
    """Recompute unconstrained ALAP ranks without the production rank owner."""
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {name: 0 for name in names}
    for edge in logical_edges:
        outgoing[edge.source].append(edge.target)
        indegree[edge.target] += 1
    queue = deque(name for name in names if indegree[name] == 0)
    earliest = {name: 0 for name in names}
    topological: list[str] = []
    while queue:
        name = queue.popleft()
        topological.append(name)
        for child in outgoing[name]:
            earliest[child] = max(earliest[child], earliest[name] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(topological) != len(names):
        return earliest
    latest = {name: max(earliest.values(), default=0) for name in names}
    for name in reversed(topological):
        if outgoing[name]:
            latest[name] = min(latest[child] - 1 for child in outgoing[name])
    return latest


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
    joint_coordinate_oracle: bool = True,
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
    layout_column_groups = _layout_column_groups(config)
    ranks = _ranks(resolved, logical_edges, layout_column_groups)
    vertices_by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    vertices_by_internal_name = {
        vertex.name: vertex for vertex in document.vertices
    }
    logical_vertices: dict[str, list[Any]] = defaultdict(list)
    for vertex in document.vertices:
        logical_vertices[vertex.logical_name or vertex.name].append(vertex)
    vertices_by_name = {
        name: next(
            (vertex for vertex in vertices if vertex.logical_name is None),
            vertices[0],
        )
        for name, vertices in logical_vertices.items()
    }
    visual_boxes = {
        vertex.name: vertex_visual_box(vertex) for vertex in document.vertices
    }

    duplicate_node_names = sorted(
        name for name, count in Counter(vertex.name for vertex in document.vertices).items() if count > 1
    )
    missing_nodes = sorted(set(config) - set(logical_vertices))
    extra_nodes = sorted(set(logical_vertices) - set(config))
    logical_indegree_for_replicas = Counter(edge.target for edge in logical_edges)
    invalid_replicas = sorted(
        vertex.name
        for vertex in document.vertices
        if vertex.logical_name is not None
        and (
            vertex.logical_name not in config
            or logical_indegree_for_replicas[vertex.logical_name] != 0
        )
    )
    type_mismatches: list[str] = []
    size_mismatches: list[str] = []
    grid_violations: list[str] = []
    port_alignment_errors: list[float] = []
    for name in sorted(set(config) & set(logical_vertices)):
        expected = resolved[name].shape
        for vertex in logical_vertices[name]:
            if vertex.drawclock_type != expected.title:
                type_mismatches.append(vertex.name)
            if not (_close(vertex.width, expected.w, tolerance) and _close(vertex.height, expected.h, tolerance)):
                size_mismatches.append(vertex.name)
            error = max(_grid_error(vertex.x, grid), _grid_error(vertex.y, grid))
            if error > tolerance:
                grid_violations.append(vertex.name)

    rank_spreads: dict[str, float] = {}
    rank_indegree = Counter(edge.target for edge in logical_edges)
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
            and len(logical_vertices[name]) == 1
            and (
                rank_indegree[name] > 0
                or "layout_column" in config[name]
            )
            and vertices_by_name[name].drawclock_type == shape_type
        ]
        rank_spreads[f"{rank}:{shape_type}"] = max(xs) - min(xs) if xs else 0.0
    rank_x_spread_max = max(rank_spreads.values(), default=0.0)
    layout_column_misalignments: list[dict[str, Any]] = []
    for level, names in sorted(layout_column_groups.items()):
        # A nonzero expected rank span means the group contains a causal
        # dependency and cannot legally occupy one column.
        if len({ranks[name] for name in names}) != 1:
            continue
        xs = [vertices_by_name[name].x for name in names if name in vertices_by_name]
        spread = max(xs) - min(xs) if xs else 0.0
        if spread > tolerance:
            layout_column_misalignments.append({
                "level": level,
                "nodes": sorted(names),
                "spread_px": round(spread, 3),
            })
    layout_column_order_violations: list[dict[str, Any]] = []
    ordered_columns = sorted(layout_column_groups.items())
    for (left_level, left_names), (right_level, right_names) in zip(
        ordered_columns, ordered_columns[1:]
    ):
        if max(ranks[name] for name in left_names) >= min(
            ranks[name] for name in right_names
        ):
            continue
        left_x = max(vertices_by_name[name].x for name in left_names)
        right_x = min(vertices_by_name[name].x for name in right_names)
        if left_x + tolerance >= right_x:
            layout_column_order_violations.append({
                "left_level": left_level,
                "right_level": right_level,
                "left_nodes": sorted(left_names),
                "right_nodes": sorted(right_names),
                "left_x_max": round(left_x, 3),
                "right_x_min": round(right_x, 3),
            })

    expected_counter = Counter(edge.key for edge in logical_edges)
    logical_fanout = Counter(
        (edge.source, edge.source_port) for edge in logical_edges
    )
    logical_outdegree = Counter(edge.source for edge in logical_edges)
    logical_indegree = Counter(edge.target for edge in logical_edges)
    independent_ranks = _independent_latest_forward_ranks(
        list(resolved), logical_edges
    )
    primary_axes = {
        name: (vertex_visual_box(vertex).left + vertex_visual_box(vertex).right) / 2.0
        for name, vertex in vertices_by_name.items()
    }
    avoidable_root_layer_positions: list[dict[str, Any]] = []
    independent_levels = set(independent_ranks.values())
    for name in sorted(resolved):
        expected_rank = independent_ranks[name]
        if (
            logical_indegree[name] != 0
            or logical_outdegree[name] != 1
            or expected_rank <= 0
            or "layout_column" in config[name]
            or name not in primary_axes
        ):
            continue
        previous_rank = max(
            rank for rank in independent_levels if rank < expected_rank
        )
        previous_axes = [
            primary_axes[other]
            for other, rank in independent_ranks.items()
            if rank == previous_rank and other in primary_axes
        ]
        if previous_axes and primary_axes[name] <= max(previous_axes) + tolerance:
            avoidable_root_layer_positions.append({
                "node": name,
                "expected_rank": expected_rank,
                "actual_axis_x": round(primary_axes[name], 3),
                "previous_rank": previous_rank,
                "previous_rank_axis_x_max": round(max(previous_axes), 3),
            })
    observed_counter: Counter[str] = Counter()
    dangling_edges: list[str] = []
    unresolved_port_edges: list[str] = []
    non_orthogonal_segments: list[str] = []
    zero_length_segments: list[str] = []
    redundant_waypoints: list[str] = []
    backtracking_edges: list[str] = []
    all_segments: list[Segment] = []
    segment_edge_ids: list[str] = []
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
    observed_edge_vertices: dict[str, tuple[Any, Any]] = {}
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
        source_name = source.logical_name or source.name
        target_name = target.logical_name or target.name
        key = _edge_key(source_name, source_port, target_name, target_port)
        observed_counter[key] += 1
        observed_edge_ports[edge.cell_id] = (source_name, source_port, target_name, target_port)
        observed_edge_vertices[edge.cell_id] = (source, target)
        points = _canonical_orthogonal_points(
            _points_for_edge(edge, source, target), tolerance
        )
        if not points:
            unresolved_port_edges.append(edge.cell_id)
            continue
        axis_offset = abs(points[-1][1] - points[0][1])
        if logical_fanout[(source_name, source_port)] == 1:
            local_axis_offsets.append(axis_offset)
            straight_local_edges += int(axis_offset <= tolerance)
            if logical_indegree[target_name] == 1 and axis_offset > tolerance:
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
            first_stub_x_by_net[(source_name, source_port)].add(
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
        logical = LogicalEdge(source_name, target_name, source_port, target_port)
        segments = [
            Segment(key, (source_name, source_port), a, b)
            for a, b in zip(points, points[1:])
            if not (_close(a[0], b[0], tolerance) and _close(a[1], b[1], tolerance))
        ]
        edge_segments[edge.cell_id] = segments
        edge_points[edge.cell_id] = points
        all_segments.extend(segments)
        segment_edge_ids.extend([edge.cell_id] * len(segments))
        crossing_capable[edge.cell_id] = _style_value(edge.style, "jumpStyle") in {"arc", "gap", "sharp"}

    missing_edges = sorted((expected_counter - observed_counter).elements())
    extra_edges = sorted((observed_counter - expected_counter).elements())
    duplicate_edges = sorted(key for key, count in observed_counter.items() if count > expected_counter[key])
    # A physical source-port net must form a rooted geometric tree.  Shared
    # prefixes and later branching are valid; split -> rejoin -> split creates
    # an undirected cycle in the union and is always redundant.  Split every
    # segment at all route vertices so a junction on another edge's interior
    # is observed without depending on the production trunk implementation.
    edge_source_ids = {edge.cell_id: edge.source_id for edge in document.edges}
    physical_net_edges: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for edge_id, (source_name, source_port, _, _) in observed_edge_ports.items():
        physical_net_edges[(edge_source_ids[edge_id], source_name, source_port)].append(edge_id)
    split_rejoin_fanout_nets: list[str] = []
    for (source_id, source_name, source_port), edge_ids in physical_net_edges.items():
        if len(edge_ids) < 2:
            continue
        vertices = {
            (round(x, 6), round(y, 6))
            for edge_id in edge_ids for x, y in edge_points[edge_id]
        }
        union_edges: set[tuple[tuple[float, float], tuple[float, float]]] = set()
        for edge_id in edge_ids:
            for a, b in zip(edge_points[edge_id], edge_points[edge_id][1:]):
                if abs(a[0] - b[0]) <= tolerance:
                    points = [p for p in vertices if abs(p[0] - a[0]) <= tolerance and min(a[1], b[1]) - tolerance <= p[1] <= max(a[1], b[1]) + tolerance]
                    points.sort(key=lambda p: p[1])
                else:
                    points = [p for p in vertices if abs(p[1] - a[1]) <= tolerance and min(a[0], b[0]) - tolerance <= p[0] <= max(a[0], b[0]) + tolerance]
                    points.sort(key=lambda p: p[0])
                union_edges.update(tuple(sorted((left, right))) for left, right in zip(points, points[1:]) if left != right)
        parent: dict[tuple[float, float], tuple[float, float]] = {}
        def find(point):
            parent.setdefault(point, point)
            while parent[point] != point:
                parent[point] = parent[parent[point]]
                point = parent[point]
            return point
        has_cycle = False
        for left, right in sorted(union_edges):
            root_left, root_right = find(left), find(right)
            if root_left == root_right:
                has_cycle = True
                break
            parent[root_left] = root_right
        if has_cycle:
            split_rejoin_fanout_nets.append(f"{source_name}:{source_port}@{source_id}")
    used_source_ids = {edge.source_id for edge in document.edges}
    unused_replicas = sorted(
        vertex.name
        for vertex in document.vertices
        if vertex.logical_name is not None and vertex.cell_id not in used_source_ids
    )
    replica_identity_errors: list[str] = []
    for logical_name, vertices in logical_vertices.items():
        if len(vertices) <= 1:
            continue
        primary = vertices_by_name[logical_name]
        for vertex in vertices:
            if vertex is primary:
                continue
            if (
                vertex.drawclock_type != primary.drawclock_type
                or not _close(vertex.width, primary.width, tolerance)
                or not _close(vertex.height, primary.height, tolerance)
                or vertex.style != primary.style
                or vertex.object_attrs != primary.object_attrs
            ):
                replica_identity_errors.append(vertex.name)

    # Index resolution follows the independent clearance scale.  This keeps
    # candidate enumeration local on very tall stress artifacts without
    # changing any exact rectangle/segment predicate below.
    spatial_size = max(32.0, grid * 8.0, routing_clearance * 4.0)
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
        endpoint_vertices = observed_edge_vertices[edge_id]
        endpoint_ids = {
            endpoint_vertices[0].cell_id, endpoint_vertices[1].cell_id
        }
        for segment in segments:
            min_x, max_x = sorted((segment.a[0], segment.b[0]))
            min_y, max_y = sorted((segment.a[1], segment.b[1]))
            candidates: set[int] = set()
            for bx in range(math.floor(min_x / spatial_size), math.floor(max_x / spatial_size) + 1):
                for by in range(math.floor(min_y / spatial_size), math.floor(max_y / spatial_size) + 1):
                    candidates.update(node_buckets.get((bx, by), ()))
            for index in candidates:
                vertex = document.vertices[index]
                if vertex.cell_id in endpoint_ids:
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
        # One branch of a shared distribution net cannot be judged by an
        # independent reroute: doing so may shorten that branch only by
        # destroying the common trunk used by its siblings. Fan-out quality
        # is enforced below by the trunk-fragmentation and cluster gates.
        if (
            logical_fanout[source_net] > 1
            and len(first_stub_x_by_net[source_net]) <= 1
        ):
            continue
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
    crossing_owner_pairs: list[tuple[str, str]] = []
    crossing_pair_intersections = 0
    crossing_points: set[tuple[float, float]] = set()
    source_crossing_points: set[tuple[float, float]] = set()
    edge_crossing_points: dict[str, set[tuple[float, float]]] = defaultdict(set)
    edge_crossing_pair_incidents: Counter[str] = Counter()
    ordered_edge_ids = sorted(
        observed_edge_ports, key=lambda item: int(item[1:])
    )
    edge_index_by_id = {
        edge_id: index for index, edge_id in enumerate(ordered_edge_ids)
    }
    edge_crossed_owner_masks = [0] * len(ordered_edge_ids)
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
                        crossing_owner_pairs.append(pair)
                        crossing_pair_intersections += 1
                        vertical, horizontal = (a, b) if a.a[0] == a.b[0] else (b, a)
                        point = (round(vertical.a[0], 3), round(horizontal.a[1], 3))
                        crossing_points.add(point)
                        edge_crossing_points[edge_a].add(point)
                        edge_crossing_points[edge_b].add(point)
                        edge_crossing_pair_incidents[edge_a] += 1
                        edge_crossing_pair_incidents[edge_b] += 1
                        edge_crossed_owner_masks[
                            edge_index_by_id[edge_a]
                        ] |= 1 << edge_index_by_id[edge_b]
                        edge_crossed_owner_masks[
                            edge_index_by_id[edge_b]
                        ] |= 1 << edge_index_by_id[edge_a]
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
        horizontal_by_cell: dict[
            tuple[int, float],
            list[tuple[float, float, Segment, set[str]]],
        ] = defaultdict(list)
        for segment, owners in horizontals:
            x0, x1 = sorted((segment.a[0], segment.b[0]))
            item = (x0, x1, segment, owners)
            horizontal_by_y[segment.a[1]].append(item)
            for bx in range(
                math.floor(x0 / spatial_size),
                math.floor(x1 / spatial_size) + 1,
            ):
                horizontal_by_cell[(bx, segment.a[1])].append(item)
        horizontal_ys = sorted(horizontal_by_y)
        for intervals in horizontal_by_y.values():
            intervals.sort(key=lambda item: item[0])
        for vertical, vertical_owners in verticals:
            x = vertical.a[0]
            y0, y1 = sorted((vertical.a[1], vertical.b[1]))
            lo = bisect_right(horizontal_ys, y0)
            hi = bisect_left(horizontal_ys, y1)
            for y in horizontal_ys[lo:hi]:
                for x0, x1, horizontal, horizontal_owners in horizontal_by_cell.get(
                    (math.floor(x / spatial_size), y), ()
                ):
                    if x0 >= x or x >= x1:
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
                        for edge_id in vertical_owners:
                            edge_crossing_points[edge_id].add(point)
                            edge_crossing_pair_incidents[edge_id] += len(
                                horizontal_owners - {edge_id}
                            )
                        for edge_id in horizontal_owners:
                            edge_crossing_points[edge_id].add(point)
                            edge_crossing_pair_incidents[edge_id] += len(
                                vertical_owners - {edge_id}
                            )
                        vertical_mask = sum(
                            1 << edge_index_by_id[edge_id]
                            for edge_id in vertical_owners
                        )
                        horizontal_mask = sum(
                            1 << edge_index_by_id[edge_id]
                            for edge_id in horizontal_owners
                        )
                        for edge_id in vertical_owners:
                            edge_crossed_owner_masks[
                                edge_index_by_id[edge_id]
                            ] |= horizontal_mask & ~(
                                1 << edge_index_by_id[edge_id]
                            )
                        for edge_id in horizontal_owners:
                            edge_crossed_owner_masks[
                                edge_index_by_id[edge_id]
                            ] |= vertical_mask & ~(
                                1 << edge_index_by_id[edge_id]
                            )
                        if any(
                            observed_edge_ports[edge_id][0] in root_names
                            for edge_id in vertical_owners | horizontal_owners
                        ):
                            source_crossing_points.add(point)
                        # Downstream only needs owner pairs that enter the
                        # same merge.  Expanding every fanout Cartesian product
                        # materialized millions of irrelevant pairs.
                        vertical_by_target: dict[str, list[str]] = defaultdict(list)
                        horizontal_by_target: dict[str, list[str]] = defaultdict(list)
                        for edge_id in vertical_owners:
                            vertical_by_target[
                                observed_edge_ports[edge_id][2]
                            ].append(edge_id)
                        for edge_id in horizontal_owners:
                            horizontal_by_target[
                                observed_edge_ports[edge_id][2]
                            ].append(edge_id)
                        crossing_owner_pairs.extend(
                            tuple(sorted((edge_a, edge_b)))
                            for target_name in (
                                vertical_by_target.keys()
                                & horizontal_by_target.keys()
                            )
                            for edge_a in vertical_by_target[target_name]
                            for edge_b in horizontal_by_target[target_name]
                            if edge_a != edge_b
                        )
                        non_cap_vertical = [
                            edge_id for edge_id in vertical_owners
                            if not crossing_capable.get(edge_id)
                        ]
                        non_cap_horizontal = [
                            edge_id for edge_id in horizontal_owners
                            if not crossing_capable.get(edge_id)
                        ]
                        untreated_crossings.extend(
                            tuple(sorted((edge_a, edge_b)))
                            for edge_a in non_cap_vertical
                            for edge_b in non_cap_horizontal
                            if edge_a != edge_b
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
    distinct_crossed_edge_pairs = sum(
        owner_mask.bit_count() for owner_mask in edge_crossed_owner_masks
    ) // 2
    crossings = sorted(set(crossings))
    same_net_junctions = sorted(set(same_net_junctions))
    ambiguous_overlaps = sorted(set(ambiguous_overlaps))
    if exact_pair_oracle:
        same_net_junction_intersections = len(same_net_junctions)
        untreated_crossings = [
            pair for pair in crossings
            if not (crossing_capable.get(pair[0]) or crossing_capable.get(pair[1]))
        ]
    untreated_crossings = sorted(set(untreated_crossings))
    merge_input_crossings = sorted({
        pair
        for pair in crossing_owner_pairs
        if observed_edge_ports[pair[0]][2] == observed_edge_ports[pair[1]][2]
    })
    merge_input_order_inversions = sorted({
        pair
        for pair in merge_input_crossings
        if ranks[observed_edge_ports[pair[0]][0]]
        == ranks[observed_edge_ports[pair[1]][0]]
        and (
            edge_points[pair[0]][0][1] - edge_points[pair[1]][0][1]
        ) * (
            edge_points[pair[0]][-1][1] - edge_points[pair[1]][-1][1]
        ) < -(tolerance * tolerance)
    })
    avoidable_local_merge_input_crossings = sorted({
        pair
        for pair in merge_input_order_inversions
        if all(
            logical_indegree[observed_edge_ports[edge_id][0]] > 0
            and logical_outdegree[observed_edge_ports[edge_id][0]] <= 2
            for edge_id in pair
        )
    })
    root_merge_input_order_inversions = sorted({
        pair
        for pair in merge_input_order_inversions
        if all(
            logical_indegree[observed_edge_ports[edge_id][0]] == 0
            for edge_id in pair
        )
    })
    avoidable_root_merge_input_crossings = sorted({
        pair
        for pair in root_merge_input_order_inversions
        if any(
            logical_outdegree[observed_edge_ports[edge_id][0]] == 1
            for edge_id in pair
        )
    })

    raw_row_centers = sorted({
        round(vertex.y + vertex.height / 2.0, 6)
        for vertex in document.vertices
    })
    median_height = median(
        [vertex.height for vertex in document.vertices] or [1.0]
    )
    row_bands: list[list[float]] = []
    for axis in raw_row_centers:
        if not row_bands or axis - row_bands[-1][0] >= median_height:
            row_bands.append([axis])
        else:
            row_bands[-1].append(axis)
    row_centers = [median(band) for band in row_bands]
    row_deltas = [
        right - left
        for left, right in zip(row_centers, row_centers[1:])
        if right - left > tolerance
    ]
    geometry_pitch = max(1.0, median_height * 2.0)
    row_pitch = (
        max(median_height, min(median(row_deltas), geometry_pitch))
        if row_deltas else geometry_pitch
    )
    routing_edge_statistics: dict[str, dict[str, Any]] = {}
    routing_source_edges: dict[str, list[str]] = defaultdict(list)
    for edge_id in ordered_edge_ids:
        source_name, source_port, target_name, _ = observed_edge_ports[edge_id]
        points_for_edge = edge_points[edge_id]
        start, end = points_for_edge[0], points_for_edge[-1]
        low, high = sorted((start[1], end[1]))
        horizontal_length = sum(
            abs(a[0] - b[0])
            for a, b in zip(points_for_edge, points_for_edge[1:])
            if abs(a[1] - b[1]) <= tolerance
        )
        vertical_lengths_for_edge = [
            abs(a[1] - b[1])
            for a, b in zip(points_for_edge, points_for_edge[1:])
            if abs(a[0] - b[0]) <= tolerance
        ]
        vertical_length = sum(vertical_lengths_for_edge)
        route_length = horizontal_length + vertical_length
        direct_length = abs(end[0] - start[0]) + abs(end[1] - start[1])
        routing_edge_statistics[edge_id] = {
            "source": source_name,
            "target": target_name,
            "crossing_points": len(edge_crossing_points[edge_id]),
            "crossing_pair_incidents": edge_crossing_pair_incidents[edge_id],
            "crossed_edge_count": edge_crossed_owner_masks[
                edge_index_by_id[edge_id]
            ].bit_count(),
            "source_port_fanout": logical_fanout[(source_name, source_port)],
            "branch_siblings": max(
                0, logical_fanout[(source_name, source_port)] - 1
            ),
            "vertical_span_px": round(high - low, 3),
            "vertical_span_rows": round((high - low) / row_pitch, 3),
            "intervening_rows": sum(low < axis < high for axis in row_centers),
            "manhattan_length_px": round(route_length, 3),
            "horizontal_length_px": round(horizontal_length, 3),
            "vertical_length_px": round(vertical_length, 3),
            "max_vertical_segment_px": round(
                max(vertical_lengths_for_edge, default=0.0), 3
            ),
            "route_inefficiency": round(
                route_length / direct_length if direct_length > tolerance else 1.0,
                4,
            ),
            "bends": max(0, len(points_for_edge) - 2),
            "segments": max(0, len(points_for_edge) - 1),
        }
        routing_source_edges[source_name].append(edge_id)
    routing_source_statistics = {}
    for source_name, edge_ids in sorted(routing_source_edges.items()):
        points = set().union(*(edge_crossing_points[edge_id] for edge_id in edge_ids))
        source_crossed_mask = 0
        for edge_id in edge_ids:
            source_crossed_mask |= edge_crossed_owner_masks[
                edge_index_by_id[edge_id]
            ]
        routing_source_statistics[source_name] = {
            "outgoing_edges": len(edge_ids),
            "crossing_points": len(points),
            "edge_crossing_points_total": sum(
                len(edge_crossing_points[edge_id]) for edge_id in edge_ids
            ),
            "crossing_pair_incidents": sum(
                edge_crossing_pair_incidents[edge_id] for edge_id in edge_ids
            ),
            "crossed_edge_count": source_crossed_mask.bit_count(),
            "max_vertical_span_rows": max(
                routing_edge_statistics[edge_id]["vertical_span_rows"] for edge_id in edge_ids
            ),
            "max_intervening_rows": max(
                routing_edge_statistics[edge_id]["intervening_rows"] for edge_id in edge_ids
            ),
            "rendering_anchors": len({
                observed_edge_vertices[edge_id][0].cell_id for edge_id in edge_ids
            }),
            "manhattan_length_px": round(sum(
                routing_edge_statistics[edge_id]["manhattan_length_px"]
                for edge_id in edge_ids
            ), 3),
            "horizontal_length_px": round(sum(
                routing_edge_statistics[edge_id]["horizontal_length_px"]
                for edge_id in edge_ids
            ), 3),
            "vertical_length_px": round(sum(
                routing_edge_statistics[edge_id]["vertical_length_px"]
                for edge_id in edge_ids
            ), 3),
            "bends_total": sum(
                routing_edge_statistics[edge_id]["bends"] for edge_id in edge_ids
            ),
            "bends_max_per_edge": max(
                routing_edge_statistics[edge_id]["bends"] for edge_id in edge_ids
            ),
            "max_edge_length_px": max(
                routing_edge_statistics[edge_id]["manhattan_length_px"]
                for edge_id in edge_ids
            ),
        }
    logical_children: dict[str, set[str]] = defaultdict(set)
    logical_source_ports: dict[str, set[str]] = defaultdict(set)
    for source_name, source_port, target_name, _ in observed_edge_ports.values():
        logical_children[source_name].add(target_name)
        logical_source_ports[source_name].add(source_port)
    physical_anchor_counts = Counter(
        vertex.logical_name or vertex.name for vertex in document.vertices
    )
    routing_node_statistics: dict[str, dict[str, Any]] = {}
    for name in sorted(resolved):
        edge_ids = routing_source_edges.get(name, [])
        crossed_mask = 0
        for edge_id in edge_ids:
            crossed_mask |= edge_crossed_owner_masks[
                edge_index_by_id[edge_id]
            ]
        routing_node_statistics[name] = {
            "incoming_edges": logical_indegree[name],
            "outgoing_edges": logical_outdegree[name],
            "direct_downstream_nodes": len(logical_children[name]),
            "source_port_nets": len(logical_source_ports[name]),
            "rendering_anchors": physical_anchor_counts[name],
            "is_root": logical_indegree[name] == 0,
            "is_terminal": logical_outdegree[name] == 0,
            "branch_siblings": sum(
                max(0, logical_fanout[(name, port)] - 1)
                for port in logical_source_ports[name]
            ),
            "crossing_points": len(set().union(*(
                edge_crossing_points[edge_id] for edge_id in edge_ids
            ))) if edge_ids else 0,
            "crossing_pair_incidents": sum(
                edge_crossing_pair_incidents[edge_id]
                for edge_id in edge_ids
            ),
            "crossed_edge_count": crossed_mask.bit_count(),
            "manhattan_length_px": round(sum(
                routing_edge_statistics[edge_id]["manhattan_length_px"]
                for edge_id in edge_ids
            ), 3),
            "bends_total": sum(
                routing_edge_statistics[edge_id]["bends"]
                for edge_id in edge_ids
            ),
        }

    # Independently search the artifact's own visibility channels for a
    # monotone H-V-H route.  A route is rejected only when that simpler route
    # is obstacle-free and dominates the stored route without adding a
    # different-net overlap or crossing.  This makes bend/crossing quality
    # structural instead of tying it to a pixel threshold or fixture name.
    avoidable_bend_edges: list[str] = []
    avoidable_crossing_edges: list[str] = []
    avoidable_merge_input_detours: list[str] = []
    zigzag_edges: list[str] = []
    observed_indegree = Counter(
        target_name for _, _, target_name, _ in observed_edge_ports.values()
    )
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

    def nearby_node_indices(segments: list[Segment]) -> set[int]:
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
                    result.update(node_buckets.get((bx, by), ()))
        return result

    def nearby_segment_indices_for_box(
        box: tuple[float, float, float, float]
    ) -> set[int]:
        result: set[int] = set()
        for bx in range(
            math.floor(box[0] / spatial_size),
            math.floor(box[2] / spatial_size) + 1,
        ):
            for by in range(
                math.floor(box[1] / spatial_size),
                math.floor(box[3] / spatial_size) + 1,
            ):
                result.update(segment_buckets.get((bx, by), ()))
        return result

    for edge_id, points in edge_points.items():
        actual_bends = max(0, len(points) - 2)
        source_name, source_port, target_name, _ = observed_edge_ports[edge_id]
        source_vertex, target_vertex = observed_edge_vertices[edge_id]
        # A per-edge H-V-H replacement is independent only for a one-to-one
        # source net.  Replacing one branch of a shared fan-out could destroy
        # its common trunk, so fan-out alternatives are judged by the trunk
        # gate instead of this local merge-input gate.
        is_merge_input = (
            observed_indegree[target_name] > 1
            and logical_fanout[(source_name, source_port)] == 1
            and logical_outdegree[source_name] <= 2
        )
        if actual_bends < 4 and not (is_merge_input and actual_bends >= 2):
            continue
        net = (source_name, source_port)
        if logical_fanout[net] > 1:
            continue
        own_segments = edge_segments[edge_id]

        def route_cost(
            segments: list[Segment], bends: int
        ) -> tuple[int, int, int, int, float, float]:
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
                if name not in (source_vertex.name, target_vertex.name)
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
            endpoint_low, endpoint_high = sorted((points[0][1], points[-1][1]))
            route_axes = [axis for segment in segments for axis in (segment.a[1], segment.b[1])]
            outer_excursion = max(
                0.0,
                endpoint_low - min(route_axes, default=endpoint_low),
                max(route_axes, default=endpoint_high) - endpoint_high,
            )
            return hits, overlaps, crossing_count, bends, outer_excursion, length

        actual_cost = route_cost(own_segments, actual_bends)
        source_right = visual_boxes[source_vertex.name].right
        target_left = visual_boxes[target_vertex.name].left
        candidate_xs = {
            point[0]
            for point in points[1:-1]
            if source_right - tolerance <= point[0] <= target_left + tolerance
        }
        if source_right <= target_left:
            channel_left = source_right + routing_clearance
            channel_right = target_left - routing_clearance
            if channel_left <= channel_right + tolerance:
                candidate_xs.update((
                    channel_left,
                    (channel_left + channel_right) / 2.0,
                    channel_right,
                ))
        best_cost: tuple[int, int, int, int, float, float] | None = None
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
        if (
            is_merge_input
            and best_cost[1] <= actual_cost[1]
            and best_cost[2] <= actual_cost[2]
            and best_cost[3] <= actual_cost[3]
            and best_cost[4] <= actual_cost[4] + tolerance
            and (
                best_cost[2] < actual_cost[2]
                or best_cost[3] < actual_cost[3]
                or best_cost[4] < actual_cost[4] - tolerance
                or best_cost[5] < actual_cost[5] - tolerance
            )
        ):
            avoidable_merge_input_detours.append(edge_id)

    # Coordinate and route dominance is evaluated together.  Candidate axes
    # come from the artifact's incident port and route channel coordinates;
    # every incident edge is rerouted, and a move is accepted only if the
    # complete local interaction set and the visible bounding box do not
    # regress.  No component kind or instance name participates.
    avoidable_joint_coordinate_bends: list[str] = []
    joint_coordinate_tradeoffs: dict[str, list[str]] = {}
    incident_edges_by_vertex: dict[str, list[str]] = defaultdict(list)
    for edge_id, (source, target) in observed_edge_vertices.items():
        incident_edges_by_vertex[source.cell_id].append(edge_id)
        incident_edges_by_vertex[target.cell_id].append(edge_id)
    def simplify_candidate(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        points = _canonical_orthogonal_points(points, tolerance)
        compact: list[tuple[float, float]] = []
        for point in points:
            if compact and _close(point[0], compact[-1][0], tolerance) and _close(point[1], compact[-1][1], tolerance):
                continue
            compact.append(point)
            while len(compact) >= 3:
                a, b, c = compact[-3:]
                if (
                    (_close(a[0], b[0], tolerance) and _close(b[0], c[0], tolerance))
                    or (_close(a[1], b[1], tolerance) and _close(b[1], c[1], tolerance))
                ):
                    compact.pop(-2)
                else:
                    break
        return compact

    suspect_vertices: dict[str, set[float]] = defaultdict(set)
    source_ports_by_name: dict[str, set[str]] = defaultdict(set)
    incoming_by_name: dict[str, list[LogicalEdge]] = defaultdict(list)
    for logical in logical_edges:
        source_ports_by_name[logical.source].add(logical.source_port)
        incoming_by_name[logical.target].append(logical)

    def joint_coordinate_safe(name: str) -> bool:
        return all(
            not (
                logical_indegree[logical.source] == 0
                and logical_fanout[(logical.source, logical.source_port)] > 1
            )
            and len(source_ports_by_name[logical.source]) <= 1
            for logical in incoming_by_name[name]
        )

    for edge_id, points in edge_points.items():
        if max(0, len(points) - 2) < 4:
            continue
        source, target = observed_edge_vertices[edge_id]
        horizontal_axes = {
            a[1]
            for a, b in zip(points, points[1:])
            if _close(a[1], b[1], tolerance)
            and not _close(a[0], b[0], tolerance)
        }
        for vertex, endpoint in ((source, points[0]), (target, points[-1])):
            logical_name = vertex.logical_name or vertex.name
            if (
                logical_indegree[logical_name] == 0
                or logical_outdegree[logical_name] > 1
                or not joint_coordinate_safe(logical_name)
            ):
                continue
            for axis in horizontal_axes:
                if not _close(axis, endpoint[1], tolerance):
                    suspect_vertices[vertex.cell_id].add(axis - endpoint[1])

    for vertex_id in list(suspect_vertices):
        incident_ids = incident_edges_by_vertex[vertex_id]
        viable_deltas = set()
        for delta in suspect_vertices[vertex_id]:
            old_bends = sum(
                max(0, len(edge_points[edge_id]) - 2)
                for edge_id in incident_ids
            )
            best_bends = 0
            for edge_id in incident_ids:
                source, target = observed_edge_vertices[edge_id]
                points = edge_points[edge_id]
                start = (
                    points[0][0],
                    points[0][1]
                    + (delta if source.cell_id == vertex_id else 0.0),
                )
                end = (
                    points[-1][0],
                    points[-1][1]
                    + (delta if target.cell_id == vertex_id else 0.0),
                )
                best_bends += (
                    0 if _close(start[1], end[1], tolerance) else 2
                )
            if best_bends < old_bends:
                viable_deltas.add(delta)
        if viable_deltas:
            suspect_vertices[vertex_id] = viable_deltas
        else:
            del suspect_vertices[vertex_id]
    if not joint_coordinate_oracle:
        suspect_vertices.clear()

    for vertex_id, deltas in suspect_vertices.items():
        moved = vertices_by_id[vertex_id]
        moved_box = visual_boxes[moved.name]
        incident_ids = set(incident_edges_by_vertex[vertex_id])
        old_bends = sum(max(0, len(edge_points[edge_id]) - 2) for edge_id in incident_ids)
        old_segments = [
            segment
            for edge_id in incident_ids
            for segment in edge_segments[edge_id]
        ]
        old_lead_violations = sum(
            edge_id in source_lead_clearance_short
            or edge_id in target_lead_clearance_short
            or edge_id in source_lead_non_horizontal
            or edge_id in target_lead_non_horizontal
            for edge_id in incident_ids
        )
        old_nearby = [
            all_segments[index]
            for index in nearby_segment_indices(old_segments)
            if segment_edge_ids[index] not in incident_ids
        ]
        old_overlaps = sum(
            _overlap_length(segment, other) >= grid
            and segment.source_net != other.source_net
            for segment in old_segments for other in old_nearby
        )
        old_crossings = sum(
            _proper_cross(segment, other)
            for segment in old_segments for other in old_nearby
        )
        old_overlaps += sum(
            _overlap_length(segment, other) >= grid
            and segment.source_net != other.source_net
            and segment.edge_key != other.edge_key
            for index, segment in enumerate(old_segments)
            for other in old_segments[index + 1:]
        )
        old_crossings += sum(
            _proper_cross(segment, other)
            and segment.edge_key != other.edge_key
            for index, segment in enumerate(old_segments)
            for other in old_segments[index + 1:]
        )
        for delta in sorted(deltas, key=lambda value: (abs(value), value)):
            candidate_box = (
                moved_box.left,
                moved_box.top + delta,
                moved_box.right,
                moved_box.bottom + delta,
            )
            candidate_node_indices = {
                index
                for bx in range(
                    math.floor(candidate_box[0] / spatial_size),
                    math.floor(candidate_box[2] / spatial_size) + 1,
                )
                for by in range(
                    math.floor(candidate_box[1] / spatial_size),
                    math.floor(candidate_box[3] / spatial_size) + 1,
                )
                for index in node_buckets.get((bx, by), ())
            }
            if any(
                document.vertices[index].cell_id != vertex_id
                and max(candidate_box[0], visual_boxes[other.name].left)
                < min(candidate_box[2], visual_boxes[other.name].right) - tolerance
                and max(candidate_box[1], visual_boxes[other.name].top)
                < min(candidate_box[3], visual_boxes[other.name].bottom) - tolerance
                for index in candidate_node_indices
                for other in (document.vertices[index],)
            ):
                continue
            if any(
                segment_edge_ids[index] not in incident_ids
                and _segment_hits_rect(
                    all_segments[index].a,
                    all_segments[index].b,
                    candidate_box,
                )
                for index in nearby_segment_indices_for_box(candidate_box)
            ):
                continue
            candidate_segments: list[Segment] = []
            candidate_bends = 0
            candidate_lead_violations = 0
            candidate_failed = False
            selected_option_segments: list[Segment] = []
            for edge_id in sorted(incident_ids):
                source, target = observed_edge_vertices[edge_id]
                source_name, source_port, target_name, target_port = observed_edge_ports[edge_id]
                points = edge_points[edge_id]
                start = (points[0][0], points[0][1] + (delta if source.cell_id == vertex_id else 0.0))
                end = (points[-1][0], points[-1][1] + (delta if target.cell_id == vertex_id else 0.0))
                candidate_xs = {
                    a[0]
                    for a, b in zip(points, points[1:])
                    if _close(a[0], b[0], tolerance)
                    and not _close(a[1], b[1], tolerance)
                }
                if not candidate_xs:
                    candidate_xs.add((start[0] + end[0]) / 2.0)
                route_options: list[tuple[tuple[int, int, int, int, float], list[Segment]]] = []
                for x in candidate_xs:
                    option_points = simplify_candidate(
                        [start, (x, start[1]), (x, end[1]), end]
                        if not _close(start[1], end[1], tolerance)
                        else [start, end]
                    )
                    net = (source_name, source_port)
                    option_segments = [
                        Segment(edge_id, net, a, b)
                        for a, b in zip(option_points, option_points[1:])
                    ]
                    hits = 0
                    option_node_indices = nearby_node_indices(option_segments)
                    for segment in option_segments:
                        for index in option_node_indices:
                            other = document.vertices[index]
                            if other.cell_id in (source.cell_id, target.cell_id):
                                continue
                            box = candidate_box if other.cell_id == vertex_id else (
                                visual_boxes[other.name].left,
                                visual_boxes[other.name].top,
                                visual_boxes[other.name].right,
                                visual_boxes[other.name].bottom,
                            )
                            hits += int(_segment_hits_rect(segment.a, segment.b, box))
                    nearby = [
                        all_segments[index]
                        for index in nearby_segment_indices(option_segments)
                        if segment_edge_ids[index] not in incident_ids
                    ]
                    overlaps = sum(
                        _overlap_length(segment, other) >= grid
                        and segment.source_net != other.source_net
                        for segment in option_segments for other in nearby
                    )
                    crossings_count = sum(
                        _proper_cross(segment, other)
                        for segment in option_segments for other in nearby
                    )
                    overlaps += sum(
                        _overlap_length(segment, other) >= grid
                        and segment.source_net != other.source_net
                        for segment in option_segments
                        for other in selected_option_segments
                    )
                    crossings_count += sum(
                        _proper_cross(segment, other)
                        for segment in option_segments
                        for other in selected_option_segments
                    )
                    length = sum(
                        abs(segment.b[0] - segment.a[0])
                        + abs(segment.b[1] - segment.a[1])
                        for segment in option_segments
                    )
                    source_box = visual_boxes[source.name]
                    target_box = visual_boxes[target.name]
                    lead_violations = int(
                        len(option_points) > 2
                        and option_points[1][0]
                        < source_box.right + routing_clearance - tolerance
                    ) + int(
                        len(option_points) > 2
                        and option_points[-2][0]
                        > target_box.left - routing_clearance + tolerance
                    )
                    route_options.append((
                        (
                            lead_violations,
                            hits,
                            overlaps,
                            crossings_count,
                            max(0, len(option_points) - 2),
                            length,
                            tuple(option_points),
                        ),
                        option_segments,
                    ))
                option_score, option_segments = min(route_options, key=lambda item: item[0])
                if option_score[1]:
                    candidate_failed = True
                    break
                candidate_segments.extend(option_segments)
                selected_option_segments.extend(option_segments)
                candidate_bends += max(0, len(option_segments) - 1)
                candidate_lead_violations += option_score[0]
            if candidate_failed or candidate_bends >= old_bends:
                continue
            candidate_overlaps = sum(
                _overlap_length(segment, other) >= grid
                and segment.source_net != other.source_net
                for segment in candidate_segments for other in old_nearby
            )
            candidate_crossings = sum(
                _proper_cross(segment, other)
                for segment in candidate_segments for other in old_nearby
            )
            candidate_overlaps += sum(
                _overlap_length(segment, other) >= grid
                and segment.source_net != other.source_net
                and segment.edge_key != other.edge_key
                for index, segment in enumerate(candidate_segments)
                for other in candidate_segments[index + 1:]
            )
            candidate_crossings += sum(
                _proper_cross(segment, other)
                and segment.edge_key != other.edge_key
                for index, segment in enumerate(candidate_segments)
                for other in candidate_segments[index + 1:]
            )
            edge_ids = sorted(incident_ids)
            if (
                candidate_overlaps <= old_overlaps
                and candidate_crossings <= old_crossings
                and candidate_lead_violations <= old_lead_violations
            ):
                avoidable_joint_coordinate_bends.extend(edge_ids)
                break
            reasons = []
            if candidate_overlaps > old_overlaps:
                reasons.append("overlap")
            if candidate_crossings > old_crossings:
                reasons.append("crossing")
            if candidate_lead_violations > old_lead_violations:
                reasons.append("endpoint-lead")
            for edge_id in edge_ids:
                joint_coordinate_tradeoffs.setdefault(edge_id, []).extend(reasons)

    avoidable_joint_coordinate_bends = sorted(set(avoidable_joint_coordinate_bends))
    joint_coordinate_tradeoffs = {
        edge_id: sorted(set(reasons))
        for edge_id, reasons in sorted(joint_coordinate_tradeoffs.items())
    }

    # A fixed-endpoint route oracle cannot detect a dogleg that disappears
    # only after translating an exclusive upstream chain.  Independently
    # derive those chains from logical degree, translate their visible boxes
    # and incident routes, and compare the complete local interaction set.
    avoidable_exclusive_chain_bends: list[str] = []
    observed_edge_by_key = {
        _edge_key(*ports): edge_id
        for edge_id, ports in observed_edge_ports.items()
    }
    incoming_logical: dict[str, list[LogicalEdge]] = defaultdict(list)
    for logical in logical_edges:
        incoming_logical[logical.target].append(logical)

    def conflict_counts(
        segments: list[Segment],
        stationary: list[Segment],
    ) -> tuple[int, int]:
        overlaps = sum(
            _overlap_length(segment, other) >= grid
            and segment.source_net != other.source_net
            for segment in segments
            for other in stationary
        )
        crossings_count = sum(
            _proper_cross(segment, other)
            for segment in segments
            for other in stationary
        )
        overlaps += sum(
            _overlap_length(segment, other) >= grid
            and segment.source_net != other.source_net
            and segment.edge_key != other.edge_key
            for index, segment in enumerate(segments)
            for other in segments[index + 1:]
        )
        crossings_count += sum(
            _proper_cross(segment, other)
            and segment.edge_key != other.edge_key
            for index, segment in enumerate(segments)
            for other in segments[index + 1:]
        )
        return overlaps, crossings_count

    for main_edge_id, main_points in edge_points.items():
        if len(main_points) - 2 != 2:
            continue
        source_name, _, _, _ = observed_edge_ports[main_edge_id]
        if logical_outdegree[source_name] != 1:
            continue
        chain = {source_name}
        cursor = source_name
        while logical_indegree[cursor] == 1:
            parent_edge = incoming_logical[cursor][0]
            if logical_outdegree[parent_edge.source] != 1:
                break
            chain.add(parent_edge.source)
            cursor = parent_edge.source
        if logical_indegree[cursor] != 0 or any(
            len(logical_vertices[name]) != 1 for name in chain
        ):
            continue
        delta = main_points[-1][1] - main_points[0][1]
        if _close(delta, 0.0, tolerance):
            continue

        affected_logical = [
            logical for logical in logical_edges
            if logical.source in chain or logical.target in chain
        ]
        if any(logical.key not in observed_edge_by_key for logical in affected_logical):
            continue
        affected_ids = {
            observed_edge_by_key[logical.key] for logical in affected_logical
        }
        boundary_ids = [
            observed_edge_by_key[logical.key]
            for logical in affected_logical
            if logical.source not in chain and logical.target in chain
        ]
        if len(boundary_ids) > 1:
            continue
        old_bends = sum(
            max(0, len(edge_points[edge_id]) - 2)
            for edge_id in affected_ids
        )
        stationary_segments = [
            segment
            for index, segment in enumerate(all_segments)
            if segment_edge_ids[index] not in affected_ids
        ]
        old_segments = [
            segment
            for edge_id in affected_ids
            for segment in edge_segments[edge_id]
        ]
        old_overlaps, old_crossings = conflict_counts(
            old_segments, stationary_segments
        )

        channels: list[float | None] = [None]
        if boundary_ids:
            boundary_id = boundary_ids[0]
            boundary_points = edge_points[boundary_id]
            channels = [
                a[0]
                for a, b in zip(boundary_points, boundary_points[1:])
                if _close(a[0], b[0], tolerance)
                and not _close(a[1], b[1], tolerance)
            ]
            boundary_source, boundary_target = observed_edge_vertices[boundary_id]
            left = visual_boxes[boundary_source.name].right + routing_clearance
            right = visual_boxes[boundary_target.name].left - routing_clearance
            if left <= right + tolerance:
                channels.extend((left, (left + right) / 2.0, right))
            channels = list(dict.fromkeys(channels))
            if not channels:
                channels = [
                    (boundary_points[0][0] + boundary_points[-1][0]) / 2.0
                ]

        moved_cell_ids = {
            logical_vertices[name][0].cell_id for name in chain
        }
        candidate_boxes = {
            vertex.cell_id: (
                visual_boxes[vertex.name].left,
                visual_boxes[vertex.name].top
                + (delta if vertex.cell_id in moved_cell_ids else 0.0),
                visual_boxes[vertex.name].right,
                visual_boxes[vertex.name].bottom
                + (delta if vertex.cell_id in moved_cell_ids else 0.0),
            )
            for vertex in document.vertices
        }
        moved_overlap = any(
            left_id != right_id
            and (
                left_id in moved_cell_ids or right_id in moved_cell_ids
            )
            and max(candidate_boxes[left_id][0], candidate_boxes[right_id][0])
            < min(candidate_boxes[left_id][2], candidate_boxes[right_id][2]) - tolerance
            and max(candidate_boxes[left_id][1], candidate_boxes[right_id][1])
            < min(candidate_boxes[left_id][3], candidate_boxes[right_id][3]) - tolerance
            for index, left_id in enumerate(candidate_boxes)
            for right_id in list(candidate_boxes)[index + 1:]
        )
        if moved_overlap:
            continue

        for channel in channels:
            candidate_points_by_edge: dict[str, list[tuple[float, float]]] = {}
            for edge_id in affected_ids:
                source, target = observed_edge_vertices[edge_id]
                points = edge_points[edge_id]
                source_moved = source.cell_id in moved_cell_ids
                target_moved = target.cell_id in moved_cell_ids
                if edge_id == main_edge_id:
                    option = [
                        (points[0][0], points[0][1] + delta),
                        points[-1],
                    ]
                elif source_moved and target_moved:
                    option = [(x, y + delta) for x, y in points]
                else:
                    start = (
                        points[0][0],
                        points[0][1] + (delta if source_moved else 0.0),
                    )
                    end = (
                        points[-1][0],
                        points[-1][1] + (delta if target_moved else 0.0),
                    )
                    route_x = channel
                    if route_x is None:
                        route_x = (start[0] + end[0]) / 2.0
                    option = (
                        [start, end]
                        if _close(start[1], end[1], tolerance)
                        else [
                            start,
                            (route_x, start[1]),
                            (route_x, end[1]),
                            end,
                        ]
                    )
                candidate_points_by_edge[edge_id] = simplify_candidate(option)
            candidate_bends = sum(
                max(0, len(points) - 2)
                for points in candidate_points_by_edge.values()
            )
            if candidate_bends >= old_bends:
                continue

            candidate_segments_by_edge: dict[str, list[Segment]] = {}
            for edge_id, points in candidate_points_by_edge.items():
                source_name, source_port, _, _ = observed_edge_ports[edge_id]
                candidate_segments_by_edge[edge_id] = [
                    Segment(edge_id, (source_name, source_port), a, b)
                    for a, b in zip(points, points[1:])
                    if a != b
                ]
            candidate_segments = [
                segment
                for segments in candidate_segments_by_edge.values()
                for segment in segments
            ]
            candidate_hits = 0
            for edge_id, segments in candidate_segments_by_edge.items():
                source, target = observed_edge_vertices[edge_id]
                for segment in segments:
                    candidate_hits += sum(
                        _segment_hits_rect(segment.a, segment.b, box)
                        for cell_id, box in candidate_boxes.items()
                        if cell_id not in (source.cell_id, target.cell_id)
                    )
            candidate_hits += sum(
                _segment_hits_rect(segment.a, segment.b, candidate_boxes[cell_id])
                for segment in stationary_segments
                for cell_id in moved_cell_ids
            )
            if candidate_hits:
                continue
            candidate_overlaps, candidate_crossings = conflict_counts(
                candidate_segments, stationary_segments
            )
            if (
                candidate_overlaps <= old_overlaps
                and candidate_crossings <= old_crossings
            ):
                avoidable_exclusive_chain_bends.append(main_edge_id)
                break

    avoidable_exclusive_chain_bends = sorted(
        set(avoidable_exclusive_chain_bends)
    )

    direction_violations = sorted(
        edge_id
        for edge_id, _ in observed_edge_ports.items()
        for source, target in (observed_edge_vertices[edge_id],)
        if source.x >= target.x - tolerance
    )

    mux_inputs: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for edge_id, (source_name, source_port, target_name, target_port) in observed_edge_ports.items():
        source, target = observed_edge_vertices[edge_id]
        if not target_port.startswith("in"):
            continue
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
    for edge_id, (source_name, source_port, target_name, target_port) in observed_edge_ports.items():
        _, target = observed_edge_vertices[edge_id]
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
        and len(xs) > max(
            justified_trunk_counts.get((name, port), 1),
            len(logical_vertices.get(name, ())),
        )
    }

    # A sink-layer order inversion is an avoidable crossing: terminal nodes
    # have no successors constraining their vertical order, so swapping them
    # can remove the inversion without changing topology or port correctness.
    terminal_edges: list[tuple[str, float, float, tuple[str, str]]] = []
    rightmost_rank = max(ranks.values(), default=0)
    for edge_id, (source_name, source_port, target_name, target_port) in observed_edge_ports.items():
        if (
            logical_outdegree[target_name] != 0
            or ranks.get(target_name) != rightmost_rank
        ):
            continue
        source, target = observed_edge_vertices[edge_id]
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
    for edge_id, (source_name, _, target_name, target_port) in observed_edge_ports.items():
        if source_name not in root_names:
            continue
        _, target = observed_edge_vertices[edge_id]
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
    avoidable_source_replicas: list[str] = []
    for root in sorted(root_names):
        anchors = logical_vertices.get(root, [])
        if len(anchors) <= 1:
            continue
        assigned: dict[str, list[float]] = defaultdict(list)
        for edge_id, (source_name, source_port, _, target_port) in observed_edge_ports.items():
            if source_name != root:
                continue
            source, target = observed_edge_vertices[edge_id]
            target_axis = abs_port_xy(
                target.x, target.y, target.width, target.height,
                target.style, target.drawclock_type, target_port,
            )[1]
            source_anchor = port_anchors(
                source.style, source.drawclock_type
            )[source_port][1]
            assigned[source.cell_id].append(
                target_axis - source.height * source_anchor
            )
        groups = [
            (anchor.x, sorted(assigned[anchor.cell_id]))
            for anchor in anchors
            if assigned[anchor.cell_id]
        ]
        if len(groups) <= 1:
            continue
        groups.sort(key=lambda item: median(item[1]))

        def l1_cost(values: list[float]) -> float:
            pivot = median(values)
            return sum(abs(value - pivot) for value in values)

        fixed_cost = row_pitch * 3
        actual_cost = sum(l1_cost(group) for _, group in groups) + fixed_cost * len(groups)
        for index in range(len(groups) - 1):
            left_x, left_group = groups[index]
            right_x, right_group = groups[index + 1]
            if not _close(left_x, right_x, tolerance):
                continue
            merged = left_group + right_group
            merged_cost = (
                actual_cost
                - l1_cost(left_group)
                - l1_cost(right_group)
                - fixed_cost
                + l1_cost(merged)
            )
            if merged_cost <= actual_cost + tolerance:
                avoidable_source_replicas.append(
                    f"{root}:{index + 1}/{index + 2}"
                )

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
        + invalid_replicas + unused_replicas + replica_identity_errors
        + [f"avoidable-source-replica:{item}" for item in avoidable_source_replicas]
        + grid_violations + (["rank-x-spread"] if rank_x_spread_max > tolerance else [])
        + (["layout-column-misalignment"] if layout_column_misalignments else [])
        + (["layout-column-order"] if layout_column_order_violations else [])
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
        + [
            f"avoidable-joint-coordinate-bends:{edge_id}"
            for edge_id in avoidable_joint_coordinate_bends
        ]
        + [
            f"avoidable-exclusive-chain-bends:{edge_id}"
            for edge_id in avoidable_exclusive_chain_bends
        ]
        + [f"avoidable-crossing:{edge_id}" for edge_id in avoidable_crossing_edges]
        + [f"avoidable-merge-input-detour:{edge_id}" for edge_id in avoidable_merge_input_detours]
        + [
            f"avoidable-local-merge-input-crossing:{a}/{b}"
            for a, b in avoidable_local_merge_input_crossings
        ]
        + [
            f"avoidable-root-merge-input-crossing:{a}/{b}"
            for a, b in avoidable_root_merge_input_crossings
        ]
        + [f"avoidable-outer-detour:{edge_id}" for edge_id in avoidable_outer_detours]
        + [f"fragmented-fanout:{net}" for net in fragmented_fanouts]
        + [f"split-rejoin-fanout:{net}" for net in split_rejoin_fanout_nets]
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
        + [
            f"avoidable-root-layer:{item['node']}"
            for item in avoidable_root_layer_positions
        ]
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
            "invalid_rendering_replicas": invalid_replicas,
            "unused_rendering_replicas": unused_replicas,
            "replica_identity_errors": sorted(replica_identity_errors),
            "rendering_replicas": {
                name: len(vertices) - 1
                for name, vertices in sorted(logical_vertices.items())
                if len(vertices) > 1
            },
            "avoidable_source_replicas": avoidable_source_replicas,
            "duplicate_node_names": duplicate_node_names,
            "type_mismatches": type_mismatches,
            "size_mismatches": size_mismatches,
            "grid_violations": grid_violations,
            "rank_x_spread_max_px": round(rank_x_spread_max, 3),
            "rank_x_spreads_px": {key: round(value, 3) for key, value in rank_spreads.items()},
            "layout_column_misalignments": layout_column_misalignments,
            "layout_column_order_violations": layout_column_order_violations,
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
            "avoidable_joint_coordinate_bend_edges": avoidable_joint_coordinate_bends,
            "avoidable_exclusive_chain_bend_edges": avoidable_exclusive_chain_bends,
            "joint_coordinate_bend_tradeoffs": joint_coordinate_tradeoffs,
            "avoidable_crossing_edges": sorted(set(avoidable_crossing_edges)),
            "avoidable_merge_input_detours": sorted(set(avoidable_merge_input_detours)),
            "merge_input_crossings": merge_input_crossings,
            "merge_input_order_inversions": merge_input_order_inversions,
            "avoidable_local_merge_input_crossings": avoidable_local_merge_input_crossings,
            "root_merge_input_order_inversions": root_merge_input_order_inversions,
            "avoidable_root_merge_input_crossings": avoidable_root_merge_input_crossings,
            "split_rejoin_fanout_nets": sorted(split_rejoin_fanout_nets),
            "zigzag_edges": sorted(set(zigzag_edges)),
            "ambiguous_overlaps": [list(pair) for pair in ambiguous_overlaps],
            "crossings": crossing_pair_intersections,
            "distinct_crossed_edge_pairs": distinct_crossed_edge_pairs,
            "distinct_crossing_points": len(crossing_points),
            "source_induced_crossing_points": len(source_crossing_points),
            "same_net_junctions": same_net_junction_intersections,
            "untreated_crossings": [list(pair) for pair in untreated_crossings],
            "bends_total": bends_total,
            "bends_max_per_edge": bends_max,
            "manhattan_length_px": round(manhattan_length, 2),
        },
        "readability": {
            "routing_statistics": {
                "row_pitch_px": round(row_pitch, 3),
                "totals": {
                    "edges": len(routing_edge_statistics),
                    "crossing_pair_intersections": crossing_pair_intersections,
                    "distinct_crossed_edge_pairs": distinct_crossed_edge_pairs,
                    "distinct_crossing_points": len(crossing_points),
                    "source_induced_crossing_points": len(source_crossing_points),
                    "bends_total": bends_total,
                    "manhattan_length_px": round(sum(
                        item["manhattan_length_px"]
                        for item in routing_edge_statistics.values()
                    ), 3),
                    "horizontal_length_px": round(sum(
                        item["horizontal_length_px"]
                        for item in routing_edge_statistics.values()
                    ), 3),
                    "vertical_length_px": round(sum(
                        item["vertical_length_px"]
                        for item in routing_edge_statistics.values()
                    ), 3),
                },
                "edges": routing_edge_statistics,
                "nodes": routing_node_statistics,
                "sources": routing_source_statistics,
            },
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
            "avoidable_root_layer_positions": avoidable_root_layer_positions,
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


def write_quality_report(report: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
