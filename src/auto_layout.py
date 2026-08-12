from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from config_input import load_config
from drawio_build import build_drawio_xml, junction_points
from drawio_layout import EdgeLayout, LAYOUT_VERSION, LayoutDocument, VertexLayout
from drawio_library import LibraryShape, canonical_object_attrs, load_library_shapes
from drawio_ports import EDGE_DRAW_STYLE, abs_port_xy, port_anchors
from from_resolve import parse_source_ref
from internal_kind import INTERNAL_OBJECT_KEYS
from library_ports import input_connection_keys, output_connection_keys, port_topology_from_style
from validate_config import validate_config


@dataclass(frozen=True)
class LayoutProfile:
    layer_spacing: float
    node_spacing: float
    margin: float
    route_clearance: float
    grid: float


PROFILES = {
    "compact": LayoutProfile(90.0, 28.0, 40.0, 10.0, 10.0),
    "balanced": LayoutProfile(115.0, 40.0, 50.0, 14.0, 10.0),
    "readable": LayoutProfile(140.0, 52.0, 60.0, 18.0, 10.0),
}

# Bound the obstacle-ranked lane search so tall trees do not grow toward
# O(edges * canvas-height * prior-segments) routing time.
MAX_ROUTE_LANES = 24


@dataclass(frozen=True)
class ResolvedNode:
    name: str
    item: dict[str, Any]
    shape: LibraryShape
    cell_id: str


@dataclass(frozen=True)
class LogicalEdge:
    source: str
    target: str
    source_port: str
    target_port: str

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_port}->{self.target}:{self.target_port}"


@dataclass(frozen=True)
class Segment:
    edge_key: str
    source_net: tuple[str, str]
    a: tuple[float, float]
    b: tuple[float, float]


def load_clock_tree(path: str | Path) -> dict[str, dict[str, Any]]:
    input_path = Path(path)
    try:
        data = load_config(input_path)
    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("不支持输入格式"):
            raise
        raise ValueError(f"无法读取拓扑配置 {input_path}：{exc}") from exc
    if not isinstance(data, dict) or any(not isinstance(value, dict) for value in data.values()):
        raise ValueError("时钟拓扑顶层必须是器件名称到属性对象的映射")
    return {str(name): dict(item) for name, item in data.items()}


def load_component_hints(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("component hints 必须是 version 1 对象")
    components = data.get("components", {})
    if not isinstance(components, dict) or any(
        not isinstance(name, str) or not isinstance(title, str)
        for name, title in components.items()
    ):
        raise ValueError("component hints 的 components 必须是名称到器件库 title 的映射")
    return dict(components)


def _source_values(item: dict[str, Any]) -> list[tuple[str | None, str]]:
    source = item.get("source")
    if source is None:
        return []
    if isinstance(source, str):
        return [(None, source)]
    if isinstance(source, dict):
        if not source:
            raise ValueError("多输入器件的 source 不能为空对象")
        return [(str(key), str(value)) for key, value in source.items()]
    raise ValueError("source 必须是字符串、对象或省略")


def _shape_title(
    name: str,
    item: dict[str, Any],
    hints: dict[str, str],
    shapes: dict[str, LibraryShape],
) -> str:
    kind = str(item.get("kind", ""))
    if not kind:
        raise ValueError(f"器件 {name} 缺少 kind")
    overrides = [
        ("component hints", hints.get(name)),
        ("component", item.get("component")),
    ]
    for field, value in overrides:
        if value is not None and str(value) != kind:
            raise ValueError(
                f"器件 {name} 的 {field}={value} 与 kind={kind} 不一致；"
                "kind 必须直接填写器件库 title"
            )
    if kind not in shapes:
        raise ValueError(f"器件 {name} 的 kind={kind} 不在当前器件库中")
    return kind


def resolve_nodes(
    config: dict[str, dict[str, Any]],
    shapes: dict[str, LibraryShape],
    hints: dict[str, str],
    *,
    library_path: str | Path,
) -> dict[str, ResolvedNode]:
    unknown_hints = sorted(set(hints) - set(config))
    if unknown_hints:
        raise ValueError(f"component hints 引用了未知器件: {', '.join(unknown_hints)}")
    nodes: dict[str, ResolvedNode] = {}
    errors: list[str] = []
    for index, (name, item) in enumerate(config.items(), 2):
        try:
            title = _shape_title(name, item, hints, shapes)
            shape = shapes.get(title)
            if shape is None:
                raise ValueError(f"器件库中不存在类型 {title}")
            nodes[name] = ResolvedNode(name, item, shape, f"n{index}")
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("\n".join(errors))
    return nodes


def _connection_port(mapping: dict[str, str], key: str, *, context: str) -> str:
    matches = [port for port, connection_key in mapping.items() if connection_key == key]
    if len(matches) != 1:
        raise ValueError(f"{context} 的连接键 [{key}] 不能唯一映射到器件端口")
    return matches[0]


def build_logical_edges(
    config: dict[str, dict[str, Any]],
    nodes: dict[str, ResolvedNode],
    library_path: str | Path,
) -> list[LogicalEdge]:
    edges: list[LogicalEdge] = []
    for target, item in config.items():
        target_node = nodes[target]
        target_topology = port_topology_from_style(target_node.shape.style)
        target_keys = input_connection_keys(target_node.shape.title, library_path=library_path)
        for input_key, raw in _source_values(item):
            source, suffix = parse_source_ref(raw)
            if source not in nodes:
                raise ValueError(f"器件 {target} 连接到未知器件 {raw}")
            source_node = nodes[source]
            source_topology = port_topology_from_style(source_node.shape.style)
            source_keys = output_connection_keys(source_node.shape.title, library_path=library_path)
            if suffix is None:
                if len(source_topology.outputs) != 1:
                    raise ValueError(
                        f"器件 {target} 引用多输出器件 {source} 时必须写输出键"
                    )
                source_port = source_topology.outputs[0]
            else:
                source_port = _connection_port(
                    source_keys, suffix, context=f"器件 {source} 输出"
                )
            if input_key is None:
                if len(target_topology.inputs) != 1:
                    raise ValueError(
                        f"器件 {target} 有多个输入端口，source 必须按输入键给出对象"
                    )
                target_port = target_topology.inputs[0]
            else:
                target_port = _connection_port(
                    target_keys, input_key, context=f"器件 {target} 输入"
                )
            edges.append(LogicalEdge(source, target, source_port, target_port))
    return edges


def _ranks(names: Iterable[str], edges: list[LogicalEdge]) -> dict[str, int]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {name: 0 for name in names}
    for edge in edges:
        outgoing[edge.source].append(edge.target)
        indegree[edge.target] += 1
    queue = deque(name for name in names if indegree[name] == 0)
    rank = {name: 0 for name in names}
    visited: list[str] = []
    while queue:
        name = queue.popleft()
        visited.append(name)
        for child in outgoing[name]:
            rank[child] = max(rank[child], rank[name] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(visited) != len(indegree):
        cyclic = sorted(name for name, degree in indegree.items() if degree > 0)
        raise ValueError(f"clock-tree 包含环路: {', '.join(cyclic)}")
    return rank


def _candidate_orders(
    config: dict[str, dict[str, Any]],
    edges: list[LogicalEdge],
    rank: dict[str, int],
    limit: int,
) -> list[dict[int, list[str]]]:
    by_rank: dict[int, list[str]] = defaultdict(list)
    for name in config:
        by_rank[rank[name]].append(name)
    parents: dict[str, list[str]] = defaultdict(list)
    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        parents[edge.target].append(edge.source)
        children[edge.source].append(edge.target)

    bases = [
        {level: list(names) for level, names in by_rank.items()},
        {level: sorted(names) for level, names in by_rank.items()},
    ]
    candidates: list[dict[int, list[str]]] = []
    seen: set[tuple[tuple[int, tuple[str, ...]], ...]] = set()
    for base_index, base in enumerate(bases + bases[:1] * 2):
        order = {level: list(names) for level, names in base.items()}
        if base_index >= 2:
            for level in order:
                if level % 2 == base_index % 2:
                    order[level].reverse()
        for _ in range(4):
            positions = {
                name: index
                for names in order.values()
                for index, name in enumerate(names)
            }
            for level in range(1, max(order, default=0) + 1):
                order[level].sort(
                    key=lambda name: (
                        _mean(positions[parent] for parent in parents[name]),
                        positions[name],
                        name,
                    )
                )
            positions = {
                name: index
                for names in order.values()
                for index, name in enumerate(names)
            }
            for level in range(max(order, default=0) - 1, -1, -1):
                order[level].sort(
                    key=lambda name: (
                        _mean(positions[child] for child in children[name]),
                        positions[name],
                        name,
                    )
                )
        key = tuple((level, tuple(order[level])) for level in sorted(order))
        if key not in seen:
            seen.add(key)
            candidates.append(order)
        if len(candidates) >= limit:
            break
    return candidates


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else math.inf


def _snap(value: float, grid: float) -> float:
    return round(value / grid) * grid


def _place_nodes(
    nodes: dict[str, ResolvedNode],
    rank: dict[str, int],
    order: dict[int, list[str]],
    profile: LayoutProfile,
    edges: list[LogicalEdge],
) -> dict[str, tuple[float, float]]:
    max_rank = max(rank.values(), default=0)
    rank_width = {
        level: max((nodes[name].shape.w for name in order[level]), default=0)
        for level in range(max_rank + 1)
    }
    rank_x: dict[int, float] = {0: profile.margin}
    for level in range(1, max_rank + 1):
        rank_x[level] = (
            rank_x[level - 1] + rank_width[level - 1] + profile.layer_spacing
        )

    incoming_edges: dict[str, list[LogicalEdge]] = defaultdict(list)
    outgoing_edges: dict[str, list[LogicalEdge]] = defaultdict(list)
    for edge in edges:
        incoming_edges[edge.target].append(edge)
        outgoing_edges[edge.source].append(edge)

    centers: dict[str, float] = {}
    max_layer_height = max(
        (
            sum(nodes[name].shape.h for name in names)
            + profile.node_spacing * max(0, len(names) - 1)
        )
        for names in order.values()
    )
    for level in range(max_rank + 1):
        names = order[level]
        total = sum(nodes[name].shape.h for name in names) + profile.node_spacing * max(0, len(names) - 1)
        cursor = profile.margin + (max_layer_height - total) / 2
        for name in names:
            centers[name] = cursor + nodes[name].shape.h / 2
            cursor += nodes[name].shape.h + profile.node_spacing

    for _ in range(3):
        for levels, edge_map, forward in (
            (range(1, max_rank + 1), incoming_edges, True),
            (range(max_rank - 1, -1, -1), outgoing_edges, False),
        ):
            for level in levels:
                names = order[level]
                desired: dict[str, float] = {}
                for name in names:
                    aligned: list[float] = []
                    for edge in edge_map[name]:
                        source = nodes[edge.source]
                        target = nodes[edge.target]
                        source_anchor = port_anchors(source.shape.style, source.shape.title)[edge.source_port][1]
                        target_anchor = port_anchors(target.shape.style, target.shape.title)[edge.target_port][1]
                        source_offset = (source_anchor - 0.5) * source.shape.h
                        target_offset = (target_anchor - 0.5) * target.shape.h
                        if forward:
                            aligned.append(centers[edge.source] + source_offset - target_offset)
                        else:
                            aligned.append(centers[edge.target] + target_offset - source_offset)
                    desired[name] = _mean(aligned)
                cursor = profile.margin
                for name in names:
                    h = nodes[name].shape.h
                    wanted_top = desired[name] - h / 2 if math.isfinite(desired[name]) else centers[name] - h / 2
                    top = max(cursor, wanted_top)
                    centers[name] = top + h / 2
                    cursor = top + h + profile.node_spacing

    return {
        name: (
            _snap(rank_x[rank[name]], profile.grid),
            _snap(centers[name] - nodes[name].shape.h / 2, profile.grid),
        )
        for name in nodes
    }


def _rects(
    nodes: dict[str, ResolvedNode],
    positions: dict[str, tuple[float, float]],
    clearance: float,
) -> dict[str, tuple[float, float, float, float]]:
    return {
        name: (
            positions[name][0] - clearance,
            positions[name][1] - clearance,
            positions[name][0] + node.shape.w + clearance,
            positions[name][1] + node.shape.h + clearance,
        )
        for name, node in nodes.items()
    }


def _segments(points: list[tuple[float, float]], edge: LogicalEdge) -> list[Segment]:
    return [
        Segment(edge.key, (edge.source, edge.source_port), a, b)
        for a, b in zip(points, points[1:])
        if a != b
    ]


def _segment_hits_rect(
    a: tuple[float, float],
    b: tuple[float, float],
    rect: tuple[float, float, float, float],
) -> bool:
    left, top, right, bottom = rect
    if a[0] == b[0]:
        x = a[0]
        lo, hi = sorted((a[1], b[1]))
        return left < x < right and max(lo, top) < min(hi, bottom)
    if a[1] == b[1]:
        y = a[1]
        lo, hi = sorted((a[0], b[0]))
        return top < y < bottom and max(lo, left) < min(hi, right)
    return True


def _proper_cross(a: Segment, b: Segment) -> bool:
    a_vertical = a.a[0] == a.b[0]
    b_vertical = b.a[0] == b.b[0]
    if a_vertical == b_vertical:
        return False
    vertical, horizontal = (a, b) if a_vertical else (b, a)
    x = vertical.a[0]
    y = horizontal.a[1]
    vy0, vy1 = sorted((vertical.a[1], vertical.b[1]))
    hx0, hx1 = sorted((horizontal.a[0], horizontal.b[0]))
    return hx0 < x < hx1 and vy0 < y < vy1


def _overlap_length(a: Segment, b: Segment) -> float:
    if a.a[0] == a.b[0] == b.a[0] == b.b[0]:
        a0, a1 = sorted((a.a[1], a.b[1]))
        b0, b1 = sorted((b.a[1], b.b[1]))
        return max(0.0, min(a1, b1) - max(a0, b0))
    if a.a[1] == a.b[1] == b.a[1] == b.b[1]:
        a0, a1 = sorted((a.a[0], a.b[0]))
        b0, b1 = sorted((b.a[0], b.b[0]))
        return max(0.0, min(a1, b1) - max(a0, b0))
    return 0.0


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for point in points:
        if out and point == out[-1]:
            continue
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (a[0] == b[0] == point[0]) or (a[1] == b[1] == point[1]):
                out[-1] = point
                continue
        out.append(point)
    return out


def _route_edges(
    nodes: dict[str, ResolvedNode],
    positions: dict[str, tuple[float, float]],
    logical_edges: list[LogicalEdge],
    profile: LayoutProfile,
) -> tuple[list[EdgeLayout], list[Segment]]:
    rects = _rects(nodes, positions, profile.route_clearance)
    all_segments: list[Segment] = []
    layouts: list[EdgeLayout] = []
    diagram_top = min(y for _, y in positions.values()) - profile.node_spacing
    diagram_bottom = max(
        positions[name][1] + node.shape.h for name, node in nodes.items()
    ) + profile.node_spacing

    outgoing_order: dict[tuple[str, str], list[str]] = defaultdict(list)
    incoming_order: dict[str, list[str]] = defaultdict(list)
    for edge in logical_edges:
        outgoing_order[(edge.source, edge.source_port)].append(edge.key)
        incoming_order[edge.target].append(edge.key)
    for keys in outgoing_order.values():
        keys.sort()
    for keys in incoming_order.values():
        keys.sort()

    edge_ids = {edge.key: f"e{index}" for index, edge in enumerate(logical_edges, 1)}
    ordered_edges = sorted(
        logical_edges,
        key=lambda edge: (
            positions[edge.target][0] - positions[edge.source][0],
            edge.target,
            edge.target_port,
        ),
    )
    for edge in ordered_edges:
        source = nodes[edge.source]
        target = nodes[edge.target]
        sx, sy = abs_port_xy(
            *positions[edge.source], source.shape.w, source.shape.h,
            source.shape.style, source.shape.title, edge.source_port,
        )
        tx, ty = abs_port_xy(
            *positions[edge.target], target.shape.w, target.shape.h,
            target.shape.style, target.shape.title, edge.target_port,
        )
        stub = min(30.0, max(profile.grid, (tx - sx) / 4))
        source_group = outgoing_order[(edge.source, edge.source_port)]
        source_lane = source_group.index(edge.key)
        target_lane = incoming_order[edge.target].index(edge.key) + source_lane
        x1 = _snap(sx + stub + source_lane * profile.grid * 2, profile.grid)
        x2 = _snap(tx - stub - target_lane * profile.grid, profile.grid)
        if x2 <= x1:
            middle = _snap((sx + tx) / 2, profile.grid)
            x1 = middle
            x2 = middle

        essential_lanes = {
            sy,
            ty,
            _snap((sy + ty) / 2, profile.grid),
            diagram_top,
            diagram_bottom,
        }
        lane_values = set(essential_lanes)
        for rect in rects.values():
            lane_values.add(_snap(rect[1] - profile.grid, profile.grid))
            lane_values.add(_snap(rect[3] + profile.grid, profile.grid))
        if len(lane_values) > MAX_ROUTE_LANES:
            midpoint = (sy + ty) / 2
            optional = sorted(
                lane_values - essential_lanes,
                key=lambda lane: (
                    sum(
                        _segment_hits_rect((x1, lane), (x2, lane), rect)
                        for name, rect in rects.items()
                        if name not in (edge.source, edge.target)
                    ),
                    abs(lane - midpoint),
                    abs(lane - sy),
                ),
            )
            lane_values = essential_lanes | set(
                optional[: MAX_ROUTE_LANES - len(essential_lanes)]
            )
        best: tuple[tuple[float, ...], list[tuple[float, float]], list[Segment]] | None = None
        for lane in sorted(lane_values):
            points = _simplify([(sx, sy), (x1, sy), (x1, lane), (x2, lane), (x2, ty), (tx, ty)])
            candidate_segments = _segments(points, edge)
            obstacle_hits = 0
            for segment in candidate_segments:
                for name, rect in rects.items():
                    if name in (edge.source, edge.target):
                        continue
                    obstacle_hits += int(_segment_hits_rect(segment.a, segment.b, rect))
            crossings = sum(
                _proper_cross(segment, prior)
                for segment in candidate_segments
                for prior in all_segments
                if segment.edge_key != prior.edge_key
            )
            ambiguous = sum(
                _overlap_length(segment, prior) >= profile.grid
                and segment.source_net != prior.source_net
                for segment in candidate_segments
                for prior in all_segments
            )
            bends = max(0, len(points) - 2)
            length = sum(
                abs(a[0] - b[0]) + abs(a[1] - b[1])
                for a, b in zip(points, points[1:])
            )
            score = (obstacle_hits, ambiguous, crossings, bends, length, abs(lane - sy))
            if best is None or score < best[0]:
                best = (score, points, candidate_segments)
        assert best is not None
        _, points, candidate_segments = best
        all_segments.extend(candidate_segments)
        source_anchor = port_anchors(source.shape.style, source.shape.title)[edge.source_port]
        target_anchor = port_anchors(target.shape.style, target.shape.title)[edge.target_port]
        style = (
            f"{EDGE_DRAW_STYLE}"
            "jumpStyle=arc;jumpSize=6;"
            f"exitX={source_anchor[0]:g};exitY={source_anchor[1]:g};"
            f"entryX={target_anchor[0]:g};entryY={target_anchor[1]:g};"
        )
        layouts.append(
            EdgeLayout(
                cell_id=edge_ids[edge.key],
                source_id=source.cell_id,
                target_id=target.cell_id,
                style=style,
                waypoints=tuple(points[1:-1]),
            )
        )
    layouts.sort(key=lambda edge: edge.cell_id)
    return layouts, all_segments


def _vertex_layouts(
    nodes: dict[str, ResolvedNode],
    positions: dict[str, tuple[float, float]],
    library_path: str | Path,
) -> list[VertexLayout]:
    vertices: list[VertexLayout] = []
    for name, node in nodes.items():
        attrs = dict(node.shape.object_defaults)
        for key, value in node.item.items():
            if key == "source" or key in INTERNAL_OBJECT_KEYS:
                continue
            attrs[key] = str(value)
        attrs["name"] = name
        attrs = canonical_object_attrs(
            node.shape.title,
            attrs,
            library_path=library_path,
        )
        x, y = positions[name]
        vertices.append(
            VertexLayout(
                name=name,
                cell_id=node.cell_id,
                drawclock_type=node.shape.title,
                x=x,
                y=y,
                width=float(node.shape.w),
                height=float(node.shape.h),
                style=node.shape.style,
                object_attrs=attrs,
            )
        )
    return sorted(vertices, key=lambda vertex: vertex.name)


def assess_layout(
    doc: LayoutDocument,
    logical_edges: list[LogicalEdge],
    runtime_ms: float,
) -> dict[str, Any]:
    by_id = {vertex.cell_id: vertex for vertex in doc.vertices}
    edge_by_id = {edge.cell_id: edge for edge in doc.edges}
    segments: list[Segment] = []
    node_overlaps = 0
    for index, a in enumerate(doc.vertices):
        for b in doc.vertices[index + 1 :]:
            if max(a.x, b.x) < min(a.x + a.width, b.x + b.width) and max(a.y, b.y) < min(a.y + a.height, b.y + b.height):
                node_overlaps += 1
    edge_node_intersections = 0
    bends_total = 0
    bends_max = 0
    length = 0.0
    for index, logical in enumerate(logical_edges, 1):
        edge = edge_by_id[f"e{index}"]
        source = by_id[edge.source_id]
        target = by_id[edge.target_id]
        start = abs_port_xy(source.x, source.y, source.width, source.height, source.style, source.drawclock_type, logical.source_port)
        end = abs_port_xy(target.x, target.y, target.width, target.height, target.style, target.drawclock_type, logical.target_port)
        points = _simplify([start, *edge.waypoints, end])
        edge_segments = _segments(points, logical)
        segments.extend(edge_segments)
        bends = max(0, len(points) - 2)
        bends_total += bends
        bends_max = max(bends_max, bends)
        length += sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(points, points[1:]))
        for segment in edge_segments:
            for vertex in doc.vertices:
                if vertex.name in (logical.source, logical.target):
                    continue
                rect = (vertex.x, vertex.y, vertex.x + vertex.width, vertex.y + vertex.height)
                edge_node_intersections += int(_segment_hits_rect(segment.a, segment.b, rect))
    crossings = 0
    ambiguous = 0
    for index, a in enumerate(segments):
        for b in segments[index + 1 :]:
            if a.edge_key == b.edge_key:
                continue
            crossings += int(_proper_cross(a, b))
            ambiguous += int(_overlap_length(a, b) >= 10.0 and a.source_net != b.source_net)
    min_x = min((vertex.x for vertex in doc.vertices), default=0.0)
    min_y = min((vertex.y for vertex in doc.vertices), default=0.0)
    max_x = max((vertex.x + vertex.width for vertex in doc.vertices), default=0.0)
    max_y = max((vertex.y + vertex.height for vertex in doc.vertices), default=0.0)
    direction_violations = sum(
        by_id[edge.source_id].x >= by_id[edge.target_id].x for edge in doc.edges
    )
    hard_pass = (
        node_overlaps == 0
        and edge_node_intersections == 0
        and ambiguous == 0
        and direction_violations == 0
    )
    return {
        "hard_pass": hard_pass,
        "nodes": len(doc.vertices),
        "edges": len(doc.edges),
        "node_overlaps": node_overlaps,
        "edge_node_intersections": edge_node_intersections,
        "direction_violations": direction_violations,
        "crossings": crossings,
        "ambiguous_overlaps": ambiguous,
        "bends_total": bends_total,
        "bends_max_per_edge": bends_max,
        "manhattan_length": round(length, 2),
        "width": round(max_x - min_x, 2),
        "height": round(max_y - min_y, 2),
        "area": round((max_x - min_x) * (max_y - min_y), 2),
        "runtime_ms": round(runtime_ms, 3),
    }


def _metric_vector(report: dict[str, Any]) -> tuple[float, ...]:
    return (
        0 if report["hard_pass"] else 1,
        report["node_overlaps"],
        report["edge_node_intersections"],
        report["ambiguous_overlaps"],
        report["crossings"],
        report["bends_total"],
        report["manhattan_length"],
        report["area"],
    )


def generate_layout(
    config: dict[str, dict[str, Any]],
    *,
    library_path: str | Path,
    component_hints: dict[str, str] | None = None,
    profile_name: str = "readable",
    candidate_limit: int = 6,
) -> tuple[LayoutDocument, dict[str, Any]]:
    started = time.perf_counter()
    if profile_name not in PROFILES:
        raise ValueError(f"未知布局 profile: {profile_name}")
    if not 1 <= candidate_limit <= 6:
        raise ValueError("candidate_limit 必须在 1..6")
    validate_config(config, library_path=library_path)
    shapes = load_library_shapes(library_path)
    nodes = resolve_nodes(
        config, shapes, component_hints or {}, library_path=library_path
    )
    logical_edges = build_logical_edges(config, nodes, library_path)
    rank = _ranks(nodes, logical_edges)
    orders = _candidate_orders(config, logical_edges, rank, candidate_limit)
    profile = PROFILES[profile_name]
    best: tuple[tuple[float, ...], LayoutDocument, dict[str, Any]] | None = None
    candidate_reports: list[dict[str, Any]] = []
    consecutive_non_improvements = 0
    for candidate_index, order in enumerate(orders, 1):
        positions = _place_nodes(nodes, rank, order, profile, logical_edges)
        edges, _ = _route_edges(nodes, positions, logical_edges, profile)
        doc = LayoutDocument(
            version=LAYOUT_VERSION,
            vertices=_vertex_layouts(nodes, positions, library_path),
            edges=edges,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        report = assess_layout(doc, logical_edges, elapsed_ms)
        report["candidate"] = candidate_index
        candidate_reports.append(report)
        vector = _metric_vector(report)
        if best is None or vector < best[0]:
            best = (vector, doc, report)
            consecutive_non_improvements = 0
        else:
            consecutive_non_improvements += 1
        if consecutive_non_improvements >= 2 and best[2]["hard_pass"]:
            break
    assert best is not None
    _, document, selected = best
    total_runtime_ms = (time.perf_counter() - started) * 1000
    final_report = dict(selected)
    final_report.update(
        {
            "runtime_ms": round(total_runtime_ms, 3),
            "profile": profile_name,
            "candidates_evaluated": len(candidate_reports),
            "candidate_stop": (
                "two-consecutive-non-improvements"
                if len(candidate_reports) < len(orders)
                else "candidate-limit"
            ),
            "selected_candidate": selected["candidate"],
            "component_types": {
                name: node.shape.title for name, node in sorted(nodes.items())
            },
            "junction_dots": len(junction_points(document)),
            "crossing_treatment": (
                "draw.io arc jump and SVG white-gap bridge"
                if selected["crossings"]
                else "not needed"
            ),
            "candidate_reports": candidate_reports,
        }
    )
    return document, final_report


def write_generated_drawio(document: LayoutDocument, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_drawio_xml(document), encoding="utf-8")
    return output
