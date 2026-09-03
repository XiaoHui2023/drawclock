#!/usr/bin/env python3
"""Independently measure feedback symptoms from a final drawclock SVG.

This file deliberately imports no drawclock production module.  It treats the
SVG as the observed user artifact and the JSON as the logical topology.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


NS = "{http://www.w3.org/2000/svg}"
EPS = 1e-4
ISSUES = (
    "FB-ROOT-001",
    "FB-ROUTE-002",
    "FB-ROOT-003",
    "FB-ROOT-004",
    "FB-BEND-005",
    "FB-PORT-006",
    "FB-ROUTE-009",
    "FB-ROOT-010",
)


@dataclass(frozen=True)
class Box:
    node: str
    x: float
    y: float
    w: float
    h: float

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def contains(self, point: tuple[float, float], tolerance: float = 0.6) -> bool:
        return (
            self.x - tolerance <= point[0] <= self.x + self.w + tolerance
            and self.y - tolerance <= point[1] <= self.y + self.h + tolerance
        )


@dataclass(frozen=True)
class LogicalEdge:
    source: str
    target: str
    target_port: str
    source_port: str = "right"


@dataclass
class Route:
    index: int
    points: list[tuple[float, float]]
    source: str = ""
    target: str = ""
    target_port: str = ""
    source_port: str = "right"

    @property
    def edge_id(self) -> str:
        return f"svg-edge-{self.index:04d}"


def _numbers(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", text)]


def simplify(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for raw in points:
        point = (round(raw[0], 4), round(raw[1], 4))
        if result and point == result[-1]:
            continue
        result.append(point)
        while len(result) >= 3:
            a, b, c = result[-3:]
            if (abs(a[0] - b[0]) <= EPS and abs(b[0] - c[0]) <= EPS) or (
                abs(a[1] - b[1]) <= EPS and abs(b[1] - c[1]) <= EPS
            ):
                result.pop(-2)
            else:
                break
    return result


def _parse_path_as_polyline(data: str) -> list[tuple[float, float]]:
    """Recover the rectilinear route from M/L and generated jump-arc paths."""
    tokens = re.findall(
        r"[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", data
    )
    points: list[tuple[float, float]] = []
    index = 0
    command = ""

    def numbers(count: int) -> list[float]:
        nonlocal index
        values = tokens[index:index + count]
        if len(values) != count or any(re.fullmatch(r"[A-Za-z]", value) for value in values):
            raise ValueError(f"invalid SVG edge path: {data}")
        index += count
        return [float(value) for value in values]

    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r"[A-Za-z]", token):
            command = token
            index += 1
        if command in {"M", "L"}:
            x, y = numbers(2)
            points.append((x, y))
            command = "L"
        elif command == "A":
            _rx, _ry, _rotation, _large_arc, _sweep, x, y = numbers(7)
            if not points or (
                abs(points[-1][0] - x) > EPS and abs(points[-1][1] - y) > EPS
            ):
                raise ValueError("Oracle rejects non-orthogonal SVG edge arcs")
            points.append((x, y))
        else:
            raise ValueError(f"Oracle rejects unsupported SVG edge command: {command}")
    if len(points) < 2:
        raise ValueError(f"invalid SVG edge path: {data}")
    return simplify(points)


def parse_svg(path: Path, node_names: set[str] | None = None) -> tuple[list[Box], list[Route]]:
    root = ET.parse(path).getroot()
    boxes: list[Box] = []
    routes: list[Route] = []
    for group in root.iter(f"{NS}g"):
        node = group.get("data-node-id")
        if not node or "component" not in (group.get("class") or "").split():
            continue
        graphic = next(
            (
                child
                for child in group
                if child.tag == f"{NS}svg"
                and "component-graphic" in (child.get("class") or "").split()
            ),
            None,
        )
        if graphic is not None:
            boxes.append(Box(node, *map(float, (
                graphic.get("x", "0"), graphic.get("y", "0"),
                graphic.get("width", "0"), graphic.get("height", "0"),
            ))))
    if not boxes and node_names:
        for foreign in root.iter(f"{NS}foreignObject"):
            tokens = {text.strip() for text in foreign.itertext() if text.strip()}
            matches = sorted(tokens.intersection(node_names))
            if len(matches) == 1:
                boxes.append(Box(matches[0], *map(float, (
                    foreign.get("x", "0"), foreign.get("y", "0"),
                    foreign.get("width", "0"), foreign.get("height", "0"),
                ))))
    for element in root.iter():
        if "edge" not in (element.get("class") or "").split():
            continue
        if element.tag == f"{NS}polyline":
            values = _numbers(element.get("points", ""))
            points = [(values[i], values[i + 1]) for i in range(0, len(values), 2)]
        elif element.tag == f"{NS}path":
            points = _parse_path_as_polyline(element.get("d", ""))
        else:
            continue
        routes.append(Route(len(routes), simplify(points)))
    if not boxes or not routes:
        raise ValueError("SVG must contain component boxes and edge polylines")
    return boxes, routes


def _source_reference(reference: str) -> tuple[str, str]:
    match = re.fullmatch(r"(.+)\[([^][]+)\]", reference)
    return (match.group(1), match.group(2)) if match else (reference, "right")


def parse_topology(path: Path) -> tuple[dict[str, dict[str, Any]], list[LogicalEdge]]:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("input JSON must be an object")
    edges: list[LogicalEdge] = []
    for target, item in config.items():
        if not isinstance(item, dict):
            raise ValueError(f"node {target} must be an object")
        source = item.get("source")
        if isinstance(source, str):
            source_name, source_port = _source_reference(source)
            edges.append(LogicalEdge(source_name, target, "left", source_port))
        elif isinstance(source, dict):
            for port, reference in source.items():
                source_name, source_port = _source_reference(str(reference))
                edges.append(LogicalEdge(source_name, target, str(port), source_port))
        elif source is not None:
            raise ValueError(f"node {target} has invalid source")
    return config, edges


def _endpoint_candidates(point: tuple[float, float], boxes: list[Box]) -> set[str]:
    inside = {box.node for box in boxes if box.contains(point)}
    if inside:
        return inside
    distance = sorted(
        (
            max(box.x - point[0], 0, point[0] - box.x - box.w) ** 2
            + max(box.y - point[1], 0, point[1] - box.y - box.h) ** 2,
            box.node,
        )
        for box in boxes
    )
    if not distance or distance[0][0] > 4.0:
        return set()
    return {name for value, name in distance if abs(value - distance[0][0]) <= EPS}


def bind_routes(routes: list[Route], boxes: list[Box], logical: list[LogicalEdge]) -> None:
    remaining = list(logical)
    starts_by_route = {route.index: _endpoint_candidates(route.points[0], boxes) for route in routes}
    ends_by_route = {route.index: _endpoint_candidates(route.points[-1], boxes) for route in routes}
    for route in routes:
        starts = starts_by_route[route.index]
        ends = ends_by_route[route.index]
        candidates = [edge for edge in remaining if edge.source in starts and edge.target in ends]
        if not candidates:
            raise ValueError(
                f"cannot bind {route.edge_id} endpoints {route.points[0]} -> {route.points[-1]} "
                f"to logical graph; inferred {sorted(starts)} -> {sorted(ends)}"
            )
        pair = (candidates[0].source, candidates[0].target)
        same_pair_all = [edge for edge in logical if (edge.source, edge.target) == pair]
        pair_routes = [
            candidate
            for candidate in routes
            if pair[0] in starts_by_route[candidate.index] and pair[1] in ends_by_route[candidate.index]
        ]
        if len(pair_routes) != len(same_pair_all):
            raise ValueError(f"ambiguous repeated source-target binding for {pair[0]} -> {pair[1]}")
        route_rank = sorted(pair_routes, key=lambda candidate: (candidate.points[-1][1], candidate.index)).index(route)
        chosen = sorted(same_pair_all, key=lambda edge: _port_order(edge.target_port))[route_rank]
        if chosen not in remaining:
            raise ValueError(f"duplicate route binding for {pair[0]} -> {pair[1]}.{chosen.target_port}")
        route.source = chosen.source
        route.target = chosen.target
        route.target_port = chosen.target_port
        route.source_port = chosen.source_port
        remaining.remove(chosen)
    if remaining:
        raise ValueError(f"SVG is missing {len(remaining)} logical edges")


def _port_order(value: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", value)
    return (int(match.group(1)) if match else -1, value)


def segments(route: Route) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(route.points, route.points[1:]))


def same_net(left: Route, right: Route) -> bool:
    return (
        left.source == right.source
        and left.source_port == right.source_port
    )


def proper_cross(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> tuple[float, float] | None:
    ah = abs(a[1] - b[1]) <= EPS and abs(a[0] - b[0]) > EPS
    ch = abs(c[1] - d[1]) <= EPS and abs(c[0] - d[0]) > EPS
    if ah == ch:
        return None
    h0, h1, v0, v1 = (a, b, c, d) if ah else (c, d, a, b)
    x, y = v0[0], h0[1]
    lo_x, hi_x = sorted((h0[0], h1[0]))
    lo_y, hi_y = sorted((v0[1], v1[1]))
    if lo_x + EPS < x < hi_x - EPS and lo_y + EPS < y < hi_y - EPS:
        return round(x, 4), round(y, 4)
    return None


def collinear_overlap(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> float:
    if abs(a[1] - b[1]) <= EPS and abs(c[1] - d[1]) <= EPS and abs(a[1] - c[1]) <= EPS:
        return max(0.0, min(max(a[0], b[0]), max(c[0], d[0])) - max(min(a[0], b[0]), min(c[0], d[0])))
    if abs(a[0] - b[0]) <= EPS and abs(c[0] - d[0]) <= EPS and abs(a[0] - c[0]) <= EPS:
        return max(0.0, min(max(a[1], b[1]), max(c[1], d[1])) - max(min(a[1], b[1]), min(c[1], d[1])))
    return 0.0


def route_crossings(routes: list[Route]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    overlaps: list[dict[str, Any]] = []
    for left_index, left in enumerate(routes):
        for right in routes[left_index + 1:]:
            shared_net = same_net(left, right)
            for li, (a, b) in enumerate(segments(left)):
                for ri, (c, d) in enumerate(segments(right)):
                    point = proper_cross(a, b, c, d)
                    if point is not None and not shared_net:
                        events.append({"point": list(point), "edges": [left.edge_id, right.edge_id], "segments": [li, ri]})
                    overlap = collinear_overlap(a, b, c, d)
                    if overlap > EPS and not shared_net:
                        overlaps.append({"length": round(overlap, 4), "edges": [left.edge_id, right.edge_id]})
    return events, overlaps


def _rect_interior_hit(a: tuple[float, float], b: tuple[float, float], box: Box) -> bool:
    if abs(a[1] - b[1]) <= EPS:
        lo, hi = sorted((a[0], b[0]))
        return box.y + EPS < a[1] < box.y + box.h - EPS and max(lo, box.x) + EPS < min(hi, box.x + box.w)
    if abs(a[0] - b[0]) <= EPS:
        lo, hi = sorted((a[1], b[1]))
        return box.x + EPS < a[0] < box.x + box.w - EPS and max(lo, box.y) + EPS < min(hi, box.y + box.h)
    return True


def _cross_count_for_segment(a: tuple[float, float], b: tuple[float, float], route: Route, routes: list[Route]) -> int:
    count = 0
    for other in routes:
        if other is route or same_net(other, route):
            continue
        count += sum(proper_cross(a, b, c, d) is not None for c, d in segments(other))
    return count


def _candidate_quality(
    points: list[tuple[float, float]], route: Route, routes: list[Route], boxes: list[Box]
) -> tuple[int, int, float] | None:
    candidate = simplify(points)
    if any(
        _rect_interior_hit(a, b, box)
        for a, b in zip(candidate, candidate[1:])
        for box in boxes
        if box.node not in {route.source, route.target}
    ):
        return None
    crossings = sum(
        proper_cross(a, b, c, d) is not None
        for a, b in zip(candidate, candidate[1:])
        for other in routes
        if other is not route and not same_net(other, route)
        for c, d in segments(other)
    )
    overlaps = sum(
        collinear_overlap(a, b, c, d) > EPS
        for a, b in zip(candidate, candidate[1:])
        for other in routes
        if other is not route and not same_net(other, route)
        for c, d in segments(other)
    )
    length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(candidate, candidate[1:]))
    return crossings, overlaps, length


def _fewer_bend_witness(
    route: Route,
    routes: list[Route],
    boxes: list[Box],
    actual_crossings: int,
    actual_overlaps: int,
) -> list[tuple[float, float]] | None:
    start, end = route.points[0], route.points[-1]
    candidates: list[list[tuple[float, float]]] = []
    if abs(start[1] - end[1]) <= EPS:
        candidates.append([start, end])
    if len(route.points) - 2 >= 3 and abs(start[1] - end[1]) > EPS:
        xs = {round((start[0] + end[0]) / 2, 4)}
        xs.update(point[0] for candidate in routes for point in candidate.points)
        for x in sorted(xs):
            if min(start[0], end[0]) + EPS < x < max(start[0], end[0]) - EPS:
                candidates.append([start, (x, start[1]), (x, end[1]), end])
    actual_bends = len(route.points) - 2
    actual_length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segments(route))
    for candidate in candidates:
        compact = simplify(candidate)
        if len(compact) - 2 >= actual_bends:
            continue
        quality = _candidate_quality(compact, route, routes, boxes)
        if quality is None:
            continue
        crossings, overlaps, length = quality
        if crossings <= actual_crossings and overlaps <= actual_overlaps and length <= actual_length + EPS:
            return compact
    return None


def _root_relocation_witness(
    route: Route, routes: list[Route], boxes: list[Box], boxes_by_node: dict[str, list[Box]]
) -> dict[str, Any] | None:
    source_boxes = boxes_by_node[route.source]
    target_boxes = boxes_by_node[route.target]
    if len(source_boxes) != 1 or not target_boxes:
        return None
    source_box = source_boxes[0]
    target_box = min(target_boxes, key=lambda box: abs(box.cy - route.points[-1][1]))
    start, end = route.points[0], route.points[-1]
    output_offset = start[0] - source_box.x
    candidate_x = end[0] - 24.0 - output_offset
    delta = candidate_x - source_box.x
    if delta <= 1.0:
        return None
    moved = Box(source_box.node, candidate_x, source_box.y, source_box.w, source_box.h)
    if any(
        box.node != route.source
        and moved.x < box.x + box.w - EPS and box.x < moved.x + moved.w - EPS
        and moved.y < box.y + box.h - EPS and box.y < moved.y + moved.h - EPS
        for box in boxes
    ):
        return None
    moved_start = (round(start[0] + delta, 4), start[1])
    if abs(moved_start[1] - end[1]) <= EPS:
        candidate = [moved_start, end]
    else:
        trunk_x = round((moved_start[0] + end[0]) / 2, 4)
        candidate = [moved_start, (trunk_x, moved_start[1]), (trunk_x, end[1]), end]
    quality = _candidate_quality(candidate, route, routes, boxes)
    if quality is None:
        return None
    new_crossings, new_overlaps, new_length = quality
    actual_crossings = _cross_count_for_route(route, routes)
    actual_overlaps = _overlap_count_for_route(route, routes)
    actual_length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segments(route))
    if new_crossings < actual_crossings and new_overlaps <= actual_overlaps and new_length < actual_length - EPS:
        return {
            "root": route.source,
            "edge_id": route.edge_id,
            "from_x": round(source_box.x, 4),
            "to_x": round(candidate_x, 4),
            "crossings_before": actual_crossings,
            "crossings_after": new_crossings,
            "length_before": round(actual_length, 4),
            "length_after": round(new_length, 4),
        }
    return None


def _cross_count_for_route(route: Route, routes: list[Route]) -> int:
    return sum(
        proper_cross(a, b, c, d) is not None
        for a, b in segments(route)
        for other in routes
        if other is not route and not same_net(other, route)
        for c, d in segments(other)
    )


def _overlap_count_for_route(route: Route, routes: list[Route]) -> int:
    return sum(
        collinear_overlap(a, b, c, d) > EPS
        for a, b in segments(route)
        for other in routes
        if other is not route and not same_net(other, route)
        for c, d in segments(other)
    )


def _endpoint_box_index(
    point: tuple[float, float], node: str, boxes: list[Box]
) -> int:
    matches = [
        index for index, box in enumerate(boxes)
        if box.node == node and box.contains(point)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"endpoint {point} for {node} resolves to {len(matches)} physical anchors"
        )
    return matches[0]


def _route_interactions(
    route: Route, others: list[Route]
) -> tuple[int, int, int]:
    points: set[tuple[float, float]] = set()
    crossing_events = 0
    overlaps = 0
    for other in others:
        if other.index == route.index or same_net(route, other):
            continue
        for a, b in segments(route):
            for c, d in segments(other):
                point = proper_cross(a, b, c, d)
                if point is not None:
                    crossing_events += 1
                    points.add(point)
                overlaps += int(collinear_overlap(a, b, c, d) > EPS)
    return len(points), crossing_events, overlaps


def _box_overlap(left: Box, right: Box) -> bool:
    return (
        left.x < right.x + right.w - EPS
        and right.x < left.x + left.w - EPS
        and left.y < right.y + right.h - EPS
        and right.y < left.y + left.h - EPS
    )


def _route_hits_unrelated_box(
    route: Route, boxes: list[Box], source_index: int, target_index: int
) -> bool:
    last_segment = len(route.points) - 2
    for segment_index, (a, b) in enumerate(segments(route)):
        for box_index, box in enumerate(boxes):
            if box_index == source_index and segment_index == 0:
                continue
            if box_index == target_index and segment_index == last_segment:
                continue
            if _rect_interior_hit(a, b, box):
                return True
    return False


def _box_is_crossed_by_routes(
    box: Box, routes: list[Route], ignored_route_index: int
) -> bool:
    return any(
        _rect_interior_hit(a, b, box)
        for route in routes
        if route.index != ignored_route_index
        for a, b in segments(route)
    )


def _copy_route(route: Route, points: list[tuple[float, float]]) -> Route:
    return Route(
        route.index,
        simplify(points),
        source=route.source,
        target=route.target,
        target_port=route.target_port,
        source_port=route.source_port,
    )


def _route_length(route: Route) -> float:
    return sum(
        abs(b[0] - a[0]) + abs(b[1] - a[1])
        for a, b in segments(route)
    )


def _root_facility_split_witnesses(
    roots: set[str], routes: list[Route], boxes: list[Box]
) -> list[dict[str, Any]]:
    """Prove that one incident route deserves its own root display facility."""
    source_box_by_route = {
        route.index: _endpoint_box_index(route.points[0], route.source, boxes)
        for route in routes
    }
    routes_by_anchor: dict[int, list[Route]] = defaultdict(list)
    for route in routes:
        if route.source in roots:
            routes_by_anchor[source_box_by_route[route.index]].append(route)
    witnesses: list[dict[str, Any]] = []
    for route in routes:
        if route.source not in roots or len(route.points) - 2 < 4:
            continue
        source_index = source_box_by_route[route.index]
        if len(routes_by_anchor[source_index]) <= 1:
            continue
        target_index = _endpoint_box_index(route.points[-1], route.target, boxes)
        source_box = boxes[source_index]
        target_box = boxes[target_index]
        output_x = route.points[0][0] - source_box.x
        output_y = route.points[0][1] - source_box.y
        clearance = max(
            1.0,
            min(source_box.w, source_box.h, target_box.w, target_box.h) / 4.0,
        )
        candidate_box = Box(
            source_box.node,
            target_box.x - clearance - source_box.w,
            route.points[-1][1] - output_y,
            source_box.w,
            source_box.h,
        )
        if candidate_box.x <= source_box.x + EPS:
            continue
        if any(_box_overlap(candidate_box, box) for box in boxes):
            continue
        candidate = _copy_route(
            route,
            [
                (candidate_box.x + output_x, candidate_box.y + output_y),
                route.points[-1],
            ],
        )
        candidate_boxes = [*boxes, candidate_box]
        if _route_hits_unrelated_box(
            candidate, candidate_boxes, len(candidate_boxes) - 1, target_index
        ):
            continue
        if _box_is_crossed_by_routes(candidate_box, routes, route.index):
            continue
        before = _route_interactions(route, routes)
        after = _route_interactions(candidate, routes)
        before_bends = len(route.points) - 2
        after_bends = len(candidate.points) - 2
        before_length = _route_length(route)
        after_length = _route_length(candidate)
        if (
            after[0] <= before[0]
            and after[1] <= before[1]
            and after[2] <= before[2]
            and after_bends < before_bends
            and after_length < before_length - EPS
        ):
            witnesses.append({
                "root": route.source,
                "edge_id": route.edge_id,
                "anchor_edges_before": len(routes_by_anchor[source_index]),
                "crossing_points_before": before[0],
                "crossing_points_after": after[0],
                "crossing_events_before": before[1],
                "crossing_events_after": after[1],
                "bends_before": before_bends,
                "bends_after": after_bends,
                "length_before": round(before_length, 4),
                "length_after": round(after_length, 4),
                "candidate_anchor": [
                    round(candidate_box.x, 4), round(candidate_box.y, 4)
                ],
            })
    return witnesses


def _physical_anchor_relocation_witnesses(
    roots: set[str], routes: list[Route], boxes: list[Box]
) -> list[dict[str, Any]]:
    """Move one physical root facility past crossed trunks, widening its suffix."""
    source_box_by_route = {
        route.index: _endpoint_box_index(route.points[0], route.source, boxes)
        for route in routes
    }
    routes_by_anchor: dict[int, list[Route]] = defaultdict(list)
    for route in routes:
        if route.source in roots:
            routes_by_anchor[source_box_by_route[route.index]].append(route)
    witnesses: list[dict[str, Any]] = []
    for route in routes:
        if route.source not in roots:
            continue
        source_index = source_box_by_route[route.index]
        if len(routes_by_anchor[source_index]) != 1:
            continue
        before = _route_interactions(route, routes)
        if before[1] == 0:
            continue
        crossed_vertical_x: list[float] = []
        for other in routes:
            if other.index == route.index or same_net(route, other):
                continue
            for a, b in segments(route):
                for c, d in segments(other):
                    if proper_cross(a, b, c, d) is None:
                        continue
                    vertical_a, _vertical_b = (
                        (a, b) if abs(a[0] - b[0]) <= EPS else (c, d)
                    )
                    crossed_vertical_x.append(vertical_a[0])
        if not crossed_vertical_x:
            continue
        target_index = _endpoint_box_index(route.points[-1], route.target, boxes)
        source_box = boxes[source_index]
        target_box = boxes[target_index]
        clearance = max(
            1.0,
            min(source_box.w, source_box.h, target_box.w, target_box.h) / 4.0,
        )
        candidate_x = max(crossed_vertical_x) + clearance
        if candidate_x <= source_box.x + EPS:
            continue
        suffix_cut = target_box.x
        suffix_shift = max(
            0.0,
            candidate_x + source_box.w + clearance - target_box.x,
        )
        candidate_boxes = [
            Box(
                box.node,
                box.x + (suffix_shift if box.x >= suffix_cut - EPS else 0.0),
                box.y,
                box.w,
                box.h,
            )
            for box in boxes
        ]
        candidate_box = Box(
            source_box.node,
            candidate_x,
            source_box.y,
            source_box.w,
            source_box.h,
        )
        candidate_boxes[source_index] = candidate_box
        if any(
            _box_overlap(candidate_box, box)
            for index, box in enumerate(candidate_boxes)
            if index != source_index
        ):
            continue
        transformed = [
            _copy_route(
                other,
                [
                    (
                        x + (suffix_shift if x >= suffix_cut - EPS else 0.0),
                        y,
                    )
                    for x, y in other.points
                ],
            )
            for other in routes
        ]
        candidate_route = next(
            other for other in transformed if other.index == route.index
        )
        output_x = route.points[0][0] - source_box.x
        start = (candidate_box.x + output_x, route.points[0][1])
        end = candidate_route.points[-1]
        candidate_route.points = simplify(
            [start, end]
            if abs(start[1] - end[1]) <= EPS
            else [
                start,
                ((start[0] + end[0]) / 2.0, start[1]),
                ((start[0] + end[0]) / 2.0, end[1]),
                end,
            ]
        )
        transformed_others = [
            other for other in transformed if other.index != route.index
        ]
        if _route_hits_unrelated_box(
            candidate_route, candidate_boxes, source_index, target_index
        ):
            continue
        if _box_is_crossed_by_routes(
            candidate_box, transformed_others, route.index
        ):
            continue
        after = _route_interactions(candidate_route, transformed_others)
        before_bends = len(route.points) - 2
        after_bends = len(candidate_route.points) - 2
        before_length = _route_length(route)
        after_length = _route_length(candidate_route)
        if (
            (after[0], after[1]) < (before[0], before[1])
            and after[2] <= before[2]
            and after_bends <= before_bends
            and after_length < before_length - EPS
        ):
            witnesses.append({
                "root": route.source,
                "edge_id": route.edge_id,
                "physical_anchor_edges": 1,
                "from_x": round(source_box.x, 4),
                "to_x": round(candidate_box.x, 4),
                "suffix_shift_px": round(suffix_shift, 4),
                "crossed_trunk_x": sorted({round(x, 4) for x in crossed_vertical_x}),
                "crossing_points_before": before[0],
                "crossing_points_after": after[0],
                "crossing_events_before": before[1],
                "crossing_events_after": after[1],
                "bends_before": before_bends,
                "bends_after": after_bends,
                "length_before": round(before_length, 4),
                "length_after": round(after_length, 4),
            })
    return witnesses


def _same_net_cycle(routes: list[Route]) -> bool:
    """Detect split/rejoin by cycles in a source net's segment arrangement."""
    raw = [segment for route in routes for segment in segments(route)]
    cuts: list[set[tuple[float, float]]] = [{a, b} for a, b in raw]
    for i, (a, b) in enumerate(raw):
        for j in range(i + 1, len(raw)):
            c, d = raw[j]
            cross = proper_cross(a, b, c, d)
            if cross is not None:
                cuts[i].add(cross)
                cuts[j].add(cross)
            for point in (a, b):
                if _point_on_segment(point, c, d):
                    cuts[j].add(point)
            for point in (c, d):
                if _point_on_segment(point, a, b):
                    cuts[i].add(point)
    graph_edges: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for (a, b), points in zip(raw, cuts):
        ordered = sorted(points, key=lambda p: (p[0], p[1]))
        for first, second in zip(ordered, ordered[1:]):
            if first != second:
                graph_edges.add(tuple(sorted((first, second))))
    parent: dict[tuple[float, float], tuple[float, float]] = {}
    def find(value: tuple[float, float]) -> tuple[float, float]:
        parent.setdefault(value, value)
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value
    for a, b in graph_edges:
        ra, rb = find(a), find(b)
        if ra == rb:
            return True
        parent[ra] = rb
    return False


def _point_on_segment(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> bool:
    if abs(a[0] - b[0]) <= EPS:
        return abs(point[0] - a[0]) <= EPS and min(a[1], b[1]) - EPS <= point[1] <= max(a[1], b[1]) + EPS
    if abs(a[1] - b[1]) <= EPS:
        return abs(point[1] - a[1]) <= EPS and min(a[0], b[0]) - EPS <= point[0] <= max(a[0], b[0]) + EPS
    return False


def analyze(input_path: Path, svg_path: Path) -> dict[str, Any]:
    config, logical = parse_topology(input_path)
    boxes, routes = parse_svg(svg_path, set(config))
    rendered_names = {box.node for box in boxes}
    missing_nodes = set(config) - rendered_names
    unexpected_nodes = rendered_names - set(config)
    if missing_nodes or unexpected_nodes:
        raise ValueError(
            f"component identity mismatch; missing={sorted(missing_nodes)}, unexpected={sorted(unexpected_nodes)}"
        )
    bind_routes(routes, boxes, logical)
    indegree = Counter(edge.target for edge in logical)
    outdegree = Counter(edge.source for edge in logical)
    roots = {name for name in config if indegree[name] == 0 and outdegree[name] > 0}
    parents: dict[str, set[str]] = defaultdict(set)
    for edge in logical:
        parents[edge.target].add(edge.source)
    root_ancestors: dict[str, set[str]] = {}
    unresolved = set(config)
    while unresolved:
        progressed = False
        for name in sorted(unresolved):
            if not parents[name]:
                root_ancestors[name] = {name} if name in roots else set()
            elif all(parent in root_ancestors for parent in parents[name]):
                root_ancestors[name] = set().union(*(root_ancestors[parent] for parent in parents[name]))
            else:
                continue
            unresolved.remove(name)
            progressed = True
            break
        if not progressed:
            raise ValueError("input graph must be acyclic")
    boxes_by_node: dict[str, list[Box]] = defaultdict(list)
    for box in boxes:
        boxes_by_node[box.node].append(box)
    crossings, overlaps = route_crossings(routes)
    incident = Counter(edge for event in crossings for edge in event["edges"])
    overlap_incident = Counter(edge for event in overlaps for edge in event["edges"])
    crossing_points_by_edge: dict[str, set[tuple[float, float]]] = defaultdict(set)
    crossing_partners_by_edge: dict[str, set[str]] = defaultdict(set)
    for event in crossings:
        left, right = event["edges"]
        point = tuple(event["point"])
        crossing_points_by_edge[left].add(point)
        crossing_points_by_edge[right].add(point)
        crossing_partners_by_edge[left].add(right)
        crossing_partners_by_edge[right].add(left)
    fanout = Counter((route.source, route.source_port) for route in routes)
    route_rows = []
    avoidable = []
    for route in routes:
        length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segments(route))
        horizontal_length = sum(
            abs(b[0] - a[0]) for a, b in segments(route)
            if abs(a[1] - b[1]) <= EPS
        )
        vertical_segments = [
            abs(b[1] - a[1]) for a, b in segments(route)
            if abs(a[0] - b[0]) <= EPS
        ]
        vertical_length = sum(vertical_segments)
        bends = max(0, len(route.points) - 2)
        witness = _fewer_bend_witness(
            route, routes, boxes, incident[route.edge_id], overlap_incident[route.edge_id]
        )
        if witness is not None:
            avoidable.append({"edge_id": route.edge_id, "candidate": [list(point) for point in witness]})
        route_rows.append({
            "edge_id": route.edge_id, "source": route.source, "target": route.target,
            "source_port": route.source_port, "target_port": route.target_port,
            "points": [list(point) for point in route.points],
            "segments": len(route.points) - 1, "bends": bends,
            "manhattan_length_px": round(length, 4),
            "horizontal_length_px": round(horizontal_length, 4),
            "vertical_length_px": round(vertical_length, 4),
            "max_vertical_segment_px": round(max(vertical_segments, default=0.0), 4),
            "crossing_points": len(crossing_points_by_edge[route.edge_id]),
            "crossing_pair_incidents": incident[route.edge_id],
            "crossed_edge_count": len(crossing_partners_by_edge[route.edge_id]),
            "source_port_fanout": fanout[(route.source, route.source_port)],
            "branch_siblings": fanout[(route.source, route.source_port)] - 1,
        })
    split_rejoin = sorted(
        f"{source}:{source_port}"
        for source, source_port in {
            (route.source, route.source_port)
            for route in routes
            if route.source in roots
        }
        if len([
            route for route in routes
            if (route.source, route.source_port) == (source, source_port)
        ]) > 1
        and _same_net_cycle([
            route for route in routes
            if (route.source, route.source_port) == (source, source_port)
        ])
    )
    root_kinds = {name: str(config[name].get("kind", "")) for name in roots}
    first_x = min(box.x for name in roots for box in boxes_by_node[name]) if roots else 0.0
    x_values = sorted({round(box.x, 3) for box in boxes})
    low_use_left_crossing = []
    root_relocation_witnesses = []
    for name in sorted(roots):
        related = [route for route in routes if route.source == name]
        if outdegree[name] != 1 or not related:
            continue
        route = related[0]
        root_x = min(box.x for box in boxes_by_node[name])
        target_x = min(box.x for box in boxes_by_node[route.target])
        intervening_columns = sum(root_x + EPS < x < target_x - EPS for x in x_values)
        if abs(root_x - first_x) <= 1.0 and intervening_columns >= 1 and incident[route.edge_id] > 0:
            low_use_left_crossing.append(name)
        relocation = _root_relocation_witness(route, routes, boxes, boxes_by_node)
        if relocation is not None:
            root_relocation_witnesses.append(relocation)
    port_inversions = []
    incoming: dict[str, list[Route]] = defaultdict(list)
    for route in routes:
        if route.source in roots and outdegree[route.source] == 1:
            incoming[route.target].append(route)
    for target, target_routes in incoming.items():
        for i, left in enumerate(target_routes):
            for right in target_routes[i + 1:]:
                source_y_left = left.points[0][1]
                source_y_right = right.points[0][1]
                target_y_left = left.points[-1][1]
                target_y_right = right.points[-1][1]
                if (source_y_left - source_y_right) * (target_y_left - target_y_right) < -EPS:
                    pair = {left.edge_id, right.edge_id}
                    if any(set(event["edges"]) == pair for event in crossings):
                        port_inversions.append({"target": target, "edges": sorted(pair)})
    # A single-use root may reach the merge through an exclusive chain. The
    # readable order invariant applies to the complete branch, not only to a
    # direct root-to-merge edge.
    for target in sorted({route.target for route in routes}):
        target_routes = [route for route in routes if route.target == target]
        attributed: list[tuple[Route, str]] = []
        for route in target_routes:
            ancestors = root_ancestors.get(route.source, set())
            if len(ancestors) == 1:
                root = next(iter(ancestors))
                if outdegree[root] == 1:
                    attributed.append((route, root))
        for i, (left, left_root) in enumerate(attributed):
            for right, right_root in attributed[i + 1:]:
                if left_root == right_root:
                    continue
                left_root_y = min(
                    (route.points[0][1] for route in routes if route.source == left_root),
                    default=boxes_by_node[left_root][0].cy,
                )
                right_root_y = min(
                    (route.points[0][1] for route in routes if route.source == right_root),
                    default=boxes_by_node[right_root][0].cy,
                )
                if (left_root_y - right_root_y) * (left.points[-1][1] - right.points[-1][1]) >= -EPS:
                    continue
                pair = {left.edge_id, right.edge_id}
                if any(set(event["edges"]) == pair for event in crossings):
                    witness = {"target": target, "roots": sorted((left_root, right_root)), "edges": sorted(pair)}
                    if witness not in port_inversions:
                        port_inversions.append(witness)
    public_root_crossings = []
    for public in roots:
        if outdegree[public] < 2:
            continue
        public_edges = {route.edge_id for route in routes if route.source == public}
        for event in crossings:
            if public_edges.intersection(event["edges"]):
                other_id = next(edge for edge in event["edges"] if edge not in public_edges)
                other = next(route for route in routes if route.edge_id == other_id)
                if other.source in roots and outdegree[other.source] == 1:
                    public_root_crossings.append({"public_root": public, "other_root": other.source, "edges": event["edges"]})
    mixed_root_quality_failures = [
        witness
        for witness in public_root_crossings
        if root_kinds.get(witness["public_root"]) not in {"source", "from"}
    ]
    root_facility_split_witnesses = _root_facility_split_witnesses(
        roots, routes, boxes
    )
    physical_anchor_relocation_witnesses = (
        _physical_anchor_relocation_witnesses(roots, routes, boxes)
    )
    detected = {
        # Mixed kinds are only a precondition.  A defect is present only when
        # an ordinary zero-indegree component also exhibits the measured root
        # placement failure; otherwise this would be an always-true coverage
        # check masquerading as a defect oracle.
        "FB-ROOT-001": (
            len(set(root_kinds.values())) >= 3
            and bool(mixed_root_quality_failures)
        ),
        "FB-ROUTE-002": bool(split_rejoin),
        "FB-ROOT-003": bool(public_root_crossings),
        "FB-ROOT-004": bool(root_relocation_witnesses),
        "FB-BEND-005": bool(avoidable),
        "FB-PORT-006": bool(port_inversions),
        "FB-ROUTE-009": bool(root_facility_split_witnesses),
        "FB-ROOT-010": bool(physical_anchor_relocation_witnesses),
    }
    route_row_by_id = {row["edge_id"]: row for row in route_rows}
    node_statistics = {}
    for name in sorted(config):
        outgoing_routes = [route for route in routes if route.source == name]
        incoming_routes = [route for route in routes if route.target == name]
        outgoing_rows = [route_row_by_id[route.edge_id] for route in outgoing_routes]
        node_statistics[name] = {
            "kind": str(config[name].get("kind", "")),
            "incoming_edges": len(incoming_routes),
            "outgoing_edges": len(outgoing_routes),
            "direct_downstream_nodes": len({route.target for route in outgoing_routes}),
            "source_port_nets": len({route.source_port for route in outgoing_routes}),
            "rendering_anchors": len(boxes_by_node[name]),
            "is_root": name in roots,
            "is_terminal": not outgoing_routes,
            "manhattan_length_px": round(sum(row["manhattan_length_px"] for row in outgoing_rows), 4),
            "bends_total": sum(row["bends"] for row in outgoing_rows),
            "crossing_points": len({
                point
                for route in outgoing_routes
                for point in crossing_points_by_edge[route.edge_id]
            }),
            "crossing_pair_incidents": sum(
                row["crossing_pair_incidents"] for row in outgoing_rows
            ),
            "crossed_edge_count": len({
                partner
                for route in outgoing_routes
                for partner in crossing_partners_by_edge[route.edge_id]
            }),
        }
    network_statistics = {}
    for source, source_port in sorted(fanout):
        net_routes = [
            route for route in routes
            if (route.source, route.source_port) == (source, source_port)
        ]
        rows = [route_row_by_id[route.edge_id] for route in net_routes]
        key = f"{source}:{source_port}"
        network_statistics[key] = {
            "source": source,
            "source_port": source_port,
            "edges": len(net_routes),
            "rendering_anchors": len({route.points[0] for route in net_routes}),
            "branch_count": max(0, len(net_routes) - 1),
            "crossing_points": len({
                point
                for route in net_routes
                for point in crossing_points_by_edge[route.edge_id]
            }),
            "crossing_pair_incidents": sum(row["crossing_pair_incidents"] for row in rows),
            "crossed_edge_count": len({
                partner
                for route in net_routes
                for partner in crossing_partners_by_edge[route.edge_id]
            }),
            "manhattan_length_px": round(sum(row["manhattan_length_px"] for row in rows), 4),
            "horizontal_length_px": round(sum(row["horizontal_length_px"] for row in rows), 4),
            "vertical_length_px": round(sum(row["vertical_length_px"] for row in rows), 4),
            "bends_total": sum(row["bends"] for row in rows),
            "bends_max_per_edge": max((row["bends"] for row in rows), default=0),
            "split_rejoin": key in split_rejoin,
        }
    return {
        "schema_version": 1,
        "input": input_path.name, "svg": svg_path.name,
        "totals": {
            "logical_nodes": len(config), "rendered_nodes": len(boxes), "logical_edges": len(logical),
            "rendered_edges": len(routes), "proper_crossing_events": len(crossings),
            "distinct_crossing_points": len({tuple(event["point"]) for event in crossings}),
            "different_net_overlaps": len(overlaps),
            "bends": sum(row["bends"] for row in route_rows),
            "manhattan_length_px": round(sum(row["manhattan_length_px"] for row in route_rows), 4),
        },
        "roots": {name: {"kind": root_kinds[name], "outdegree": outdegree[name], "rendered_copies": len(boxes_by_node[name])} for name in sorted(roots)},
        "nodes": node_statistics,
        "networks": network_statistics,
        "edges": route_rows, "crossings": crossings, "overlaps": overlaps,
        "witnesses": {
            "mixed_root_kinds": sorted(set(root_kinds.values())),
            "mixed_root_quality_failures": mixed_root_quality_failures,
            "split_rejoin_roots": split_rejoin,
            "public_root_crossings": public_root_crossings,
            "low_use_left_crossing_roots": low_use_left_crossing,
            "root_relocation_witnesses": root_relocation_witnesses,
            "avoidable_bend_edges": avoidable,
            "port_order_inversions": port_inversions,
            "root_facility_split_witnesses": root_facility_split_witnesses,
            "physical_anchor_relocation_witnesses": (
                physical_anchor_relocation_witnesses
            ),
        },
        "detected_issues": [issue for issue in ISSUES if detected[issue]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--issue", choices=ISSUES)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = analyze(args.input, args.svg)
    except (OSError, ValueError, ET.ParseError, json.JSONDecodeError) as exc:
        print(f"feedback layout oracle: invalid evidence: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if args.issue and args.issue not in report["detected_issues"]:
        print(f"feedback layout oracle: symptom not observed: {args.issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
