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


@dataclass
class Route:
    index: int
    points: list[tuple[float, float]]
    source: str = ""
    target: str = ""
    target_port: str = ""

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
    """Read M/L-only paths. Reproduction runs use crossing-style none."""
    if re.search(r"[AaCcHhQqSsTtVvZz]", data):
        raise ValueError("Oracle requires a line-only edge path; run with --crossing-style none")
    values = _numbers(data)
    if len(values) < 4 or len(values) % 2:
        raise ValueError(f"invalid line path: {data}")
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


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


def _source_name(reference: str) -> str:
    return reference.split("[", 1)[0]


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
            edges.append(LogicalEdge(_source_name(source), target, "left"))
        elif isinstance(source, dict):
            for port, reference in source.items():
                edges.append(LogicalEdge(_source_name(str(reference)), target, str(port)))
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
        route.source, route.target, route.target_port = chosen.source, chosen.target, chosen.target_port
        remaining.remove(chosen)
    if remaining:
        raise ValueError(f"SVG is missing {len(remaining)} logical edges")


def _port_order(value: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", value)
    return (int(match.group(1)) if match else -1, value)


def segments(route: Route) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(route.points, route.points[1:]))


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
            same_net = left.source == right.source
            for li, (a, b) in enumerate(segments(left)):
                for ri, (c, d) in enumerate(segments(right)):
                    point = proper_cross(a, b, c, d)
                    if point is not None and not same_net:
                        events.append({"point": list(point), "edges": [left.edge_id, right.edge_id], "segments": [li, ri]})
                    overlap = collinear_overlap(a, b, c, d)
                    if overlap > EPS and not same_net:
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
        if other is route or other.source == route.source:
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
        if other is not route and other.source != route.source
        for c, d in segments(other)
    )
    overlaps = sum(
        collinear_overlap(a, b, c, d) > EPS
        for a, b in zip(candidate, candidate[1:])
        for other in routes
        if other is not route and other.source != route.source
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
        if other is not route and other.source != route.source
        for c, d in segments(other)
    )


def _overlap_count_for_route(route: Route, routes: list[Route]) -> int:
    return sum(
        collinear_overlap(a, b, c, d) > EPS
        for a, b in segments(route)
        for other in routes
        if other is not route and other.source != route.source
        for c, d in segments(other)
    )


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
    route_rows = []
    avoidable = []
    for route in routes:
        length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segments(route))
        bends = max(0, len(route.points) - 2)
        witness = _fewer_bend_witness(
            route, routes, boxes, incident[route.edge_id], overlap_incident[route.edge_id]
        )
        if witness is not None:
            avoidable.append({"edge_id": route.edge_id, "candidate": [list(point) for point in witness]})
        route_rows.append({
            "edge_id": route.edge_id, "source": route.source, "target": route.target,
            "target_port": route.target_port, "points": [list(point) for point in route.points],
            "segments": len(route.points) - 1, "bends": bends,
            "manhattan_length_px": round(length, 4),
            "crossing_pair_incidents": incident[route.edge_id],
        })
    split_rejoin = sorted(
        source for source in roots
        if len([route for route in routes if route.source == source]) > 1
        and _same_net_cycle([route for route in routes if route.source == source])
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
    detected = {
        "FB-ROOT-001": len(set(root_kinds.values())) >= 3,
        "FB-ROUTE-002": bool(split_rejoin),
        "FB-ROOT-003": bool(public_root_crossings),
        "FB-ROOT-004": bool(root_relocation_witnesses),
        "FB-BEND-005": bool(avoidable),
        "FB-PORT-006": bool(port_inversions),
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
        "edges": route_rows, "crossings": crossings, "overlaps": overlaps,
        "witnesses": {
            "mixed_root_kinds": sorted(set(root_kinds.values())),
            "split_rejoin_roots": split_rejoin,
            "public_root_crossings": public_root_crossings,
            "low_use_left_crossing_roots": low_use_left_crossing,
            "root_relocation_witnesses": root_relocation_witnesses,
            "avoidable_bend_edges": avoidable,
            "port_order_inversions": port_inversions,
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
