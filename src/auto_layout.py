from __future__ import annotations

import json
import math
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from config_input import load_config
from drawio_layout import EdgeLayout, LAYOUT_VERSION, LayoutDocument, VertexLayout
from drawio_library import (
    LibraryShape,
    LibrarySource,
    canonical_object_attrs,
    library_cache_key,
    load_library_shapes,
)
from drawio_ports import EDGE_DRAW_STYLE, abs_port_xy, port_anchors
from source_reference import parse_source_ref
from internal_kind import INTERNAL_OBJECT_KEYS
from library_ports import input_connection_keys, output_connection_keys, port_topology_from_style
from validate_config import validate_config


def _junction_count(document: LayoutDocument) -> int:
    from layout_preview import junction_points

    return len(junction_points(document))


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
    library_path: LibrarySource,
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
    library_path: LibrarySource,
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


def _layout_column_groups(
    items: dict[str, Any],
) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = defaultdict(list)
    for name, value in items.items():
        item = value.item if isinstance(value, ResolvedNode) else value
        if not isinstance(item, dict) or "layout_column" not in item:
            continue
        groups[item["layout_column"]].append(name)
    return dict(groups)


def _ranks(
    names: Iterable[str],
    edges: list[LogicalEdge],
    layout_columns: dict[int, list[str]] | None = None,
) -> dict[str, int]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    indegree = {name: 0 for name in names}
    for edge in edges:
        outgoing[edge.source].append(edge.target)
        incoming[edge.target].append(edge.source)
        indegree[edge.target] += 1
    queue = deque(name for name in names if indegree[name] == 0)
    earliest = {name: 0 for name in names}
    visited: list[str] = []
    while queue:
        name = queue.popleft()
        visited.append(name)
        for child in outgoing[name]:
            earliest[child] = max(earliest[child], earliest[name] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(visited) != len(indegree):
        cyclic = sorted(name for name, degree in indegree.items() if degree > 0)
        raise ValueError(f"clock-tree 包含环路: {', '.join(cyclic)}")

    # A low-use root feeding the same merge as a reusable root needs a real
    # intermediate layer.  Moving it after routing makes the old distribution
    # trunk look like an obstacle and traps the layout in the first column.
    # Seed the layer before the merge here, so ordering and routing see the
    # complete geometry together.  The rule uses only indegree, outdegree and
    # ancestry; component kinds and fixture names never participate.
    explicit_column_nodes = {
        name for cohort in (layout_columns or {}).values() for name in cohort
    }
    root_outdegree = {
        name: len(outgoing[name]) for name in visited if not incoming[name]
    }
    ancestor_roots: dict[str, frozenset[str]] = {}
    for name in visited:
        ancestor_roots[name] = (
            frozenset((name,))
            if not incoming[name]
            else frozenset().union(
                *(ancestor_roots[parent] for parent in incoming[name])
            )
        )
    promoted_roots = {
        root
        for root, degree in root_outdegree.items()
        if degree == 1
        and root not in explicit_column_nodes
        and any(
            other != root and root_outdegree.get(other, 0) > 1
            for other in ancestor_roots[outgoing[root][0]]
        )
    }
    distribution_roots = {
        root
        for root, degree in root_outdegree.items()
        if degree > 1
        and any(len(incoming[target]) > 1 for target in outgoing[root])
    }
    if promoted_roots:
        for name in visited:
            if not incoming[name]:
                earliest[name] = int(name in promoted_roots)
            else:
                earliest[name] = max(
                    earliest[parent] + 1 for parent in incoming[name]
                )

    # Repeated reconvergence is easier to scan when equivalent merge points
    # share a column.  Build cohorts from topology only: the complete set of
    # root ancestors plus the number of merge points already traversed.  The
    # latter keeps two causally ordered reconvergences out of the same cohort.
    # Cohorts move left only inside their common ASAP/ALAP feasibility window;
    # predecessors are then pulled left as required, so every edge still
    # advances by at least one layer.
    root_ancestors: dict[str, frozenset[str]] = {}
    merge_generation: dict[str, int] = {}
    for name in visited:
        parents = incoming[name]
        if not parents:
            root_ancestors[name] = frozenset((name,))
            merge_generation[name] = 0
            continue
        root_ancestors[name] = frozenset().union(
            *(root_ancestors[parent] for parent in parents)
        )
        merge_generation[name] = max(
            merge_generation[parent] for parent in parents
        ) + int(len(parents) > 1)
    cohorts: dict[tuple[frozenset[str], int], list[str]] = defaultdict(list)
    for name in visited:
        if len(incoming[name]) > 1:
            cohorts[(root_ancestors[name], merge_generation[name])].append(name)

    downstream_depth: dict[str, int] = {}
    for name in reversed(visited):
        downstream_depth[name] = max(
            (downstream_depth[child] + 1 for child in outgoing[name]),
            default=0,
        )

    # Build reachability summaries for the user-ranked groups in one reverse
    # DAG pass.  Equal values request one column; increasing values request
    # increasing columns.  A group that would reverse an already accepted
    # lower value remains topology-driven instead of creating a directed cycle.
    column_groups = layout_columns or {}
    column_bits = {
        level: 1 << index for index, level in enumerate(column_groups)
    }
    member_bit = {
        name: column_bits[level]
        for level, cohort in column_groups.items()
        for name in cohort
    }
    descendant_bits: dict[str, int] = {}
    conflicting_bits = 0
    for name in reversed(visited):
        bits = 0
        for child in outgoing[name]:
            bits |= member_bit.get(child, 0) | descendant_bits[child]
        conflicting_bits |= member_bit.get(name, 0) & bits
        descendant_bits[name] = bits
    feasible_columns: dict[int, list[str]] = {}
    accepted_bits = 0
    for level, cohort in sorted(column_groups.items()):
        level_bit = column_bits[level]
        same_level_conflict = bool(conflicting_bits & level_bit)
        reversed_level_conflict = any(
            descendant_bits[name] & accepted_bits for name in cohort
        )
        if same_level_conflict or reversed_level_conflict:
            continue
        feasible_columns[level] = cohort
        accepted_bits |= level_bit

    # Contract every accepted equal-level group, then add one ordering edge
    # between adjacent numeric levels.  A single longest-path pass applies both
    # equality and ordering in O(V + E + L); numeric distance is intentionally
    # ignored, so 10 and 100 do not reserve ninety columns.
    column_targets: dict[int, int] = {}
    if feasible_columns:
        member_level = {
            name: level
            for level, cohort in feasible_columns.items()
            for name in cohort
        }
        representative = {
            name: ("column", member_level[name])
            if name in member_level else ("node", name)
            for name in visited
        }
        representatives = list(dict.fromkeys(representative.values()))
        constraint_out: dict[tuple[str, Any], dict[tuple[str, Any], None]] = {
            item: {} for item in representatives
        }
        constraint_indegree = {item: 0 for item in representatives}

        def add_constraint(
            source: tuple[str, Any], target: tuple[str, Any]
        ) -> None:
            if source == target or target in constraint_out[source]:
                return
            constraint_out[source][target] = None
            constraint_indegree[target] += 1

        for edge in edges:
            add_constraint(
                representative[edge.source], representative[edge.target]
            )
        levels = list(feasible_columns)
        for left_level, right_level in zip(levels, levels[1:]):
            add_constraint(
                ("column", left_level), ("column", right_level)
            )

        constraint_queue = deque(
            item for item in representatives if constraint_indegree[item] == 0
        )
        constraint_rank = {item: 0 for item in representatives}
        for name in promoted_roots:
            constraint_rank[representative[name]] = max(
                constraint_rank[representative[name]], 1
            )
        constraint_visited = 0
        while constraint_queue:
            item = constraint_queue.popleft()
            constraint_visited += 1
            for child in constraint_out[item]:
                constraint_rank[child] = max(
                    constraint_rank[child], constraint_rank[item] + 1
                )
                constraint_indegree[child] -= 1
                if constraint_indegree[child] == 0:
                    constraint_queue.append(child)
        if constraint_visited != len(representatives):
            raise RuntimeError("layout_column constraint graph contains a cycle")
        earliest = {
            name: constraint_rank[representative[name]] for name in visited
        }
        column_targets = {
            level: constraint_rank[("column", level)]
            for level in feasible_columns
        }

    # Align every terminal on the rightmost layer, then schedule each
    # predecessor as late as its earliest consumer permits.  Equivalent merge
    # cohorts may need slack when one branch is longer before the merge and a
    # different branch is longer after it.  Add exactly that constraint-derived
    # slack; this is not a node-count or component-kind threshold.
    last_layer = max(earliest.values(), default=0)
    for cohort in cohorts.values():
        if len(cohort) > 1:
            last_layer = max(
                last_layer,
                max(earliest[name] for name in cohort)
                + max(downstream_depth[name] for name in cohort),
            )
    for cohort in feasible_columns.values():
        last_layer = max(
            last_layer,
            max(earliest[name] for name in cohort)
            + max(downstream_depth[name] for name in cohort),
        )
    latest = {name: last_layer for name in earliest}
    for name in reversed(visited):
        children = outgoing[name]
        if children:
            latest[name] = min(latest[child] - 1 for child in children)

    anchored = dict(latest)
    for cohort in cohorts.values():
        if len(cohort) < 2:
            continue
        lower = max(earliest[name] for name in cohort)
        upper = min(latest[name] for name in cohort)
        if lower <= upper:
            target = max(lower, min(latest[name] for name in cohort))
            for name in cohort:
                anchored[name] = target
    for level, cohort in feasible_columns.items():
        target = column_targets[level]
        for name in cohort:
            anchored[name] = target
    for name in reversed(visited):
        children = outgoing[name]
        if children:
            anchored[name] = min(
                anchored[name], min(anchored[child] - 1 for child in children)
            )
    for root in distribution_roots - explicit_column_nodes:
        anchored[root] = earliest[root]
    return anchored


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
    epsilon = 1e-6
    if abs(a[0] - b[0]) <= epsilon:
        x = (a[0] + b[0]) / 2.0
        lo, hi = sorted((a[1], b[1]))
        return left < x < right and max(lo, top) < min(hi, bottom)
    if abs(a[1] - b[1]) <= epsilon:
        y = (a[1] + b[1]) / 2.0
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
    tolerance = 0.01
    out: list[tuple[float, float]] = []
    for point in points:
        if out and all(abs(a - b) <= tolerance for a, b in zip(point, out[-1])):
            continue
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (
                max(a[0], b[0], point[0]) - min(a[0], b[0], point[0]) <= tolerance
                or max(a[1], b[1], point[1]) - min(a[1], b[1], point[1]) <= tolerance
            ):
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
            points = _simplify([
                (sx, sy), (x1, sy), (x1, lane),
                (x2, lane), (x2, ty), (tx, ty),
            ])
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
                _overlap_length(segment, prior) > 1e-6
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
    library_path: LibrarySource,
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
    *,
    include_routing_statistics: bool = False,
    reject_geometry_worse_than: tuple[int, int] | None = None,
    reuse_hard_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by_id = {vertex.cell_id: vertex for vertex in doc.vertices}
    edge_by_id = {edge.cell_id: edge for edge in doc.edges}
    bucket_size = 256.0

    def bucket_keys(
        left: float, top: float, right: float, bottom: float
    ) -> Iterable[tuple[int, int]]:
        for bx in range(math.floor(left / bucket_size), math.floor(right / bucket_size) + 1):
            for by in range(math.floor(top / bucket_size), math.floor(bottom / bucket_size) + 1):
                yield bx, by

    node_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    node_rects: list[tuple[float, float, float, float]] = []
    overlap_pairs: set[tuple[int, int]] = set()
    if reuse_hard_metrics is None:
        node_rects = [
            (vertex.x, vertex.y, vertex.x + vertex.width, vertex.y + vertex.height)
            for vertex in doc.vertices
        ]
        for index, rect in enumerate(node_rects):
            for key in bucket_keys(*rect):
                node_buckets[key].append(index)
        for index, rect in enumerate(node_rects):
            nearby: set[int] = set()
            for key in bucket_keys(*rect):
                nearby.update(node_buckets[key])
            for other_index in nearby:
                if other_index <= index:
                    continue
                other = node_rects[other_index]
                if (
                    max(rect[0], other[0]) < min(rect[2], other[2])
                    and max(rect[1], other[1]) < min(rect[3], other[3])
                ):
                    overlap_pairs.add((index, other_index))
    segments: list[Segment] = []
    segment_edge_ids: list[str] = []
    segment_endpoints: list[tuple[str, str]] = []
    node_overlaps = (
        int(reuse_hard_metrics["node_overlaps"])
        if reuse_hard_metrics is not None else len(overlap_pairs)
    )
    edge_node_intersections = (
        int(reuse_hard_metrics["edge_node_intersections"])
        if reuse_hard_metrics is not None else 0
    )
    bends_total = 0
    bends_max = 0
    length = 0.0
    edge_route_metrics: dict[str, dict[str, float | int]] = {}
    for index, logical in enumerate(logical_edges, 1):
        edge = edge_by_id[f"e{index}"]
        source = by_id[edge.source_id]
        target = by_id[edge.target_id]
        start = abs_port_xy(source.x, source.y, source.width, source.height, source.style, source.drawclock_type, logical.source_port)
        end = abs_port_xy(target.x, target.y, target.width, target.height, target.style, target.drawclock_type, logical.target_port)
        points = _simplify([start, *edge.waypoints, end])
        edge_segments = _segments(points, logical)
        segments.extend(edge_segments)
        segment_edge_ids.extend([edge.cell_id] * len(edge_segments))
        segment_endpoints.extend(
            [(edge.source_id, edge.target_id)] * len(edge_segments)
        )
        bends = max(0, len(points) - 2)
        bends_total += bends
        bends_max = max(bends_max, bends)
        horizontal_length = 0.0
        vertical_length = 0.0
        max_vertical_length = 0.0
        for a, b in zip(points, points[1:]):
            if abs(a[1] - b[1]) <= 1e-6:
                horizontal_length += abs(a[0] - b[0])
            elif abs(a[0] - b[0]) <= 1e-6:
                segment_length = abs(a[1] - b[1])
                vertical_length += segment_length
                max_vertical_length = max(max_vertical_length, segment_length)
        route_length = horizontal_length + vertical_length
        if include_routing_statistics:
            direct_length = (
                abs(points[-1][0] - points[0][0])
                + abs(points[-1][1] - points[0][1])
            )
            edge_route_metrics[edge.cell_id] = {
                "manhattan_length_px": round(route_length, 3),
                "horizontal_length_px": round(horizontal_length, 3),
                "vertical_length_px": round(vertical_length, 3),
                "max_vertical_segment_px": round(max_vertical_length, 3),
                "route_inefficiency": round(
                    route_length / direct_length if direct_length > 1e-6 else 1.0,
                    4,
                ),
                "bends": bends,
                "segments": max(0, len(points) - 1),
            }
        length += route_length
    if reuse_hard_metrics is None:
        for segment, endpoints in zip(segments, segment_endpoints):
            nearby: set[int] = set()
            left, right = sorted((segment.a[0], segment.b[0]))
            top, bottom = sorted((segment.a[1], segment.b[1]))
            for key in bucket_keys(left, top, right, bottom):
                nearby.update(node_buckets.get(key, ()))
            edge_node_intersections += sum(
                _segment_hits_rect(segment.a, segment.b, node_rects[index])
                for index in nearby
                if doc.vertices[index].cell_id not in endpoints
            )
    if reject_geometry_worse_than is not None and (
        node_overlaps > reject_geometry_worse_than[0]
        or edge_node_intersections > reject_geometry_worse_than[1]
    ):
        return {
            "geometry_short_circuit": True,
            "node_overlaps": node_overlaps,
            "edge_node_intersections": edge_node_intersections,
        }
    # Collapse geometrically identical shared trunks, then use an orthogonal
    # sweep.  The previous square buckets still generated millions of segment
    # pairs for large fanout trees even though only a few trunks were visible.
    grouped: dict[
        tuple[str, float, float, float, tuple[str, str]],
        tuple[Segment, set[str]],
    ] = {}
    for segment, edge_id in zip(segments, segment_edge_ids):
        if abs(segment.a[0] - segment.b[0]) <= 1e-6:
            low, high = sorted((segment.a[1], segment.b[1]))
            key = ("v", segment.a[0], low, high, segment.source_net)
        else:
            low, high = sorted((segment.a[0], segment.b[0]))
            key = ("h", segment.a[1], low, high, segment.source_net)
        if key not in grouped:
            grouped[key] = (segment, set())
        grouped[key][1].add(edge_id)

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
            math.floor(x0 / bucket_size),
            math.floor(x1 / bucket_size) + 1,
        ):
            horizontal_by_cell[(bx, segment.a[1])].append(item)
    horizontal_ys = sorted(horizontal_by_y)
    for intervals in horizontal_by_y.values():
        intervals.sort(key=lambda item: item[0])

    crossings = 0
    crossing_points: set[tuple[float, float]] = set()
    source_crossing_points: set[tuple[float, float]] = set()
    edge_crossing_points: dict[str, set[tuple[float, float]]] = defaultdict(set)
    edge_crossing_pair_incidents: Counter[str] = Counter()
    edge_index_by_id = {
        f"e{index}": index - 1 for index in range(1, len(logical_edges) + 1)
    }
    edge_crossed_owner_masks = [0] * len(logical_edges)
    grouped_crossing_points: dict[int, set[tuple[float, float]]] = defaultdict(set)
    grouped_pair_incidents: Counter[int] = Counter()
    grouped_owner_adjustments: Counter[tuple[int, str]] = Counter()
    logical_indegree = Counter(edge.target for edge in logical_edges)
    root_names = {
        name
        for name in {edge.source for edge in logical_edges}
        if logical_indegree[name] == 0
    }
    for vertical, vertical_owners in verticals:
        x = vertical.a[0]
        y0, y1 = sorted((vertical.a[1], vertical.b[1]))
        for y in horizontal_ys[
            bisect_right(horizontal_ys, y0):bisect_left(horizontal_ys, y1)
        ]:
            for x0, x1, horizontal, horizontal_owners in horizontal_by_cell.get(
                (math.floor(x / bucket_size), y), ()
            ):
                if x0 >= x or x >= x1 or vertical.source_net == horizontal.source_net:
                    continue
                crossings += (
                    len(vertical_owners) * len(horizontal_owners)
                    - len(vertical_owners & horizontal_owners)
                )
                point = (round(x, 3), round(y, 3))
                crossing_points.add(point)
                if include_routing_statistics:
                    vertical_key = id(vertical)
                    horizontal_key = id(horizontal)
                    grouped_crossing_points[vertical_key].add(point)
                    grouped_crossing_points[horizontal_key].add(point)
                    grouped_pair_incidents[vertical_key] += len(horizontal_owners)
                    grouped_pair_incidents[horizontal_key] += len(vertical_owners)
                    for shared_edge in vertical_owners & horizontal_owners:
                        grouped_owner_adjustments[(vertical_key, shared_edge)] += 1
                        grouped_owner_adjustments[(horizontal_key, shared_edge)] += 1
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
                if (
                    vertical.source_net[0] in root_names
                    or horizontal.source_net[0] in root_names
                ):
                    source_crossing_points.add(point)

    if include_routing_statistics:
        for segment, owners in (*verticals, *horizontals):
            group_key = id(segment)
            points = grouped_crossing_points.get(group_key)
            incidents = grouped_pair_incidents[group_key]
            for edge_id in owners:
                if points:
                    edge_crossing_points[edge_id].update(points)
                edge_crossing_pair_incidents[edge_id] += (
                    incidents - grouped_owner_adjustments[(group_key, edge_id)]
                )
    distinct_crossed_edge_pairs = sum(
        owner_mask.bit_count() for owner_mask in edge_crossed_owner_masks
    ) // 2

    ambiguous = (
        int(reuse_hard_metrics["ambiguous_overlaps"])
        if reuse_hard_metrics is not None else 0
    )
    parallel: dict[
        tuple[str, float], list[tuple[Segment, set[str]]],
    ] = defaultdict(list)
    if reuse_hard_metrics is None:
        for segment, owners in verticals:
            parallel[("v", segment.a[0])].append((segment, owners))
        for segment, owners in horizontals:
            parallel[("h", segment.a[1])].append((segment, owners))
    for group in parallel.values():
        intervals = []
        for segment, owners in group:
            values = (
                (segment.a[1], segment.b[1])
                if abs(segment.a[0] - segment.b[0]) <= 1e-6
                else (segment.a[0], segment.b[0])
            )
            low, high = sorted(values)
            intervals.append((low, high, segment, owners))
        intervals.sort(key=lambda item: item[0])
        active: list[tuple[float, Segment, set[str]]] = []
        minimum_overlap = 1e-6
        for low, high, segment, owners in intervals:
            active = [
                item for item in active
                if item[0] - low > minimum_overlap
            ]
            for other_high, other, other_owners in active:
                if segment.source_net == other.source_net:
                    continue
                if min(high, other_high) - low <= minimum_overlap:
                    continue
                ambiguous += (
                    len(owners) * len(other_owners)
                    - len(owners & other_owners)
                )
            active.append((high, segment, owners))
    min_x = min((vertex.x for vertex in doc.vertices), default=0.0)
    min_y = min((vertex.y for vertex in doc.vertices), default=0.0)
    max_x = max((vertex.x + vertex.width for vertex in doc.vertices), default=0.0)
    max_y = max((vertex.y + vertex.height for vertex in doc.vertices), default=0.0)
    direction_violations = (
        int(reuse_hard_metrics["direction_violations"])
        if reuse_hard_metrics is not None
        else sum(by_id[edge.source_id].x >= by_id[edge.target_id].x for edge in doc.edges)
    )
    routing_statistics = None
    if include_routing_statistics:
        raw_row_centers = sorted({
            round(vertex.y + vertex.height / 2.0, 6)
            for vertex in doc.vertices
        })
        median_height = median(
            [vertex.height for vertex in doc.vertices] or [1.0]
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
            if right - left > 1e-6
        ]
        # Cap a sparse artifact's observed gap by a geometry-derived pitch.
        geometry_pitch = max(1.0, median_height * 2.0)
        row_pitch = (
            max(median_height, min(median(row_deltas), geometry_pitch))
            if row_deltas else geometry_pitch
        )
        edge_statistics: dict[str, dict[str, Any]] = {}
        source_statistics: dict[str, dict[str, Any]] = {}
        source_edge_ids: dict[str, list[str]] = defaultdict(list)
        logical_indegree = Counter(edge.target for edge in logical_edges)
        logical_outdegree = Counter(edge.source for edge in logical_edges)
        logical_children: dict[str, set[str]] = defaultdict(set)
        logical_source_ports: dict[str, set[str]] = defaultdict(set)
        net_fanout = Counter(
            (edge.source, edge.source_port) for edge in logical_edges
        )
        logical_names = sorted({
            vertex.logical_name or vertex.name for vertex in doc.vertices
        })
        physical_anchor_counts = Counter(
            vertex.logical_name or vertex.name for vertex in doc.vertices
        )
        for index, logical in enumerate(logical_edges, 1):
            edge_id = f"e{index}"
            edge = edge_by_id[edge_id]
            source = by_id[edge.source_id]
            target = by_id[edge.target_id]
            start = abs_port_xy(
                source.x, source.y, source.width, source.height,
                source.style, source.drawclock_type, logical.source_port,
            )
            end = abs_port_xy(
                target.x, target.y, target.width, target.height,
                target.style, target.drawclock_type, logical.target_port,
            )
            low, high = sorted((start[1], end[1]))
            edge_statistics[edge_id] = {
                "source": logical.source,
                "target": logical.target,
                "crossing_points": len(edge_crossing_points[edge_id]),
                "crossing_pair_incidents": edge_crossing_pair_incidents[edge_id],
                "crossed_edge_count": edge_crossed_owner_masks[
                    edge_index_by_id[edge_id]
                ].bit_count(),
                "source_port_fanout": net_fanout[
                    (logical.source, logical.source_port)
                ],
                "branch_siblings": max(
                    0,
                    net_fanout[(logical.source, logical.source_port)] - 1,
                ),
                "vertical_span_px": round(high - low, 3),
                "vertical_span_rows": round((high - low) / row_pitch, 3),
                "intervening_rows": max(
                    0,
                    bisect_left(row_centers, high)
                    - bisect_right(row_centers, low),
                ),
                **edge_route_metrics[edge_id],
            }
            source_edge_ids[logical.source].append(edge_id)
            logical_children[logical.source].add(logical.target)
            logical_source_ports[logical.source].add(logical.source_port)
        for source, edge_ids in sorted(source_edge_ids.items()):
            points = set().union(*(edge_crossing_points[edge_id] for edge_id in edge_ids))
            source_crossed_mask = 0
            for edge_id in edge_ids:
                source_crossed_mask |= edge_crossed_owner_masks[
                    edge_index_by_id[edge_id]
                ]
            source_statistics[source] = {
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
                    edge_statistics[edge_id]["vertical_span_rows"] for edge_id in edge_ids
                ),
                "max_intervening_rows": max(
                    edge_statistics[edge_id]["intervening_rows"] for edge_id in edge_ids
                ),
                "rendering_anchors": len({
                    edge_by_id[edge_id].source_id for edge_id in edge_ids
                }),
                "manhattan_length_px": round(sum(
                    edge_statistics[edge_id]["manhattan_length_px"]
                    for edge_id in edge_ids
                ), 3),
                "horizontal_length_px": round(sum(
                    edge_statistics[edge_id]["horizontal_length_px"]
                    for edge_id in edge_ids
                ), 3),
                "vertical_length_px": round(sum(
                    edge_statistics[edge_id]["vertical_length_px"]
                    for edge_id in edge_ids
                ), 3),
                "bends_total": sum(
                    edge_statistics[edge_id]["bends"] for edge_id in edge_ids
                ),
                "bends_max_per_edge": max(
                    edge_statistics[edge_id]["bends"] for edge_id in edge_ids
                ),
                "max_edge_length_px": max(
                    edge_statistics[edge_id]["manhattan_length_px"]
                    for edge_id in edge_ids
                ),
            }
        node_statistics: dict[str, dict[str, Any]] = {}
        for name in logical_names:
            edge_ids = source_edge_ids.get(name, [])
            crossed_mask = 0
            for edge_id in edge_ids:
                crossed_mask |= edge_crossed_owner_masks[
                    edge_index_by_id[edge_id]
                ]
            node_statistics[name] = {
                "incoming_edges": logical_indegree[name],
                "outgoing_edges": logical_outdegree[name],
                "direct_downstream_nodes": len(logical_children[name]),
                "source_port_nets": len(logical_source_ports[name]),
                "rendering_anchors": physical_anchor_counts[name],
                "is_root": logical_indegree[name] == 0,
                "is_terminal": logical_outdegree[name] == 0,
                "branch_siblings": sum(
                    max(0, net_fanout[(name, port)] - 1)
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
                    edge_statistics[edge_id]["manhattan_length_px"]
                    for edge_id in edge_ids
                ), 3),
                "bends_total": sum(
                    edge_statistics[edge_id]["bends"] for edge_id in edge_ids
                ),
            }
        routing_statistics = {
            "row_pitch_px": round(row_pitch, 3),
            "totals": {
                "edges": len(edge_statistics),
                "crossing_pair_intersections": crossings,
                "distinct_crossed_edge_pairs": distinct_crossed_edge_pairs,
                "distinct_crossing_points": len(crossing_points),
                "source_induced_crossing_points": len(source_crossing_points),
                "bends_total": bends_total,
                "manhattan_length_px": round(sum(
                    item["manhattan_length_px"]
                    for item in edge_route_metrics.values()
                ), 3),
                "horizontal_length_px": round(sum(
                    item["horizontal_length_px"]
                    for item in edge_route_metrics.values()
                ), 3),
                "vertical_length_px": round(sum(
                    item["vertical_length_px"]
                    for item in edge_route_metrics.values()
                ), 3),
            },
            "edges": edge_statistics,
            "nodes": node_statistics,
            "sources": source_statistics,
        }
    hard_pass = (
        node_overlaps == 0
        and edge_node_intersections == 0
        and ambiguous == 0
        and direction_violations == 0
    )
    report = {
        "hard_pass": hard_pass,
        "nodes": len(doc.vertices),
        "edges": len(doc.edges),
        "node_overlaps": node_overlaps,
        "edge_node_intersections": edge_node_intersections,
        "direction_violations": direction_violations,
        "crossings": crossings,
        "distinct_crossing_points": len(crossing_points),
        "source_crossing_points": len(source_crossing_points),
        "ambiguous_overlaps": ambiguous,
        "bends_total": bends_total,
        "bends_max_per_edge": bends_max,
        "manhattan_length": round(length, 2),
        "width": round(max_x - min_x, 2),
        "height": round(max_y - min_y, 2),
        "area": round((max_x - min_x) * (max_y - min_y), 2),
        "runtime_ms": round(runtime_ms, 3),
    }
    if routing_statistics is not None:
        report["routing_statistics"] = routing_statistics
    return report


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
    library_path: LibrarySource,
    component_hints: dict[str, str] | None = None,
    profile_name: str = "readable",
    candidate_limit: int = 6,
) -> tuple[LayoutDocument, dict[str, Any]]:
    started = time.perf_counter()
    if profile_name not in PROFILES:
        raise ValueError(f"未知布局 profile: {profile_name}")
    if not 1 <= candidate_limit <= 6:
        raise ValueError("candidate_limit 必须在 1..6")
    library_path = library_cache_key(library_path)
    validate_config(config, library_path=library_path)
    shapes = load_library_shapes(library_path)
    nodes = resolve_nodes(
        config, shapes, component_hints or {}, library_path=library_path
    )
    logical_edges = build_logical_edges(config, nodes, library_path)
    rank = _ranks(nodes, logical_edges, _layout_column_groups(config))
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
            "junction_dots": _junction_count(document),
            "crossing_treatment": (
                "draw.io arc jump and SVG white-gap bridge"
                if selected["crossings"]
                else "not needed"
            ),
            "candidate_reports": candidate_reports,
        }
    )
    return document, final_report
