from __future__ import annotations

import json
import heapq
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from auto_layout import (
    PROFILES,
    _simplify,
    _ranks,
    _vertex_layouts,
    assess_layout,
    build_logical_edges,
    resolve_nodes,
)
from drawio_layout import EdgeLayout, LAYOUT_VERSION, LayoutDocument
from drawio_library import load_library_shapes
from drawio_ports import EDGE_DRAW_STYLE, port_anchors
from drawio_ports import abs_port_xy
from validate_config import validate_config


def elk_layout_available() -> bool:
    project_root = Path(__file__).resolve().parents[1]
    return shutil.which("node") is not None and (project_root / "node_modules" / "elkjs").exists()


@dataclass(frozen=True)
class LayoutPlan:
    mode: str
    backbone: frozenset[str]
    fanout_cutoff: float
    component_count: int
    edge_span_load: int
    gap_pair_work: int


def _regular_component_count(nodes, logical_edges, backbone: set[str]) -> int:
    regular = [name for name in nodes if name not in backbone]
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in logical_edges:
        if edge.source in backbone or edge.target in backbone:
            continue
        adjacency[edge.source].append(edge.target)
        adjacency[edge.target].append(edge.source)
    unseen = set(regular)
    count = 0
    for seed in regular:
        if seed not in unseen:
            continue
        count += 1
        unseen.remove(seed)
        stack = [seed]
        while stack:
            name = stack.pop()
            for neighbour in adjacency[name]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
    return count


def select_layout_plan(nodes, logical_edges) -> LayoutPlan:
    """Choose from graph structure, never from a global node-count boundary."""
    rank = _ranks(nodes, logical_edges)
    outgoing: dict[tuple[str, str], int] = defaultdict(int)
    for edge in logical_edges:
        outgoing[(edge.source, edge.source_port)] += 1
    fanouts = list(outgoing.values()) or [0]
    fanout_median = float(median(fanouts))
    fanout_mad = float(median(abs(value - fanout_median) for value in fanouts))
    fanout_cutoff = fanout_median + 3 * max(1.0, fanout_mad)
    outlier_backbone = {
        source
        for (source, _), count in outgoing.items()
        if count > fanout_cutoff
    }
    max_rank = max(rank.values(), default=0)
    gap_loads = [0] * max_rank
    edge_span_load = 0
    for edge in logical_edges:
        span = max(1, rank[edge.target] - rank[edge.source])
        edge_span_load += span
        for gap in range(rank[edge.source], rank[edge.target]):
            gap_loads[gap] += 1
    gap_pair_work = sum(load * load for load in gap_loads)
    # A single dominant root has no distribution in which to be an outlier.
    # Detect it by comparing projected pair work with the linear input work,
    # then admit only rootward shared nets.  The ratio is independent of total
    # node count and keeps a large simple chain on the quality path.
    linear_work = max(1, len(nodes) + edge_span_load)
    concentrated_rootward = {
        source
        for (source, _), count in outgoing.items()
        if count > 1 and rank[source] <= 1 and gap_pair_work > 6 * linear_work
    }
    backbone = outlier_backbone | concentrated_rootward
    component_count = _regular_component_count(nodes, logical_edges, backbone)
    mode = "domain" if backbone and component_count > 1 else "quality"
    return LayoutPlan(
        mode=mode,
        backbone=frozenset(backbone),
        fanout_cutoff=fanout_cutoff,
        component_count=component_count,
        edge_span_load=edge_span_load,
        gap_pair_work=gap_pair_work,
    )


def _generate_scalable_layout(nodes, logical_edges, profile, started, plan=None):
    """Linear layered layout for very large high-reuse clock networks."""
    rank = _ranks(nodes, logical_edges)
    max_rank = max(rank.values(), default=0)
    by_rank: dict[int, list[str]] = defaultdict(list)
    for name in nodes:
        by_rank[rank[name]].append(name)

    plan = plan or select_layout_plan(nodes, logical_edges)
    backbone = set(plan.backbone)

    rank_width = {
        level: max((nodes[name].shape.w for name in by_rank[level]), default=0)
        for level in range(max_rank + 1)
    }
    rank_x: dict[int, float] = {0: profile.margin}
    for level in range(1, max_rank + 1):
        rank_x[level] = (
            rank_x[level - 1] + rank_width[level - 1] + profile.layer_spacing
        )

    backbone_band = max(
        (
            sum(nodes[name].shape.h for name in by_rank[level] if name in backbone)
            + profile.node_spacing
            * max(0, sum(name in backbone for name in by_rank[level]) - 1)
        )
        for level in range(max_rank + 1)
    )
    regular_top = profile.margin + backbone_band + profile.node_spacing * 2
    positions: dict[str, tuple[float, float]] = {}
    for level in range(max_rank + 1):
        top_cursor = profile.margin
        for name in by_rank[level]:
            node = nodes[name]
            if name in backbone:
                y = top_cursor
                top_cursor += node.shape.h + profile.node_spacing
                positions[name] = (rank_x[level], y)

    regular_names = [name for name in nodes if name not in backbone]
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in logical_edges:
        if edge.source in backbone or edge.target in backbone:
            continue
        adjacency[edge.source].append(edge.target)
        adjacency[edge.target].append(edge.source)
    components: list[list[str]] = []
    unseen = set(regular_names)
    for seed in regular_names:
        if seed not in unseen:
            continue
        unseen.remove(seed)
        stack = [seed]
        component: list[str] = []
        while stack:
            name = stack.pop()
            component.append(name)
            for neighbour in adjacency[name]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
        components.append(component)

    band_top = regular_top
    for component in components:
        component_by_rank: dict[int, list[str]] = defaultdict(list)
        for name in component:
            component_by_rank[rank[name]].append(name)
        band_height = max(
            sum(nodes[name].shape.h for name in names)
            + profile.node_spacing * max(0, len(names) - 1)
            for names in component_by_rank.values()
        )
        for level, names in component_by_rank.items():
            total = (
                sum(nodes[name].shape.h for name in names)
                + profile.node_spacing * max(0, len(names) - 1)
            )
            cursor = band_top + (band_height - total) / 2
            for name in sorted(names):
                positions[name] = (rank_x[level], cursor)
                cursor += nodes[name].shape.h + profile.node_spacing
        band_top += band_height + profile.node_spacing

    diagram_bottom = max(
        y + nodes[name].shape.h for name, (_, y) in positions.items()
    )
    long_source_keys = sorted(
        {
            (edge.source, edge.source_port)
            for edge in logical_edges
            if rank[edge.target] - rank[edge.source] > 1
        }
    )
    bottom_lanes = {
        key: diagram_bottom + profile.node_spacing + index * profile.grid * 2
        for index, key in enumerate(long_source_keys)
    }

    # Colour vertical occupancy intervals in each inter-rank gap.  Different
    # nets share an x lane only when their y intervals do not overlap; all
    # branches from one source port deliberately remain one visual trunk.
    intervals_by_gap: dict[
        int, dict[tuple[str, str], tuple[float, float]]
    ] = defaultdict(dict)

    def add_interval(
        gap: int, key: tuple[str, str], y0: float, y1: float
    ) -> None:
        lo, hi = sorted((y0, y1))
        previous = intervals_by_gap[gap].get(key)
        intervals_by_gap[gap][key] = (
            min(lo, previous[0]) if previous else lo,
            max(hi, previous[1]) if previous else hi,
        )

    for edge in logical_edges:
        source = nodes[edge.source]
        target = nodes[edge.target]
        source_anchor = port_anchors(source.shape.style, source.shape.title)[edge.source_port]
        target_anchor = port_anchors(target.shape.style, target.shape.title)[edge.target_port]
        sy = positions[edge.source][1] + source.shape.h * source_anchor[1]
        ty = positions[edge.target][1] + target.shape.h * target_anchor[1]
        source_rank = rank[edge.source]
        target_rank = rank[edge.target]
        key = (edge.source, edge.source_port)
        if target_rank - source_rank > 1:
            lane_y = bottom_lanes[key]
            add_interval(source_rank + 1, key, sy, lane_y)
            add_interval(target_rank, key, lane_y, ty)
        else:
            add_interval(target_rank, key, sy, ty)

    lane_index: dict[tuple[int, str, str], int] = {}
    lane_count: dict[int, int] = {}
    for gap, grouped in intervals_by_gap.items():
        active: list[tuple[float, int]] = []
        free: list[int] = []
        next_lane = 0
        for (source, port), (lo, hi) in sorted(
            grouped.items(), key=lambda item: (item[1][0], item[1][1], item[0])
        ):
            while active and active[0][0] <= lo:
                _, released = heapq.heappop(active)
                heapq.heappush(free, released)
            lane = heapq.heappop(free) if free else next_lane
            if lane == next_lane:
                next_lane += 1
            lane_index[(gap, source, port)] = lane
            heapq.heappush(active, (hi, lane))
        lane_count[gap] = next_lane

    rank_x = {0: profile.margin}
    for level in range(1, max_rank + 1):
        gap_width = max(
            profile.layer_spacing,
            (lane_count.get(level, 0) + 2) * profile.grid,
        )
        rank_x[level] = rank_x[level - 1] + rank_width[level - 1] + gap_width
    positions = {
        name: (rank_x[rank[name]], y)
        for name, (_, y) in positions.items()
    }

    def lane_x(gap: int, key: tuple[str, str]) -> float:
        left = rank_x[gap - 1] + rank_width[gap - 1]
        return left + profile.grid * (lane_index[(gap, *key)] + 1)

    edge_ids = {edge.key: f"e{index}" for index, edge in enumerate(logical_edges, 1)}
    layouts: list[EdgeLayout] = []
    for edge in logical_edges:
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
        source_rank = rank[edge.source]
        target_rank = rank[edge.target]
        source_key = (edge.source, edge.source_port)
        if target_rank - source_rank > 1:
            first_x = lane_x(source_rank + 1, source_key)
            last_x = lane_x(target_rank, source_key)
            lane_y = bottom_lanes[source_key]
            points = _simplify(
                [(sx, sy), (first_x, sy), (first_x, lane_y),
                 (last_x, lane_y), (last_x, ty), (tx, ty)]
            )
        else:
            edge_lane_x = lane_x(target_rank, source_key)
            if abs(sy - ty) <= 0.01:
                points = [(sx, sy), (tx, ty)]
            else:
                points = _simplify(
                    [(sx, sy), (edge_lane_x, sy), (edge_lane_x, ty), (tx, ty)]
                )
        source_anchor = port_anchors(source.shape.style, source.shape.title)[edge.source_port]
        target_anchor = port_anchors(target.shape.style, target.shape.title)[edge.target_port]
        style = (
            f"{EDGE_DRAW_STYLE}jumpStyle=arc;jumpSize=6;"
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
    document = LayoutDocument(
        version=LAYOUT_VERSION,
        vertices=_vertex_layouts(nodes, positions),
        edges=layouts,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return document, {
        "engine": "scalable-layered",
        "mode": "adaptive-domain-decomposition",
        "runtime_ms": round(elapsed_ms, 3),
        "nodes": len(nodes),
        "edges": len(logical_edges),
        "selection": {
            "basis": "graph-structure",
            "fanout_cutoff": plan.fanout_cutoff,
            "backbone_nodes": len(plan.backbone),
            "regular_components": plan.component_count,
            "edge_span_load": plan.edge_span_load,
            "gap_pair_work": plan.gap_pair_work,
        },
    }


def generate_elk_layout(
    config: dict[str, dict[str, Any]],
    *,
    library_path: str | Path,
    component_hints: dict[str, str] | None = None,
    profile_name: str = "readable",
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Lay out a clock DAG with ELK Layered and exact library ports."""
    started = time.perf_counter()
    if profile_name not in PROFILES:
        raise ValueError(f"未知布局 profile: {profile_name}")
    node_executable = shutil.which("node")
    if node_executable is None:
        raise ValueError("ELK 布局需要 Node.js；请先安装 Node.js 并运行 npm install")
    project_root = Path(__file__).resolve().parents[1]
    script = project_root / "scripts" / "elk_layout.mjs"
    if not (project_root / "node_modules" / "elkjs").exists():
        raise ValueError("ELK 布局依赖未安装；请在项目根目录运行 npm install")

    validate_config(config, library_path=library_path)
    shapes = load_library_shapes(library_path)
    nodes = resolve_nodes(config, shapes, component_hints or {})
    logical_edges = build_logical_edges(config, nodes, library_path)
    profile = PROFILES[profile_name]
    plan = select_layout_plan(nodes, logical_edges)
    if plan.mode == "domain":
        return _generate_scalable_layout(nodes, logical_edges, profile, started, plan)
    graph: dict[str, Any] = {
        "layout": {
            "nodeSpacing": profile.node_spacing,
            "layerSpacing": profile.layer_spacing,
            "edgeNodeSpacing": profile.route_clearance * 2,
            "edgeSpacing": max(10.0, profile.grid),
            "margin": profile.margin,
            "mode": "quality",
        },
        "nodes": [],
        "edges": [],
    }
    left_insets: dict[str, float] = {}
    for name, node in nodes.items():
        anchors = port_anchors(node.shape.style, node.shape.title)
        width = float(node.shape.w)
        west_xs = [rx * width for rx, _ in anchors.values() if rx < 0.5]
        east_xs = [rx * width for rx, _ in anchors.values() if rx >= 0.5]
        left_inset = min(west_xs) if west_xs else 0.0
        right_boundary = max(east_xs) if east_xs else width
        left_insets[name] = left_inset
        graph["nodes"].append({
            "id": name,
            "layoutWidth": right_boundary - left_inset,
            "height": float(node.shape.h),
            "ports": [
                {
                    "id": port,
                    "x": rx * width - left_inset,
                    "y": ry * float(node.shape.h),
                    "side": "WEST" if rx < 0.5 else "EAST",
                }
                for port, (rx, ry) in anchors.items()
            ],
        })
    for index, edge in enumerate(logical_edges, 1):
        graph["edges"].append({
            "id": f"e{index}",
            "source": edge.source,
            "target": edge.target,
            "sourcePort": edge.source_port,
            "targetPort": edge.target_port,
        })

    try:
        with tempfile.TemporaryDirectory(prefix="drawclock-elk-") as temp_dir:
            input_path = Path(temp_dir) / "input.json"
            output_path = Path(temp_dir) / "output.json"
            input_path.write_text(json.dumps(graph), encoding="utf-8")
            completed = subprocess.run(
                [node_executable, str(script), str(input_path), str(output_path)],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "unknown error"
                raise ValueError(f"ELK 布局失败: {detail}")
            result = json.loads(output_path.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired as exc:
        raise ValueError("ELK 布局超过 120 秒预算") from exc

    positions = {
        name: (
            round(float(position["x"]) - left_insets[name], 4),
            round(float(position["y"]), 4),
        )
        for name, position in result["nodes"].items()
    }
    edges: list[EdgeLayout] = []
    for index, logical in enumerate(logical_edges, 1):
        edge_id = f"e{index}"
        points = _simplify([
            (round(float(point["x"]), 4), round(float(point["y"]), 4))
            for point in result["edges"][edge_id]["points"]
        ])
        source_anchor = port_anchors(
            nodes[logical.source].shape.style, nodes[logical.source].shape.title
        )[logical.source_port]
        target_anchor = port_anchors(
            nodes[logical.target].shape.style, nodes[logical.target].shape.title
        )[logical.target_port]
        style = (
            f"{EDGE_DRAW_STYLE}jumpStyle=arc;jumpSize=6;"
            f"exitX={source_anchor[0]:g};exitY={source_anchor[1]:g};"
            f"entryX={target_anchor[0]:g};entryY={target_anchor[1]:g};"
        )
        edges.append(EdgeLayout(
            cell_id=edge_id,
            source_id=nodes[logical.source].cell_id,
            target_id=nodes[logical.target].cell_id,
            style=style,
            waypoints=tuple(points[1:-1]),
        ))
    document = LayoutDocument(
        version=LAYOUT_VERSION,
        vertices=_vertex_layouts(nodes, positions),
        edges=edges,
    )
    report = assess_layout(document, logical_edges, (time.perf_counter() - started) * 1000)
    report.update({
        "engine": "elk-layered",
        "engine_version": "elkjs 0.11.1",
        "profile": profile_name,
        "layout_runtime_ms": round(float(result["runtimeMs"]), 3),
        "selection": {
            "basis": "graph-structure",
            "fanout_cutoff": plan.fanout_cutoff,
            "backbone_nodes": len(plan.backbone),
            "regular_components": plan.component_count,
            "edge_span_load": plan.edge_span_load,
            "gap_pair_work": plan.gap_pair_work,
        },
    })
    return document, report
