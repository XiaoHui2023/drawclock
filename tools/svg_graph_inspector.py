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
                "length_px": round(abs(end[0] - start[0]) + abs(end[1] - start[1]), 4),
            })
        edge_rows.append({
            "id": route.edge_id,
            "source": route.source,
            "source_port": route.source_port,
            "target": route.target,
            "target_port": route.target_port,
            "points": [list(point) for point in route.points],
            "bend_points": [list(point) for point in route.points[1:-1]],
            "segments": segment_rows,
            "crossings": sorted(crossing_by_edge[route.edge_id], key=lambda item: (item["partner"], item["point"])),
            "different_net_overlaps": sorted(overlap_by_edge[route.edge_id], key=lambda item: item["partner"]),
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
        })

    return {
        "schema_version": 1,
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
