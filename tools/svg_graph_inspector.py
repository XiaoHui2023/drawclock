#!/usr/bin/env python3
"""Extract complete topology and rectilinear geometry from a drawclock SVG.

This is an observation tool.  It imports no production layout module and binds
the public JSON topology to the final SVG artifact before reporting geometry.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import feedback_layout_reproduction_oracle as oracle


def _axis_index(values: list[float], value: float) -> int:
    return sorted(set(round(item, 4) for item in values)).index(round(value, 4))


def _segment_direction(
    start: tuple[float, float], end: tuple[float, float],
) -> str:
    if abs(start[1] - end[1]) <= oracle.EPS:
        return "right" if end[0] > start[0] else "left"
    if abs(start[0] - end[0]) <= oracle.EPS:
        return "down" if end[1] > start[1] else "up"
    return "non_orthogonal"


def _bounds(points: list[tuple[float, float]]) -> list[float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [
        round(min(xs), 4), round(min(ys), 4),
        round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4),
    ]


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    if abs(start[0] - end[0]) <= oracle.EPS:
        return (
            abs(point[0] - start[0]) <= oracle.EPS
            and min(start[1], end[1]) - oracle.EPS <= point[1]
            <= max(start[1], end[1]) + oracle.EPS
        )
    if abs(start[1] - end[1]) <= oracle.EPS:
        return (
            abs(point[1] - start[1]) <= oracle.EPS
            and min(start[0], end[0]) - oracle.EPS <= point[0]
            <= max(start[0], end[0]) + oracle.EPS
        )
    return False


def _network_geometry(routes: list[oracle.Route]) -> dict[str, Any]:
    """Build the visible source-port network graph from final SVG segments."""
    raw = [
        (route.edge_id, start, end)
        for route in routes
        for start, end in oracle.segments(route)
    ]
    cuts = [{start, end} for _edge_id, start, end in raw]
    for left_index, (_left_id, start, end) in enumerate(raw):
        for right_index in range(left_index + 1, len(raw)):
            _right_id, other_start, other_end = raw[right_index]
            crossing = oracle.proper_cross(
                start, end, other_start, other_end
            )
            if crossing is not None:
                cuts[left_index].add(crossing)
                cuts[right_index].add(crossing)
            for point in (start, end):
                if _point_on_segment(point, other_start, other_end):
                    cuts[right_index].add(point)
            for point in (other_start, other_end):
                if _point_on_segment(point, start, end):
                    cuts[left_index].add(point)

    graph_edges: set[
        tuple[tuple[float, float], tuple[float, float]]
    ] = set()
    for (_edge_id, start, end), points in zip(raw, cuts):
        if abs(start[0] - end[0]) <= oracle.EPS:
            ordered = sorted(points, key=lambda point: (point[1], point[0]))
        else:
            ordered = sorted(points, key=lambda point: (point[0], point[1]))
        for first, second in zip(ordered, ordered[1:]):
            if first != second:
                graph_edges.add(tuple(sorted((first, second))))

    degrees: Counter[tuple[float, float]] = Counter()
    parent: dict[tuple[float, float], tuple[float, float]] = {}

    def find(point: tuple[float, float]) -> tuple[float, float]:
        parent.setdefault(point, point)
        while parent[point] != point:
            parent[point] = parent[parent[point]]
            point = parent[point]
        return point

    for start, end in graph_edges:
        degrees[start] += 1
        degrees[end] += 1
        left_root = find(start)
        right_root = find(end)
        if left_root != right_root:
            parent[left_root] = right_root
    vertices = set(degrees)
    components = len({find(point) for point in vertices}) if vertices else 0
    cycle_rank = max(0, len(graph_edges) - len(vertices) + components)

    shared_segments = []
    for start, end in sorted(graph_edges):
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        users = sorted({
            edge_id for edge_id, raw_start, raw_end in raw
            if _point_on_segment(midpoint, raw_start, raw_end)
        })
        if len(users) >= 2:
            shared_segments.append({
                "start": list(start),
                "end": list(end),
                "orientation": (
                    "vertical" if abs(start[0] - end[0]) <= oracle.EPS
                    else "horizontal"
                ),
                "length_px": round(
                    abs(end[0] - start[0]) + abs(end[1] - start[1]), 4
                ),
                "edge_ids": users,
            })
    return {
        "vertex_count": len(vertices),
        "segment_count": len(graph_edges),
        "connected_components": components,
        "cycle_rank": cycle_rank,
        "junction_points": [
            {"point": list(point), "degree": degrees[point]}
            for point in sorted(vertices) if degrees[point] >= 3
        ],
        "leaf_points": [
            list(point) for point in sorted(vertices) if degrees[point] == 1
        ],
        "shared_segments": shared_segments,
        "shared_segment_length_px": round(
            sum(row["length_px"] for row in shared_segments), 4
        ),
    }


def inspect(input_path: Path, svg_path: Path) -> dict[str, Any]:
    config, logical = oracle.parse_topology(input_path)
    boxes, routes = oracle.parse_svg(svg_path, set(config))
    oracle.bind_routes(routes, boxes, logical)
    base = oracle.analyze(input_path, svg_path)
    crossings, overlaps = oracle.route_crossings(routes)

    boxes_by_node: dict[str, list[oracle.Box]] = defaultdict(list)
    for box in boxes:
        boxes_by_node[box.node].append(box)
    all_x = [box.x for box in boxes]
    all_y = [box.y for box in boxes]
    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for route in routes:
        incoming[route.target].append(route.edge_id)
        outgoing[route.source].append(route.edge_id)

    crossing_by_edge: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in crossings:
        left, right = event["edges"]
        crossing_by_edge[left].append({"partner": right, "point": event["point"]})
        crossing_by_edge[right].append({"partner": left, "point": event["point"]})
    overlap_by_edge: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in overlaps:
        left, right = event["edges"]
        overlap_by_edge[left].append({"partner": right, **{key: value for key, value in event.items() if key != "edges"}})
        overlap_by_edge[right].append({"partner": left, **{key: value for key, value in event.items() if key != "edges"}})

    node_rows = []
    for name in sorted(config):
        renderings = []
        for index, box in enumerate(sorted(boxes_by_node[name], key=lambda item: (item.x, item.y))):
            vx0, vy0, vx1, vy1 = box.visual_bounds
            renderings.append({
                "rendering_id": f"{name}#{index + 1}",
                "bbox": [box.x, box.y, box.w, box.h],
                "visible_bounds": [vx0, vy0, vx1 - vx0, vy1 - vy0],
                "center": [round(box.x + box.w / 2, 4), round(box.y + box.h / 2, 4)],
                "column_index": _axis_index(all_x, box.x),
                "row_index": _axis_index(all_y, box.y),
            })
        node_rows.append({
            "id": name,
            "kind": str(config[name].get("kind", "")),
            "indegree": len(incoming[name]),
            "outdegree": len(outgoing[name]),
            "incoming_edge_ids": sorted(incoming[name]),
            "outgoing_edge_ids": sorted(outgoing[name]),
            "physical_rendering_count": len(renderings),
            "renderings": renderings,
        })

    edge_rows = []
    for route in routes:
        segment_rows = []
        for index, (start, end) in enumerate(oracle.segments(route)):
            if abs(start[1] - end[1]) <= oracle.EPS:
                orientation = "horizontal"
            elif abs(start[0] - end[0]) <= oracle.EPS:
                orientation = "vertical"
            else:
                orientation = "non_orthogonal"
            segment_rows.append({
                "index": index,
                "start": list(start),
                "end": list(end),
                "orientation": orientation,
                "direction": _segment_direction(start, end),
                "length_px": round(abs(end[0] - start[0]) + abs(end[1] - start[1]), 4),
                "bounds": _bounds([start, end]),
            })
        crossing_rows = sorted(
            crossing_by_edge[route.edge_id],
            key=lambda item: (item["partner"], item["point"]),
        )
        overlap_rows = sorted(
            overlap_by_edge[route.edge_id], key=lambda item: item["partner"]
        )
        bend_rows = []
        directions = [row["direction"] for row in segment_rows]
        for index, point in enumerate(route.points[1:-1], start=1):
            bend_rows.append({
                "index": index,
                "point": list(point),
                "incoming_direction": directions[index - 1],
                "outgoing_direction": directions[index],
            })
        edge_rows.append({
            "id": route.edge_id,
            "source": route.source,
            "source_port": route.source_port,
            "target": route.target,
            "target_port": route.target_port,
            "points": [list(point) for point in route.points],
            "bounds": _bounds(route.points),
            "segment_count": len(segment_rows),
            "bend_count": len(bend_rows),
            "bend_points": bend_rows,
            "direction_sequence": directions,
            "segments": segment_rows,
            "crossing_count": len(crossing_rows),
            "crossing_points": [
                list(point) for point in sorted({
                    tuple(row["point"]) for row in crossing_rows
                })
            ],
            "crossed_edge_ids": sorted({
                row["partner"] for row in crossing_rows
            }),
            "crossings": crossing_rows,
            "different_net_overlap_count": len(overlap_rows),
            "different_net_overlap_length_px": round(sum(
                float(row["length"]) for row in overlap_rows
            ), 4),
            "different_net_overlaps": overlap_rows,
        })

    route_by_id = {route.edge_id: route for route in routes}
    networks = []
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for route in routes:
        grouped[(route.source, route.source_port)].append(route.edge_id)
    for (source, source_port), edge_ids in sorted(grouped.items()):
        members = [route_by_id[edge_id] for edge_id in edge_ids]
        starts = sorted({route.points[0] for route in members})
        vertical_xs = sorted({round(start[0], 4) for route in members for start, end in oracle.segments(route) if abs(start[0] - end[0]) <= oracle.EPS and abs(start[1] - end[1]) > oracle.EPS})
        source_bus_xs_set = set()
        for route in members:
            for start, end in oracle.segments(route):
                if (
                    abs(start[0] - end[0]) <= oracle.EPS
                    and abs(start[1] - end[1]) > oracle.EPS
                ):
                    source_bus_xs_set.add(round(start[0], 4))
                    break
        source_bus_xs = sorted(source_bus_xs_set)
        graph = _network_geometry(members)
        networks.append({
            "id": f"{source}:{source_port}",
            "source": source,
            "source_port": source_port,
            "edge_ids": sorted(edge_ids),
            "fanout": len(edge_ids),
            "start_points": [list(point) for point in starts],
            "physical_source_facilities": len({tuple(route.points[0]) for route in members}),
            "vertical_channel_xs": vertical_xs,
            "source_vertical_bus_xs": source_bus_xs,
            "branch_count": max(0, len(edge_ids) - 1),
            "split_rejoin": f"{source}:{source_port}" in base["witnesses"]["split_rejoin_roots"],
            "geometry_graph": graph,
        })

    return {
        "schema_version": 2,
        "input": str(input_path),
        "svg": str(svg_path),
        "summary": base["totals"],
        "nodes": node_rows,
        "edges": edge_rows,
        "networks": networks,
        "crossings": crossings,
        "different_net_overlaps": overlaps,
        "annotation_quality": base["annotation_quality"],
        "quality_witnesses": base["witnesses"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    payload = inspect(args.input, args.svg)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
