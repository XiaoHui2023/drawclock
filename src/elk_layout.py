from __future__ import annotations

import json
import heapq
import math
import os
import copy
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from auto_layout import (
    PROFILES,
    _mean,
    _simplify,
    _ranks,
    _overlap_length,
    _proper_cross,
    _segment_hits_rect,
    _vertex_layouts,
    assess_layout,
    build_logical_edges,
    resolve_nodes,
    Segment,
)
from drawio_layout import EdgeLayout, LAYOUT_VERSION, LayoutDocument
from drawio_library import load_library_shapes
from drawio_ports import EDGE_DRAW_STYLE, port_anchors
from drawio_ports import abs_port_xy
from validate_config import validate_config
from visual_geometry import estimated_label_width, vertex_visual_box, visual_box


def _elk_runtime() -> tuple[str, Path, Path] | None:
    project_root = Path(__file__).resolve().parents[1]
    runtime_roots: list[Path] = []
    staticx_program = os.environ.get("STATICX_PROG_PATH")
    if staticx_program:
        runtime_roots.append(Path(staticx_program).resolve().parent / "runtime")
    if getattr(sys, "frozen", False):
        runtime_roots.append(Path(sys.executable).resolve().parent / "runtime")
    runtime_roots.append(project_root / ".runtime")
    node_name = Path("node/node.exe") if sys.platform == "win32" else Path("node/bin/node")
    for root in runtime_roots:
        node = root / node_name
        elk_root = root / "elk"
        script = elk_root / "elk_layout.mjs"
        bundled = elk_root / "node_modules" / "elkjs" / "lib" / "elk.bundled.js"
        if node.is_file() and script.is_file() and bundled.is_file():
            return str(node), script, elk_root
    node = shutil.which("node")
    script = project_root / "scripts" / "elk_layout.mjs"
    if node and script.is_file() and (project_root / "node_modules" / "elkjs").is_dir():
        return node, script, project_root
    return None


def elk_layout_available() -> bool:
    return _elk_runtime() is not None


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


def _generate_scalable_layout(
    nodes, logical_edges, profile, started, library_path, plan=None,
    source_position_mode="consumer-median",
):
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
    label_overflow = {
        name: max(
            0.0,
            (
                estimated_label_width(
                    name,
                    node.shape.label,
                    node.shape.w,
                )
                - node.shape.w
            )
            / 2.0,
        )
        for name, node in nodes.items()
    }
    rank_overflow = {
        level: max((label_overflow[name] for name in by_rank[level]), default=0.0)
        for level in range(max_rank + 1)
    }
    rank_x: dict[int, float] = {0: profile.margin + rank_overflow[0]}
    for level in range(1, max_rank + 1):
        rank_x[level] = (
            rank_x[level - 1]
            + rank_width[level - 1]
            + rank_overflow[level - 1]
            + profile.layer_spacing
            + rank_overflow[level]
        )

    # Residual clock domains own the main vertical bands.  Shared roots are
    # positioned afterwards near the median of their consumers instead of
    # reserving a dedicated strip at the top of the drawing.
    regular_top = profile.margin
    positions: dict[str, tuple[float, float]] = {}

    def weighted_median(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[(len(ordered) - 1) // 2]

    regular_names = [name for name in nodes if name not in backbone]
    separable_backbone_domains = len(backbone) <= 1
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

    # Order residual domains by their shared-backbone incidence before
    # assigning vertical bands.  Alternating medians are the two-layer
    # crossing-minimisation step from Sugiyama layouts; the complete incidence
    # signature is a deterministic tie-breaker that keeps domains fed by the
    # same roots contiguous.  This replaces input-file insertion order, which
    # could put two groups of one source above and below many unrelated groups
    # and force a needless full-height trunk through them.
    if len(components) > 1 and backbone:
        component_of = {
            name: index
            for index, component in enumerate(components)
            for name in component
        }
        roots_by_component: dict[int, set[str]] = defaultdict(set)
        components_by_root: dict[str, set[int]] = defaultdict(set)
        for edge in logical_edges:
            if edge.source in backbone and edge.target in component_of:
                index = component_of[edge.target]
                roots_by_component[index].add(edge.source)
                components_by_root[edge.source].add(index)
            elif edge.target in backbone and edge.source in component_of:
                index = component_of[edge.source]
                roots_by_component[index].add(edge.target)
                components_by_root[edge.target].add(index)
        signatures = sorted({
            frozenset(roots) for roots in roots_by_component.values() if roots
        }, key=lambda item: tuple(sorted(item)))
        # Disjoint signatures can be grouped without trading one shared-root
        # crossing for another.  Overlapping non-identical signatures form a
        # true weave (for example A+B, B+C, C+D); keep their already stable
        # domain order instead of applying a locally attractive but globally
        # regressive sort.
        safely_separable = all(
            not (left & right)
            for index, left in enumerate(signatures)
            for right in signatures[index + 1:]
        )
        separable_backbone_domains = safely_separable
        if safely_separable:
            component_ids = list(range(len(components)))
            component_position = {index: index for index in component_ids}
            for _ in range(8):
                root_position = {
                    root: weighted_median([
                        float(component_position[index]) for index in indices
                    ])
                    for root, indices in components_by_root.items()
                }
                ordered_ids = sorted(component_ids, key=lambda index: (
                    weighted_median([
                        root_position[root] for root in roots_by_component[index]
                    ]) if roots_by_component[index] else float(component_position[index]),
                    tuple(sorted(
                        root_position[root] for root in roots_by_component[index]
                    )),
                    tuple(sorted(roots_by_component[index])),
                    component_position[index],
                ))
                new_position = {
                    index: position for position, index in enumerate(ordered_ids)
                }
                if new_position == component_position:
                    break
                component_position = new_position
            components = [components[index] for index in sorted(
                component_ids, key=component_position.__getitem__
            )]

    incoming_internal: dict[str, list[Any]] = defaultdict(list)
    outgoing_internal: dict[str, list[Any]] = defaultdict(list)
    for edge in logical_edges:
        if edge.source in backbone or edge.target in backbone:
            continue
        incoming_internal[edge.target].append(edge)
        outgoing_internal[edge.source].append(edge)

    band_top = regular_top
    component_index: dict[str, int] = {}
    component_bounds: dict[int, tuple[float, float]] = {}
    for component_number, component in enumerate(components):
        component_by_rank: dict[int, list[str]] = defaultdict(list)
        for name in component:
            component_by_rank[rank[name]].append(name)
        # A mux's fixed input pitch can be smaller than the generic routing
        # clearance.  Node boxes must not overlap, but forcing the full edge
        # clearance between siblings makes two otherwise aligned mux inputs
        # acquire needless doglegs.  Routing clearance belongs to channels,
        # not to vertical node packing.
        local_spacing = max(1.0, profile.grid / 10.0)
        sequence: dict[str, int] = {}
        for level in sorted(component_by_rank, reverse=True):
            names = component_by_rank[level]
            names.sort(key=lambda name: (
                sum(
                    sequence.get(edge.target, 0)
                    + port_anchors(
                        nodes[edge.target].shape.style,
                        nodes[edge.target].shape.title,
                    )[edge.target_port][1]
                    for edge in outgoing_internal[name]
                ),
                name,
            ))
            sequence.update({name: index for index, name in enumerate(names)})

        # Sugiyama-style alternating barycentric sweeps.  The previous
        # right-to-left seed is useful for chains, but a terminal layer sorted
        # by instance name can interleave A-B-A when A fans out twice and B
        # once.  Reordering by adjacent-layer topology keeps siblings
        # contiguous and removes the avoidable last-gap crossing before any
        # route is computed.
        def enforce_target_port_order(names: list[str]) -> None:
            """Project a barycentric order onto acyclic fixed-port precedences."""
            base_position = {name: index for index, name in enumerate(names)}
            members = set(names)
            parents_by_target: dict[str, list[Any]] = defaultdict(list)
            for source_name in names:
                for edge in outgoing_internal[source_name]:
                    if edge.source in members:
                        parents_by_target[edge.target].append(edge)
            successors: dict[str, set[str]] = defaultdict(set)
            indegree = {name: 0 for name in names}
            for target_name, edges in parents_by_target.items():
                target = nodes[target_name]
                ordered_edges = sorted(edges, key=lambda edge: (
                    port_anchors(
                        target.shape.style, target.shape.title
                    )[edge.target_port][1],
                    edge.target_port,
                    base_position[edge.source],
                ))
                for left, right in zip(ordered_edges, ordered_edges[1:]):
                    if left.source == right.source:
                        continue
                    if right.source not in successors[left.source]:
                        successors[left.source].add(right.source)
                        indegree[right.source] += 1
            ready = [
                (base_position[name], name)
                for name in names if indegree[name] == 0
            ]
            heapq.heapify(ready)
            constrained: list[str] = []
            while ready:
                _, name = heapq.heappop(ready)
                constrained.append(name)
                for child in sorted(successors[name], key=base_position.__getitem__):
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        heapq.heappush(ready, (base_position[child], child))
            if len(constrained) == len(names):
                names[:] = constrained

        levels_ascending = sorted(component_by_rank)
        for _ in range(4):
            order_index = {
                name: index
                for names in component_by_rank.values()
                for index, name in enumerate(names)
            }
            for level in levels_ascending[1:]:
                names = component_by_rank[level]
                names.sort(key=lambda name: (
                    _mean(
                        order_index[edge.source]
                        + port_anchors(
                            nodes[edge.source].shape.style,
                            nodes[edge.source].shape.title,
                        )[edge.source_port][1]
                        for edge in incoming_internal[name]
                        if edge.source in order_index
                    ),
                    order_index[name],
                    name,
                ))
                enforce_target_port_order(names)
                order_index.update({name: index for index, name in enumerate(names)})
            for level in reversed(levels_ascending[:-1]):
                names = component_by_rank[level]
                names.sort(key=lambda name: (
                    _mean(
                        order_index[edge.target]
                        + port_anchors(
                            nodes[edge.target].shape.style,
                            nodes[edge.target].shape.title,
                        )[edge.target_port][1]
                        for edge in outgoing_internal[name]
                        if edge.target in order_index
                    ),
                    order_index[name],
                    name,
                ))
                enforce_target_port_order(names)
                order_index.update({name: index for index, name in enumerate(names)})
        band_height = max(
            sum(nodes[name].shape.h for name in names)
            + local_spacing * max(0, len(names) - 1)
            for names in component_by_rank.values()
        )
        for level, names in component_by_rank.items():
            total = (
                sum(nodes[name].shape.h for name in names)
                + local_spacing * max(0, len(names) - 1)
            )
            cursor = band_top + (band_height - total) / 2
            for name in names:
                positions[name] = (rank_x[level], cursor)
                component_index[name] = component_number
                cursor += nodes[name].shape.h + local_spacing

        # Port-axis coordinate assignment.  Alternate forward and backward
        # sweeps, then project each rank onto the non-overlap constraints.  A
        # whole rank may translate, but component geometry and port anchors are
        # never changed.
        for forward in (True, False, True, False):
            levels = sorted(component_by_rank, reverse=not forward)
            for level in levels:
                names = component_by_rank[level]
                desired: list[float] = []
                for name in names:
                    related = incoming_internal[name] if forward else outgoing_internal[name]
                    candidates: list[float] = []
                    for edge in related:
                        source = nodes[edge.source]
                        target = nodes[edge.target]
                        source_y = port_anchors(source.shape.style, source.shape.title)[edge.source_port][1]
                        target_y = port_anchors(target.shape.style, target.shape.title)[edge.target_port][1]
                        if forward:
                            candidates.append(
                                positions[edge.source][1]
                                + source.shape.h * source_y
                                - target.shape.h * target_y
                            )
                        else:
                            candidates.append(
                                positions[edge.target][1]
                                + target.shape.h * target_y
                                - source.shape.h * source_y
                            )
                    desired.append(
                        sum(candidates) / len(candidates)
                        if candidates else positions[name][1]
                    )
                packed: list[float] = []
                for index, name in enumerate(names):
                    minimum = (
                        packed[-1] + nodes[names[index - 1]].shape.h + local_spacing
                        if packed else -float("inf")
                    )
                    packed.append(max(minimum, desired[index]))
                translation = sum(
                    wanted - actual for wanted, actual in zip(desired, packed)
                ) / len(packed)
                for name, top in zip(names, packed):
                    positions[name] = (positions[name][0], top + translation)

        # Projection translates a whole rank to minimize aggregate error and
        # can leave a one-parent terminal a fraction of a track off-axis.  A
        # final constraint projection moves such a sink to its exact parent
        # port axis whenever the non-overlap inequalities remain satisfied.
        # This prevents tiny H-V-H stubs without changing any port geometry.
        for level, names in component_by_rank.items():
            ordered_names = sorted(names, key=lambda item: positions[item][1])
            for index, name in enumerate(ordered_names):
                incoming_edges = incoming_internal[name]
                if len(incoming_edges) != 1 or outgoing_internal[name]:
                    continue
                edge = incoming_edges[0]
                source = nodes[edge.source]
                target = nodes[name]
                source_anchor = port_anchors(
                    source.shape.style, source.shape.title
                )[edge.source_port][1]
                target_anchor = port_anchors(
                    target.shape.style, target.shape.title
                )[edge.target_port][1]
                wanted_top = (
                    positions[edge.source][1]
                    + source.shape.h * source_anchor
                    - target.shape.h * target_anchor
                )
                previous = ordered_names[index - 1] if index else None
                following = (
                    ordered_names[index + 1]
                    if index + 1 < len(ordered_names) else None
                )
                if (
                    previous is None
                    or wanted_top
                    >= positions[previous][1] + nodes[previous].shape.h
                ) and (
                    following is None
                    or wanted_top + target.shape.h <= positions[following][1]
                ):
                    positions[name] = (positions[name][0], wanted_top)

        actual_top = min(positions[name][1] for name in component)
        shift = band_top - actual_top
        for name in component:
            x, y = positions[name]
            positions[name] = (x, y + shift)
        actual_bottom = max(
            positions[name][1] + nodes[name].shape.h for name in component
        )
        component_bounds[component_number] = (band_top, actual_bottom)
        # Two inflated node footprints may touch at the midpoint of this gap;
        # anything larger is unused whitespace unless routing proves it needs
        # another lane.
        # Keep a routable inter-domain corridor.  Node spacing is retained
        # only when it is wider than two clearances plus a real route track;
        # horizontal layer spacing is compacted independently below.
        band_top = actual_bottom + max(
            profile.node_spacing,
            2 * profile.route_clearance + profile.grid,
        )

    outgoing_all: dict[str, list[Any]] = defaultdict(list)
    for edge in logical_edges:
        outgoing_all[edge.source].append(edge)

    def nearest_free_top(
        wanted: float,
        height: float,
        occupied: list[tuple[float, float]],
        spacing: float,
        minimum_top: float = profile.margin,
    ) -> float:
        """Place a movable node in the nearest legal vertical slot."""
        candidates = {max(minimum_top, wanted)}
        for low, high in occupied:
            candidates.add(max(minimum_top, low - spacing - height))
            candidates.add(max(minimum_top, high + spacing))
        legal = [
            top
            for top in candidates
            if all(
                top + height + spacing <= low
                or top >= high + spacing
                for low, high in occupied
            )
        ]
        if legal:
            return min(legal, key=lambda top: (abs(top - wanted), top))
        top = max(minimum_top, wanted)
        for low, high in sorted(occupied):
            if top + height + spacing > low and top < high + spacing:
                top = high + spacing
        return top

    # Place shared roots/hubs from right to left, once every child position is
    # known.  The median minimizes total vertical lead length.  A unique root
    # whose consumers span the drawing and include the top route is instead
    # attached at that top boundary: the distribution trunk has the same span
    # either way, while the conventional top entry avoids an arbitrary source
    # floating in the middle of its own bus.  This decision uses only topology
    # and consumer geometry, never a component kind or instance name.
    backbone_by_rank: dict[int, list[str]] = defaultdict(list)
    for name in backbone:
        backbone_by_rank[rank[name]].append(name)
    source_spacing = max(1.0, profile.grid / 10.0)
    boundary_placed_roots: set[str] = set()
    for level in range(max_rank, -1, -1):
        names = backbone_by_rank[level]
        if not names:
            continue
        desired: dict[str, float] = {}
        target_axes_by_name: dict[str, list[float]] = {}
        for name in names:
            source = nodes[name]
            target_axes = []
            for edge in outgoing_all[name]:
                target = nodes[edge.target]
                target_anchor = port_anchors(
                    target.shape.style, target.shape.title
                )[edge.target_port][1]
                source_anchor = port_anchors(
                    source.shape.style, source.shape.title
                )[edge.source_port][1]
                target_axes.append(
                    positions[edge.target][1]
                    + target.shape.h * target_anchor
                    - source.shape.h * source_anchor
                )
            target_axes_by_name[name] = target_axes
            desired[name] = (
                weighted_median(target_axes)
                if target_axes else profile.margin
            )
        spans = {
            name: (
                max(axes) - min(axes) if len(axes) > 1 else 0.0
            )
            for name, axes in target_axes_by_name.items()
        }
        span_values = list(spans.values()) or [0.0]
        span_median = float(median(span_values))
        span_mad = float(median(
            abs(value - span_median) for value in span_values
        ))
        global_top_axis = min(
            (axis for axes in target_axes_by_name.values() for axis in axes),
            default=profile.margin,
        )
        ordered_spans = sorted(spans.values(), reverse=True)
        dominant_span = ordered_spans[0] if ordered_spans else 0.0
        runner_up_span = ordered_spans[1] if len(ordered_spans) > 1 else 0.0
        boundary_roots = {
            name
            for name, axes in target_axes_by_name.items()
            if len(axes) > 1
            and spans[name] > 0
            and separable_backbone_domains
            and min(axes) <= global_top_axis + source_spacing
            and (
                len(names) == 1
                or spans[name] > span_median + max(source_spacing, span_mad)
                or (
                    spans[name] == dominant_span
                    and dominant_span > runner_up_span + source_spacing
                )
            )
        }
        boundary_placed_roots.update(boundary_roots)
        occupied = sorted(
            (positions[name][1], positions[name][1] + nodes[name].shape.h)
            for name in by_rank[level]
            if name not in backbone and name in positions
        )
        ordered_names = sorted(names, key=lambda item: (desired[item], item))
        for source_index, name in enumerate(ordered_names):
            node = nodes[name]
            wanted = (
                min(target_axes_by_name[name])
                if source_position_mode == "adaptive-span"
                and name in boundary_roots
                else desired[name]
                if source_position_mode in {"consumer-median", "adaptive-span"}
                else profile.margin + source_index * (node.shape.h + source_spacing)
            )
            top = nearest_free_top(
                wanted,
                node.shape.h,
                occupied,
                source_spacing,
                profile.margin - profile.route_clearance,
            )
            positions[name] = (rank_x[level], top)
            occupied.append((top, top + node.shape.h))
            occupied.sort()

    rect_vertical = {
        name: (
            positions[name][1] - profile.route_clearance,
            positions[name][1] + node.shape.h + profile.route_clearance,
        )
        for name, node in nodes.items()
    }

    horizontal_lane_occupancy: dict[
        int, list[tuple[int, int, tuple[str, str]]]
    ] = defaultdict(list)

    def horizontal_lane_key(y: float) -> int:
        """Canonicalise a corridor using the routing grid, not float identity."""
        return round(y / (profile.grid / 2.0))

    def local_long_lane(edge, sy: float, ty: float) -> float:
        """Choose a collision-free y corridor near this edge's own domain."""
        source_rank = rank[edge.source]
        target_rank = rank[edge.target]
        midpoint = round(((sy + ty) / 2) / profile.grid) * profile.grid
        candidates = [sy, ty, midpoint]
        component = component_index.get(edge.target, component_index.get(edge.source))
        local_by_rank = (
            {
                level: [
                    name for name in components[component] if rank[name] == level
                ]
                for level in range(source_rank + 1, target_rank)
            }
            if component is not None
            else {
                level: [name for name in by_rank[level] if name in backbone]
                for level in range(source_rank + 1, target_rank)
            }
        )
        if component is not None:
            top, bottom = component_bounds[component]
            candidates.extend((
                top - profile.route_clearance - profile.grid,
                bottom + profile.route_clearance + profile.grid,
            ))
        else:
            candidates.extend((
                profile.margin - profile.route_clearance - profile.grid,
                regular_top - profile.route_clearance - profile.grid,
            ))
        for level in range(source_rank + 1, target_rank):
            for name in local_by_rank[level]:
                if name in (edge.source, edge.target):
                    continue
                low, high = rect_vertical[name]
                candidates.extend((low, high))

        base_candidates = tuple(dict.fromkeys(candidates))
        candidates = [
            lane + offset * profile.grid
            for lane in base_candidates
            # Compaction removes large passive gaps, so a local obstacle
            # boundary may need several neighbouring tracks before a distinct
            # net finds a non-overlapping horizontal corridor.
            for offset in (
                0, -0.5, 0.5, -1, 1, -1.5, 1.5, -2, 2,
                -3, 3, -4, 4, -5, 5, -6, 6,
            )
        ]

        endpoint_low, endpoint_high = sorted((sy, ty))
        best = None
        for lane in dict.fromkeys(candidates):
            hits = sum(
                low < lane < high
                for level in range(source_rank + 1, target_rank)
                for name in local_by_rank[level]
                if name not in (edge.source, edge.target)
                for low, high in (rect_vertical[name],)
            )
            outer_excursion = max(
                0.0, endpoint_low - lane, lane - endpoint_high
            )
            net = (edge.source, edge.source_port)
            lane_overlaps = sum(
                other_net != net
                # Rank intervals are closed here: two long horizontal routes
                # can still share physical x-space when their logical spans
                # merely meet at a rank boundary (the node/port escape zones
                # extend to either side of that boundary).
                and max(source_rank, other_start) <= min(target_rank, other_end)
                for other_start, other_end, other_net
                in horizontal_lane_occupancy[horizontal_lane_key(lane)]
            )
            score = (
                hits,
                lane_overlaps,
                outer_excursion,
                abs(lane - sy) + abs(lane - ty),
                abs(lane - midpoint),
            )
            if best is None or score < best[0]:
                best = (score, lane)
        assert best is not None
        lane = best[1]
        horizontal_lane_occupancy[horizontal_lane_key(lane)].append((
            source_rank, target_rank, (edge.source, edge.source_port)
        ))
        return lane

    long_lanes: dict[str, float] = {}

    # Colour vertical occupancy intervals in each inter-rank gap.  A compact
    # fanout remains one visual trunk.  If its target axes contain a genuine
    # geometric gap (larger than both the ordinary target pitch and two
    # routable node clearances), split the same electrical net into local
    # distribution trunks.  This avoids dragging one vertical line through a
    # large unrelated region while retaining a shared prefix and junctions.
    edges_by_net: dict[tuple[str, str], list[Any]] = defaultdict(list)
    target_axis_by_edge: dict[str, float] = {}
    for edge in logical_edges:
        target = nodes[edge.target]
        anchor = port_anchors(
            target.shape.style, target.shape.title
        )[edge.target_port][1]
        axis = positions[edge.target][1] + target.shape.h * anchor
        target_axis_by_edge[edge.key] = axis
        edges_by_net[(edge.source, edge.source_port)].append(edge)
    route_lane_key: dict[str, tuple[str, str, int]] = {}
    source_trunk_lane_key: dict[str, tuple[str, str, int]] = {}
    fanout_trunk_clusters: dict[tuple[str, str], int] = {}
    for net, net_edges in edges_by_net.items():
        ordered = sorted(
            net_edges,
            key=lambda edge: (target_axis_by_edge[edge.key], edge.target, edge.target_port),
        )
        axes = [target_axis_by_edge[edge.key] for edge in ordered]
        gaps = [right - left for left, right in zip(axes, axes[1:])]
        positive_gaps = [gap for gap in gaps if gap > 1e-6]
        ordinary_pitch = float(median(positive_gaps)) if positive_gaps else 0.0
        target_height = float(median(
            [nodes[edge.target].shape.h for edge in ordered]
        ))
        geometric_clearance = (
            target_height + 2 * profile.route_clearance + profile.grid
        )
        split_threshold = max(2 * ordinary_pitch, geometric_clearance)
        cluster = 0
        for index, edge in enumerate(ordered):
            if index and gaps[index - 1] > split_threshold:
                cluster += 1
            route_lane_key[edge.key] = (*net, cluster)
            source_trunk_lane_key[edge.key] = (
                (*net, -1) if len(ordered) > 1 else (*net, cluster)
            )
        fanout_trunk_clusters[net] = cluster + 1

    intervals_by_gap: dict[
        int, dict[tuple[str, str, int], tuple[float, float]]
    ] = defaultdict(dict)

    def add_interval(
        gap: int, key: tuple[str, str, int], y0: float, y1: float
    ) -> None:
        lo, hi = sorted((y0, y1))
        previous = intervals_by_gap[gap].get(key)
        intervals_by_gap[gap][key] = (
            min(lo, previous[0]) if previous else lo,
            max(hi, previous[1]) if previous else hi,
        )

    # Allocation and routing must use the same deterministic order.  Otherwise
    # a compact candidate can take a corridor reserved by an edge that is
    # routed later, despite both passes being individually collision-aware.
    routing_order = sorted(
        logical_edges,
        key=lambda edge: (
            rank[edge.target] - rank[edge.source],
            edge.source,
            edge.source_port,
            edge.target,
            edge.target_port,
        ),
    )

    for edge in routing_order:
        source = nodes[edge.source]
        target = nodes[edge.target]
        source_anchor = port_anchors(source.shape.style, source.shape.title)[edge.source_port]
        target_anchor = port_anchors(target.shape.style, target.shape.title)[edge.target_port]
        sy = positions[edge.source][1] + source.shape.h * source_anchor[1]
        ty = positions[edge.target][1] + target.shape.h * target_anchor[1]
        source_rank = rank[edge.source]
        target_rank = rank[edge.target]
        key = route_lane_key[edge.key]
        source_key = source_trunk_lane_key[edge.key]
        if target_rank - source_rank > 1:
            lane_y = local_long_lane(edge, sy, ty)
            long_lanes[edge.key] = lane_y
            # Either endpoint channel may be selected for the simplified
            # H-V-H candidate, so both channels must reserve the candidate's
            # complete vertical span.  Reserving only the four-bend fallback
            # span lets different nets become collinear after simplification.
            reserved_low = min(sy, ty, lane_y)
            reserved_high = max(sy, ty, lane_y)
            add_interval(
                source_rank + 1, source_key, reserved_low, reserved_high
            )
            add_interval(target_rank, key, reserved_low, reserved_high)
        else:
            add_interval(target_rank, source_key, sy, ty)

    lane_index: dict[tuple[int, str, str, int], int] = {}
    lane_count: dict[int, int] = {}
    for gap, grouped in intervals_by_gap.items():
        active: list[tuple[float, int]] = []
        free: list[int] = []
        next_lane = 0
        for (source, port, cluster), (lo, hi) in sorted(
            grouped.items(), key=lambda item: (item[1][0], item[1][1], item[0])
        ):
            while active and active[0][0] <= lo:
                _, released = heapq.heappop(active)
                heapq.heappush(free, released)
            lane = heapq.heappop(free) if free else next_lane
            if lane == next_lane:
                next_lane += 1
            lane_index[(gap, source, port, cluster)] = lane
            heapq.heappush(active, (hi, lane))
        lane_count[gap] = next_lane

    rank_x = {0: profile.margin + rank_overflow[0]}
    for level in range(1, max_rank + 1):
        gap_width = max(
            2 * profile.route_clearance
            + max(0, lane_count.get(level, 0) - 1) * profile.grid,
            profile.grid,
        )
        rank_x[level] = (
            rank_x[level - 1]
            + rank_width[level - 1]
            + rank_overflow[level - 1]
            + gap_width
            + rank_overflow[level]
        )
    positions = {
        name: (rank_x[rank[name]], y)
        for name, (_, y) in positions.items()
    }

    def lane_x(gap: int, key: tuple[str, str, int]) -> float:
        left = (
            rank_x[gap - 1]
            + rank_width[gap - 1]
            + rank_overflow[gap - 1]
        )
        return (
            left
            + profile.route_clearance
            + profile.grid * lane_index[(gap, *key)]
        )

    exact_visible_rects = {}
    visible_rects = {}
    for name, node in nodes.items():
        box = visual_box(
            name=name,
            label=node.shape.label,
            x=positions[name][0],
            y=positions[name][1],
            width=node.shape.w,
            height=node.shape.h,
        )
        exact_visible_rects[name] = (
            box.left, box.top, box.right, box.bottom
        )
        visible_rects[name] = box.inflated(profile.route_clearance)

    routed_segments: list[Any] = []
    routed_horizontal_occupancy: dict[
        float, list[tuple[float, float, tuple[str, str]]]
    ] = defaultdict(list)
    logical_fanout = Counter(
        (edge.source, edge.source_port) for edge in logical_edges
    )
    logical_outdegree = Counter(edge.source for edge in logical_edges)
    logical_indegree = Counter(edge.target for edge in logical_edges)
    # The spatial index cell follows the routing clearance scale.  A fixed
    # 256 px cell placed several independent rows in one bucket and made the
    # exact candidate checks approach quadratic growth on tall diagrams.
    route_bucket_size = max(
        profile.grid * 8.0,
        profile.route_clearance * 4.0,
    )
    routed_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    visible_buckets: dict[tuple[int, int], list[str]] = defaultdict(list)

    def segment_bucket_keys(a, b):
        min_x, max_x = sorted((a[0], b[0]))
        min_y, max_y = sorted((a[1], b[1]))
        for bx in range(
            math.floor(min_x / route_bucket_size),
            math.floor(max_x / route_bucket_size) + 1,
        ):
            for by in range(
                math.floor(min_y / route_bucket_size),
                math.floor(max_y / route_bucket_size) + 1,
            ):
                yield bx, by

    for name, rect in visible_rects.items():
        for bucket in segment_bucket_keys(
            (rect[0], rect[1]), (rect[2], rect[3])
        ):
            visible_buckets[bucket].append(name)

    def nearby_routed(segments):
        indices: set[int] = set()
        for a, b in segments:
            for bucket in segment_bucket_keys(a, b):
                indices.update(routed_buckets.get(bucket, ()))
        return [routed_segments[index] for index in indices]

    def candidate_obstacle_hits(edge, points):
        segments = [
            (a, b)
            for a, b in zip(points, points[1:])
            if a != b
        ]
        nearby_names: set[str] = set()
        for a, b in segments:
            for bucket in segment_bucket_keys(a, b):
                nearby_names.update(visible_buckets.get(bucket, ()))
        return {
            name
            for name in nearby_names
            for rect in (visible_rects[name],)
            if name not in (edge.source, edge.target)
            if any(
                _segment_hits_rect(a, b, rect)
                for a, b in segments
            )
        }

    def candidate_score(edge, points):
        segments = [
            (a, b)
            for a, b in zip(points, points[1:])
            if a != b
        ]
        clearance_hit_names = candidate_obstacle_hits(edge, points)
        clearance_hits = len(clearance_hit_names)
        exact_hits = sum(
            any(
                _segment_hits_rect(a, b, exact_visible_rects[name])
                for a, b in segments
            )
            for name in clearance_hit_names
        )
        net = (edge.source, edge.source_port)
        # A high-fanout source is one visual distribution net.  Counting every
        # logical branch against all earlier branches repeats the same bus
        # geometry quadratically and can even penalize the intended shared
        # trunk.  Its channel colouring already prevents distinct-net vertical
        # overlap; candidate choice here therefore needs only visible-box and
        # locality costs.
        local_prior = (
            [] if logical_fanout[net] > 1 else nearby_routed(segments)
        )
        crossings = sum(
            _proper_cross(
                Segment(edge.key, net, a, b), prior
            )
            for a, b in segments
            for prior in local_prior
            if prior.source_net != net
        )
        overlaps = sum(
            _overlap_length(
                Segment(edge.key, net, a, b), prior
            ) >= profile.grid
            for a, b in segments
            for prior in local_prior
            if prior.source_net != net
        )
        overlaps += sum(
            other_net != net
            and min(max(a[0], b[0]), other_high)
            - max(min(a[0], b[0]), other_low)
            >= profile.grid
            for a, b in segments
            if a[1] == b[1]
            for other_low, other_high, other_net
            in routed_horizontal_occupancy[a[1]]
        )
        bends = max(0, len(points) - 2)
        micro_segments = sum(
            0.01 < abs(b[0] - a[0]) + abs(b[1] - a[1]) < 1.0
            for a, b in segments
        )
        endpoint_low, endpoint_high = sorted((points[0][1], points[-1][1]))
        outer_excursion = max(
            0.0,
            endpoint_low - min(point[1] for point in points),
            max(point[1] for point in points) - endpoint_high,
        )
        length = sum(
            abs(b[0] - a[0]) + abs(b[1] - a[1])
            for a, b in segments
        )
        # Correctness/readability dominates compactness: never accept a
        # collinear overlap or avoidable crossing merely to save excursion.
        return (
            exact_hits,
            overlaps,
            crossings,
            bends,
            micro_segments,
            outer_excursion,
            clearance_hits,
            length,
        )

    edge_ids = {edge.key: f"e{index}" for index, edge in enumerate(logical_edges, 1)}
    layouts: list[EdgeLayout] = []
    selected_obstacle_hits = 0
    selected_overlaps = 0
    for edge in routing_order:
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
        edge_lane_key = route_lane_key[edge.key]
        candidates: list[list[tuple[float, float]]] = []
        if target_rank - source_rank > 1:
            first_x = lane_x(
                source_rank + 1, source_trunk_lane_key[edge.key]
            )
            last_x = lane_x(target_rank, edge_lane_key)
            lane_y = long_lanes[edge.key]
            candidates.append(_simplify(
                [(sx, sy), (first_x, sy), (first_x, lane_y),
                 (last_x, lane_y), (last_x, ty), (tx, ty)]
            ))
            # A two-bend route is preferred whenever either endpoint channel
            # can cross the intermediate ranks without hitting visible boxes.
            candidates.append(_simplify(
                [(sx, sy), (first_x, sy), (first_x, ty), (tx, ty)]
            ))
            if last_x != first_x and logical_fanout[source_key] == 1:
                candidates.append(_simplify(
                    [(sx, sy), (last_x, sy), (last_x, ty), (tx, ty)]
                ))
            # Expand the local visibility graph only around obstacles that an
            # initial route actually hits.  This discovers cross-domain label
            # and node boundaries without scanning every node for every edge.
            known = {tuple(candidate) for candidate in candidates}
            for _ in range(4):
                hit_names = {
                    name
                    for candidate in candidates
                    for name in candidate_obstacle_hits(edge, candidate)
                }
                added = False
                for name in sorted(hit_names):
                    rect = visible_rects[name]
                    for lane_y in (rect[1], rect[3]):
                        candidate = _simplify([
                            (sx, sy),
                            (first_x, sy),
                            (first_x, lane_y),
                            (last_x, lane_y),
                            (last_x, ty),
                            (tx, ty),
                        ])
                        key = tuple(candidate)
                        if key not in known:
                            known.add(key)
                            candidates.append(candidate)
                            added = True
                if not added or any(
                    not candidate_obstacle_hits(edge, candidate)
                    for candidate in candidates
                ):
                    break
        else:
            edge_lane_x = lane_x(
                target_rank, source_trunk_lane_key[edge.key]
            )
            if abs(sy - ty) <= 0.01:
                candidates.append([(sx, sy), (tx, ty)])
            else:
                candidates.append(_simplify(
                    [(sx, sy), (edge_lane_x, sy), (edge_lane_x, ty), (tx, ty)]
                ))
            first_x = edge_lane_x
        if logical_fanout[source_key] > 1:
            trunk_candidates = []
            for candidate in candidates:
                vertical_xs = [
                    a[0]
                    for a, b in zip(candidate, candidate[1:])
                    if abs(a[0] - b[0]) <= 1e-6
                    and abs(a[1] - b[1]) > 1e-6
                ]
                if not vertical_xs or abs(vertical_xs[0] - first_x) <= 1e-6:
                    trunk_candidates.append(candidate)
            if trunk_candidates and any(
                not candidate_obstacle_hits(edge, candidate)
                for candidate in trunk_candidates
            ):
                candidates = trunk_candidates
        selected_score, points = min(
            (candidate_score(edge, item), item) for item in candidates
        )
        selected_obstacle_hits += selected_score[0]
        selected_overlaps += selected_score[1]
        new_segments = [
            Segment(edge.key, source_key, a, b)
            for a, b in zip(points, points[1:])
            if a != b
        ]
        for segment in new_segments:
            index = len(routed_segments)
            routed_segments.append(segment)
            for bucket in segment_bucket_keys(segment.a, segment.b):
                routed_buckets[bucket].append(index)
            if segment.a[1] == segment.b[1]:
                x0, x1 = sorted((segment.a[0], segment.b[0]))
                routed_horizontal_occupancy[segment.a[1]].append(
                    (x0, x1, source_key)
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
    layouts.sort(key=lambda item: int(item.cell_id[1:]))

    # Deterministic rip-up/refine pass.  Online routing can only see earlier
    # edges; later long edges may make an earlier four-bend choice dominated.
    # Re-evaluate only such suspect routes against the complete route set and
    # replace them solely with an obstacle-free H-V-H route that has no more
    # overlaps/crossings and fewer bends.  This is part of route computation,
    # not an artifact-coordinate repair stage.
    logical_by_id = {
        edge_ids[edge.key]: edge for edge in logical_edges
    }

    def layout_points(layout, logical):
        source = nodes[logical.source]
        target = nodes[logical.target]
        start = abs_port_xy(
            *positions[logical.source], source.shape.w, source.shape.h,
            source.shape.style, source.shape.title, logical.source_port,
        )
        end = abs_port_xy(
            *positions[logical.target], target.shape.w, target.shape.h,
            target.shape.style, target.shape.title, logical.target_port,
        )
        return [start, *layout.waypoints, end]

    for _ in range(4):
        complete_segments: list[Segment] = []
        for layout in layouts:
            logical = logical_by_id[layout.cell_id]
            net = (logical.source, logical.source_port)
            points = layout_points(layout, logical)
            complete_segments.extend(
                Segment(logical.key, net, a, b)
                for a, b in zip(points, points[1:])
                if a != b
            )
        complete_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
        for index, segment in enumerate(complete_segments):
            for bucket in segment_bucket_keys(segment.a, segment.b):
                complete_buckets[bucket].append(index)
        changed = False
        for layout in layouts:
            logical = logical_by_id[layout.cell_id]
            points = layout_points(layout, logical)
            actual_bends = max(0, len(points) - 2)
            net = (logical.source, logical.source_port)
            local_merge_input = (
                logical_indegree[logical.target] > 1
                and logical_fanout[net] == 1
                and logical_outdegree[logical.source] <= 2
            )
            if actual_bends < 4 and not (
                local_merge_input and actual_bends >= 2
            ):
                continue

            def full_cost(candidate_points):
                segments = [
                    Segment(logical.key, net, a, b)
                    for a, b in zip(candidate_points, candidate_points[1:])
                    if a != b
                ]
                hits = len(candidate_obstacle_hits(logical, candidate_points))
                nearby_indices: set[int] = set()
                for segment in segments:
                    for bucket in segment_bucket_keys(segment.a, segment.b):
                        nearby_indices.update(complete_buckets.get(bucket, ()))
                other_segments = [
                    complete_segments[index]
                    for index in nearby_indices
                    if complete_segments[index].edge_key != logical.key
                    and complete_segments[index].source_net != net
                ]
                overlaps = sum(
                    _overlap_length(segment, other) >= profile.grid
                    for segment in segments
                    for other in other_segments
                )
                crossings = sum(
                    _proper_cross(segment, other)
                    for segment in segments
                    for other in other_segments
                )
                bends = max(0, len(candidate_points) - 2)
                micro_segments = sum(
                    0.01
                    < abs(b[0] - a[0]) + abs(b[1] - a[1])
                    < 1.0
                    for a, b in zip(candidate_points, candidate_points[1:])
                )
                length = sum(
                    abs(b[0] - a[0]) + abs(b[1] - a[1])
                    for a, b in zip(candidate_points, candidate_points[1:])
                )
                return hits, overlaps, crossings, bends, micro_segments, length

            actual_cost = full_cost(points)
            source_right = visible_rects[logical.source][2]
            target_left = visible_rects[logical.target][0]
            candidate_xs = {
                point[0]
                for point in points[1:-1]
                if source_right <= point[0] <= target_left
            }
            if source_right <= target_left:
                candidate_xs.update((
                    source_right,
                    (source_right + target_left) / 2.0,
                    target_left,
                ))
            if logical_fanout[net] > 1:
                candidate_xs = {
                    lane_x(
                        rank[logical.source] + 1,
                        source_trunk_lane_key[logical.key],
                    )
                }
            candidates = [
                _simplify([
                    points[0],
                    (x, points[0][1]),
                    (x, points[-1][1]),
                    points[-1],
                ])
                for x in sorted(candidate_xs)
            ]
            viable = [
                (full_cost(candidate), candidate)
                for candidate in candidates
                if full_cost(candidate)[0] == 0
            ]
            if not viable:
                continue
            best_cost, best_points = min(viable, key=lambda item: item[0])
            if (
                best_cost < actual_cost
                and best_cost[1] <= actual_cost[1]
                and best_cost[2] <= actual_cost[2]
                and best_cost[3] <= actual_cost[3]
            ):
                layout.waypoints = tuple(best_points[1:-1])
                changed = True
        if not changed:
            break

    # Layered-layout compaction phase.  Candidate routing conservatively
    # reserves both endpoint channels before it knows which one will win.
    # Re-colour only the channels that the final routes actually use, then
    # translate the complete right-hand suffix.  This is a coordinate
    # constraint pass over arbitrary ranks and ports, not image calibration.
    for level in range(1, max_rank + 1):
        left_names = by_rank[level - 1]
        right_names = by_rank[level]
        if not left_names or not right_names:
            continue
        left_edge = max(
            visual_box(
                name=name,
                label=nodes[name].shape.label,
                x=positions[name][0],
                y=positions[name][1],
                width=nodes[name].shape.w,
                height=nodes[name].shape.h,
            ).right
            for name in left_names
        )
        right_edge = min(
            visual_box(
                name=name,
                label=nodes[name].shape.label,
                x=positions[name][0],
                y=positions[name][1],
                width=nodes[name].shape.w,
                height=nodes[name].shape.h,
            ).left
            for name in right_names
        )
        used_lanes = set()
        for layout in layouts:
            logical = logical_by_id[layout.cell_id]
            points = layout_points(layout, logical)
            used_lanes.update(
                round(a[0], 6)
                for a, b in zip(points, points[1:])
                if a[0] == b[0] and left_edge < a[0] < right_edge
            )
        ordered_lanes = sorted(used_lanes)
        required_gap = 2 * profile.route_clearance + max(
            0, len(ordered_lanes) - 1
        ) * profile.grid
        delta = right_edge - left_edge - required_gap
        if delta <= 1e-6:
            continue
        lane_map = {
            old_x: left_edge + profile.route_clearance + index * profile.grid
            for index, old_x in enumerate(ordered_lanes)
        }
        for layout in layouts:
            compacted = []
            for x, y in layout.waypoints:
                rounded_x = round(x, 6)
                if rounded_x in lane_map:
                    x = lane_map[rounded_x]
                elif x >= right_edge - 1e-6:
                    x -= delta
                compacted.append((x, y))
            layout.waypoints = tuple(compacted)
        for name in nodes:
            if rank[name] >= level:
                x, y = positions[name]
                positions[name] = (x - delta, y)

    # Compaction can open a straight visibility channel that did not exist at
    # the conservative pre-routing width.  Re-evaluate only already aligned
    # endpoint pairs with spatial buckets; accept a straight route only when
    # it does not worsen exact obstacles, overlaps, or crossings.
    compact_rects = {}
    compact_rect_buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for name, node in nodes.items():
        box = visual_box(
            name=name,
            label=node.shape.label,
            x=positions[name][0],
            y=positions[name][1],
            width=node.shape.w,
            height=node.shape.h,
        )
        rect = (box.left, box.top, box.right, box.bottom)
        compact_rects[name] = rect
        for bucket in segment_bucket_keys(
            (rect[0], rect[1]), (rect[2], rect[3])
        ):
            compact_rect_buckets[bucket].append(name)
    def simplify_aligned_routes() -> bool:
        compact_segments: list[Segment] = []
        compact_segment_edges: list[str] = []
        compact_by_edge: dict[str, list[Segment]] = defaultdict(list)
        for layout in layouts:
            logical = logical_by_id[layout.cell_id]
            net = (logical.source, logical.source_port)
            points = layout_points(layout, logical)
            for a, b in zip(points, points[1:]):
                if a != b:
                    segment = Segment(logical.key, net, a, b)
                    compact_segments.append(segment)
                    compact_segment_edges.append(layout.cell_id)
                    compact_by_edge[layout.cell_id].append(segment)
        compact_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
        for index, segment in enumerate(compact_segments):
            for bucket in segment_bucket_keys(segment.a, segment.b):
                compact_buckets[bucket].append(index)
        changed = False
        for layout in layouts:
            logical = logical_by_id[layout.cell_id]
            points = layout_points(layout, logical)
            if (
                not layout.waypoints
                or abs(points[0][1] - points[-1][1]) > 1e-6
            ):
                continue
            direct = Segment(
                logical.key,
                (logical.source, logical.source_port),
                points[0],
                (points[-1][0], points[0][1]),
            )
            nearby_names: set[str] = set()
            nearby_indices: set[int] = set()
            for bucket in segment_bucket_keys(direct.a, direct.b):
                nearby_names.update(compact_rect_buckets.get(bucket, ()))
                nearby_indices.update(compact_buckets.get(bucket, ()))
            if any(
                name not in (logical.source, logical.target)
                and _segment_hits_rect(direct.a, direct.b, compact_rects[name])
                for name in nearby_names
            ):
                continue
            own_segments = compact_by_edge[layout.cell_id]
            actual_nearby = set(nearby_indices)
            for segment in own_segments:
                for bucket in segment_bucket_keys(segment.a, segment.b):
                    actual_nearby.update(compact_buckets.get(bucket, ()))

            def other_segments(indices):
                return [
                    compact_segments[index]
                    for index in indices
                    if compact_segment_edges[index] != layout.cell_id
                    and compact_segments[index].source_net != direct.source_net
                ]

            direct_others = other_segments(nearby_indices)
            actual_others = other_segments(actual_nearby)
            direct_cost = (
                sum(
                    _overlap_length(direct, other) >= profile.grid
                    for other in direct_others
                ),
                sum(_proper_cross(direct, other) for other in direct_others),
            )
            actual_cost = (
                sum(
                    _overlap_length(segment, other) >= profile.grid
                    for segment in own_segments for other in actual_others
                ),
                sum(
                    _proper_cross(segment, other)
                    for segment in own_segments for other in actual_others
                ),
            )
            if (
                direct_cost[0] <= actual_cost[0]
                and direct_cost[1] <= actual_cost[1]
            ):
                layout.waypoints = ()
                changed = True
        return changed

    for _ in range(3):
        if not simplify_aligned_routes():
            break
    document = LayoutDocument(
        version=LAYOUT_VERSION,
        vertices=_vertex_layouts(nodes, positions, library_path),
        edges=layouts,
    )

    indegree = {name: 0 for name in nodes}
    for edge in logical_edges:
        indegree[edge.target] += 1
    root_names = {name for name, degree in indegree.items() if degree == 0}
    unique_segments: dict[
        tuple[Any, ...], tuple[Segment, bool, Any]
    ] = {}
    for layout in layouts:
        logical = logical_by_id[layout.cell_id]
        net = (logical.source, logical.source_port)
        for a, b in zip(
            layout_points(layout, logical),
            layout_points(layout, logical)[1:],
        ):
            if a == b:
                continue
            orientation = "v" if a[0] == b[0] else "h"
            low, high = sorted((a, b))
            key = (orientation, low, high, net)
            unique_segments[key] = (
                Segment(logical.key, net, a, b),
                logical.source in root_names,
                logical,
            )
    metric_segments = list(unique_segments.values())
    metric_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, (segment, _, _) in enumerate(metric_segments):
        for bucket in segment_bucket_keys(segment.a, segment.b):
            metric_buckets[bucket].append(index)
    source_crossing_points: set[tuple[float, float]] = set()
    route_overlap_pairs: set[tuple[int, int]] = set()
    for index, (segment, is_root, _) in enumerate(metric_segments):
        nearby: set[int] = set()
        for bucket in segment_bucket_keys(segment.a, segment.b):
            nearby.update(metric_buckets[bucket])
        for other_index in nearby:
            if other_index == index:
                continue
            other, _, _ = metric_segments[other_index]
            if other.source_net == segment.source_net:
                continue
            if _overlap_length(segment, other) >= profile.grid:
                route_overlap_pairs.add(tuple(sorted((index, other_index))))
            if not is_root:
                continue
            if _proper_cross(segment, other):
                if segment.a[0] == segment.b[0]:
                    point = (segment.a[0], other.a[1])
                else:
                    point = (other.a[0], segment.a[1])
                source_crossing_points.add(
                    (round(point[0], 3), round(point[1], 3))
                )
    bend_total = sum(len(layout.waypoints) for layout in layouts)
    visible_bounds = [
        visual_box(
            name=name,
            label=node.shape.label,
            x=positions[name][0],
            y=positions[name][1],
            width=node.shape.w,
            height=node.shape.h,
        )
        for name, node in nodes.items()
    ]
    layout_area = (
        (max(box.right for box in visible_bounds) - min(box.left for box in visible_bounds))
        * (max(box.bottom for box in visible_bounds) - min(box.top for box in visible_bounds))
        if visible_bounds else 0.0
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return document, {
        "engine": "constraint-layered",
        "mode": (
            "adaptive-domain-decomposition"
            if plan.mode == "domain"
            else "global-port-axis"
        ),
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
            "source_position_mode": source_position_mode,
            "boundary_placed_roots": len(boundary_placed_roots),
            "fanout_nets_with_local_trunks": sum(
                count > 1 for count in fanout_trunk_clusters.values()
            ),
            "fanout_trunk_clusters_max": max(
                fanout_trunk_clusters.values(), default=0
            ),
            "source_crossing_points": len(source_crossing_points),
            "route_overlaps": len(route_overlap_pairs),
            "bends_total": bend_total,
            "visible_layout_area": round(layout_area, 3),
        },
    }


def _visible_layout_signature(
    document: LayoutDocument, logical_edges
) -> tuple[int, int, float, float]:
    """Return visible-node/edge failures and visible bounding dimensions."""
    boxes = {
        vertex.cell_id: vertex_visual_box(vertex)
        for vertex in document.vertices
    }
    vertices = document.vertices
    bucket_size = 256.0

    def keys(left: float, top: float, right: float, bottom: float):
        for bx in range(math.floor(left / bucket_size), math.floor(right / bucket_size) + 1):
            for by in range(math.floor(top / bucket_size), math.floor(bottom / bucket_size) + 1):
                yield bx, by

    node_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, vertex in enumerate(vertices):
        box = boxes[vertex.cell_id]
        for key in keys(box.left, box.top, box.right, box.bottom):
            node_buckets[key].append(index)
    overlap_pairs: set[tuple[int, int]] = set()
    for indices in node_buckets.values():
        for offset, index in enumerate(indices):
            for other_index in indices[offset + 1:]:
                overlap_pairs.add(tuple(sorted((index, other_index))))
    overlaps = sum(
        max(boxes[vertices[left].cell_id].left, boxes[vertices[right].cell_id].left)
        < min(boxes[vertices[left].cell_id].right, boxes[vertices[right].cell_id].right) - 1e-6
        and max(boxes[vertices[left].cell_id].top, boxes[vertices[right].cell_id].top)
        < min(boxes[vertices[left].cell_id].bottom, boxes[vertices[right].cell_id].bottom) - 1e-6
        for left, right in overlap_pairs
    )
    by_id = {vertex.cell_id: vertex for vertex in vertices}
    edge_by_id = {edge.cell_id: edge for edge in document.edges}
    hits = 0
    for index, logical in enumerate(logical_edges, 1):
        edge = edge_by_id[f"e{index}"]
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
        points = _simplify([start, *edge.waypoints, end])
        for a, b in zip(points, points[1:]):
            left, right = sorted((a[0], b[0]))
            top, bottom = sorted((a[1], b[1]))
            nearby: set[int] = set()
            for key in keys(left, top, right, bottom):
                nearby.update(node_buckets.get(key, ()))
            for vertex_index in nearby:
                vertex = vertices[vertex_index]
                if vertex.cell_id in (edge.source_id, edge.target_id):
                    continue
                box = boxes[vertex.cell_id]
                hits += int(_segment_hits_rect(
                    a, b, (box.left, box.top, box.right, box.bottom)
                ))
    min_x = min((box.left for box in boxes.values()), default=0.0)
    min_y = min((box.top for box in boxes.values()), default=0.0)
    max_x = max((box.right for box in boxes.values()), default=0.0)
    max_y = max((box.bottom for box in boxes.values()), default=0.0)
    return overlaps, hits, max_x - min_x, max_y - min_y


def _refine_joint_coordinates(
    document: LayoutDocument,
    logical_edges,
    *,
    eligible_vertex_ids: set[str] | None = None,
    route_clearance: float = 18.0,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Accept only type-independent node/route moves that dominate globally."""
    accepted = copy.deepcopy(document)
    accepted_report = None
    accepted_visible = None
    accepted_moves = 0
    bends_removed = 0
    blockers: Counter[str] = Counter()

    # Every accepted move strictly lowers total bends, so exhaustion is both
    # finite and complete; diagram size must not impose an arbitrary pass cap.
    while True:
        by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
        edge_by_id = {edge.cell_id: edge for edge in accepted.edges}

        def points_for(index: int):
            logical = logical_edges[index - 1]
            edge = edge_by_id[f"e{index}"]
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
            return _simplify([start, *edge.waypoints, end])

        incident: dict[str, list[int]] = defaultdict(list)
        suspect_moves: set[tuple[str, float]] = set()
        for index, logical in enumerate(logical_edges, 1):
            edge = edge_by_id[f"e{index}"]
            incident[edge.source_id].append(index)
            incident[edge.target_id].append(index)
            points = points_for(index)
            if max(0, len(points) - 2) < 4:
                continue
            axes = {
                a[1]
                for a, b in zip(points, points[1:])
                if abs(a[1] - b[1]) <= 1e-6 and abs(a[0] - b[0]) > 1e-6
            }
            for vertex_id, endpoint in (
                (edge.source_id, points[0]), (edge.target_id, points[-1])
            ):
                if (
                    eligible_vertex_ids is not None
                    and vertex_id not in eligible_vertex_ids
                ):
                    continue
                for axis in axes:
                    delta = axis - endpoint[1]
                    if abs(delta) > 1e-6:
                        suspect_moves.add((vertex_id, delta))
        viable_suspects: set[tuple[str, float]] = set()
        for vertex_id, delta in suspect_moves:
            old_bends = 0
            best_bends = 0
            old_length = 0.0
            best_length = 0.0
            for edge_index in incident[vertex_id]:
                edge = edge_by_id[f"e{edge_index}"]
                points = points_for(edge_index)
                old_bends += max(0, len(points) - 2)
                old_length += sum(
                    abs(b[0] - a[0]) + abs(b[1] - a[1])
                    for a, b in zip(points, points[1:])
                )
                start = (
                    points[0][0],
                    points[0][1]
                    + (delta if edge.source_id == vertex_id else 0.0),
                )
                end = (
                    points[-1][0],
                    points[-1][1]
                    + (delta if edge.target_id == vertex_id else 0.0),
                )
                best_bends += 0 if abs(start[1] - end[1]) <= 1e-6 else 2
                best_length += (
                    abs(end[0] - start[0])
                    + abs(end[1] - start[1])
                )
            if (
                best_bends < old_bends
                and best_length <= old_length + 1e-6
            ):
                viable_suspects.add((vertex_id, delta))
        suspect_moves = viable_suspects
        if not suspect_moves:
            break

        spatial_size = 80.0

        def spatial_keys(a, b):
            left, right = sorted((a[0], b[0]))
            top, bottom = sorted((a[1], b[1]))
            for bx in range(math.floor(left / spatial_size), math.floor(right / spatial_size) + 1):
                for by in range(math.floor(top / spatial_size), math.floor(bottom / spatial_size) + 1):
                    yield bx, by

        base_segments: list[tuple[int, Segment]] = []
        segment_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
        for edge_index, logical in enumerate(logical_edges, 1):
            net = (logical.source, logical.source_port)
            points = points_for(edge_index)
            for a, b in zip(points, points[1:]):
                if a == b:
                    continue
                segment_index = len(base_segments)
                base_segments.append((
                    edge_index,
                    Segment(logical.key, net, a, b),
                ))
                for key in spatial_keys(a, b):
                    segment_buckets[key].append(segment_index)

        visible_boxes = {
            vertex.cell_id: vertex_visual_box(vertex)
            for vertex in accepted.vertices
        }
        node_buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
        for cell_id, box in visible_boxes.items():
            for key in spatial_keys((box.left, box.top), (box.right, box.bottom)):
                node_buckets[key].append(cell_id)

        def local_option_score(
            option,
            edge_index: int,
            excluded_edges: set[int],
            selected_segments: list[Segment],
        ):
            logical = logical_edges[edge_index - 1]
            edge = edge_by_id[f"e{edge_index}"]
            net = (logical.source, logical.source_port)
            option_segments = [
                Segment(logical.key, net, a, b)
                for a, b in zip(option, option[1:])
                if a != b
            ]
            source_box = visible_boxes[edge.source_id]
            target_box = visible_boxes[edge.target_id]
            lead_violations = int(
                len(option) > 2
                and option[1][0]
                < source_box.right + route_clearance - 1e-6
            ) + int(
                len(option) > 2
                and option[-2][0]
                > target_box.left - route_clearance + 1e-6
            )
            nearby_nodes: set[str] = set()
            nearby_segments: set[int] = set()
            for segment in option_segments:
                for key in spatial_keys(segment.a, segment.b):
                    nearby_nodes.update(node_buckets.get(key, ()))
                    nearby_segments.update(segment_buckets.get(key, ()))
            hits = sum(
                _segment_hits_rect(
                    segment.a,
                    segment.b,
                    (
                        visible_boxes[cell_id].left,
                        visible_boxes[cell_id].top,
                        visible_boxes[cell_id].right,
                        visible_boxes[cell_id].bottom,
                    ),
                )
                for segment in option_segments
                for cell_id in nearby_nodes
                if cell_id not in (edge.source_id, edge.target_id)
            )
            others = [
                segment
                for index in nearby_segments
                for owner, segment in (base_segments[index],)
                if owner not in excluded_edges
                and segment.source_net != net
            ]
            overlaps = sum(
                _overlap_length(segment, other) > 1e-6
                for segment in option_segments
                for other in others
            )
            crossings = sum(
                _proper_cross(segment, other)
                for segment in option_segments
                for other in others
            )
            overlaps += sum(
                _overlap_length(segment, other) > 1e-6
                and segment.source_net != other.source_net
                for segment in option_segments
                for other in selected_segments
            )
            crossings += sum(
                _proper_cross(segment, other)
                for segment in option_segments
                for other in selected_segments
            )
            return (
                lead_violations,
                hits,
                overlaps,
                crossings,
                max(0, len(option) - 2),
                sum(
                    abs(b[0] - a[0]) + abs(b[1] - a[1])
                    for a, b in zip(option, option[1:])
                ),
                tuple(option),
            )
        changed = False
        touched_edges: set[int] = set()
        moved_vertices: set[str] = set()
        for vertex_id, delta in sorted(
            suspect_moves,
            key=lambda item: (abs(item[1]), item[0], item[1]),
        ):
            if (
                vertex_id in moved_vertices
                or touched_edges.intersection(incident[vertex_id])
            ):
                continue
            incident_old_points = {
                edge_index: points_for(edge_index)
                for edge_index in incident[vertex_id]
            }
            old_incident_bends = sum(
                max(0, len(points) - 2)
                for points in incident_old_points.values()
            )
            old_incident_length = sum(
                abs(b[0] - a[0]) + abs(b[1] - a[1])
                for points in incident_old_points.values()
                for a, b in zip(points, points[1:])
            )
            candidate = copy.deepcopy(accepted)
            candidate_by_id = {
                vertex.cell_id: vertex for vertex in candidate.vertices
            }
            candidate_edge_by_id = {
                edge.cell_id: edge for edge in candidate.edges
            }
            candidate_by_id[vertex_id].y += delta
            valid_routes = True
            selected_candidate_segments: list[Segment] = []
            for edge_index in incident[vertex_id]:
                logical = logical_edges[edge_index - 1]
                old_points = incident_old_points[edge_index]
                edge = candidate_edge_by_id[f"e{edge_index}"]
                source = candidate_by_id[edge.source_id]
                target = candidate_by_id[edge.target_id]
                start = abs_port_xy(
                    source.x, source.y, source.width, source.height,
                    source.style, source.drawclock_type, logical.source_port,
                )
                end = abs_port_xy(
                    target.x, target.y, target.width, target.height,
                    target.style, target.drawclock_type, logical.target_port,
                )
                vertical_xs = [
                    a[0]
                    for a, b in zip(old_points, old_points[1:])
                    if abs(a[0] - b[0]) <= 1e-6
                    and abs(a[1] - b[1]) > 1e-6
                ]
                if abs(start[1] - end[1]) <= 1e-6:
                    options = [[start, end]]
                else:
                    if not vertical_xs:
                        vertical_xs = [(start[0] + end[0]) / 2.0]
                    source_box = vertex_visual_box(source)
                    target_box = vertex_visual_box(target)
                    channel_left = source_box.right + route_clearance
                    channel_right = target_box.left - route_clearance
                    if channel_left <= channel_right + 1e-6:
                        vertical_xs.extend((
                            channel_left,
                            (channel_left + channel_right) / 2.0,
                            channel_right,
                        ))
                    options = [
                        _simplify([
                            start,
                            (x, start[1]),
                            (x, end[1]),
                            end,
                        ])
                        for x in dict.fromkeys(vertical_xs)
                    ]
                best_option = None
                best_signature = None
                for option in options:
                    signature = local_option_score(
                        option,
                        edge_index,
                        set(incident[vertex_id]),
                        selected_candidate_segments,
                    )
                    if best_signature is None or signature < best_signature:
                        best_signature = signature
                        best_option = tuple(option[1:-1])
                if best_option is None:
                    valid_routes = False
                    break
                edge.waypoints = best_option
                selected_candidate_segments.extend(
                    Segment(
                        logical.key,
                        (logical.source, logical.source_port),
                        a,
                        b,
                    )
                    for a, b in zip(
                        [start, *best_option, end],
                        [start, *best_option, end][1:],
                    )
                    if a != b
                )
            if not valid_routes:
                continue
            candidate_incident_points = {
                edge_index: _simplify([
                    abs_port_xy(
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].source_id].x,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].source_id].y,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].source_id].width,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].source_id].height,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].source_id].style,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].source_id].drawclock_type,
                        logical_edges[edge_index - 1].source_port,
                    ),
                    *candidate_edge_by_id[f"e{edge_index}"].waypoints,
                    abs_port_xy(
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].target_id].x,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].target_id].y,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].target_id].width,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].target_id].height,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].target_id].style,
                        candidate_by_id[candidate_edge_by_id[f"e{edge_index}"].target_id].drawclock_type,
                        logical_edges[edge_index - 1].target_port,
                    ),
                ])
                for edge_index in incident[vertex_id]
            }
            candidate_incident_bends = sum(
                max(0, len(points) - 2)
                for points in candidate_incident_points.values()
            )
            candidate_incident_length = sum(
                abs(b[0] - a[0]) + abs(b[1] - a[1])
                for points in candidate_incident_points.values()
                for a, b in zip(points, points[1:])
            )
            if (
                candidate_incident_bends >= old_incident_bends
                or candidate_incident_length
                > old_incident_length + 1e-6
            ):
                blockers[
                    "no-local-bend-dominance"
                    if candidate_incident_bends >= old_incident_bends
                    else "local-length"
                ] += 1
                continue
            if accepted_report is None:
                accepted_report = assess_layout(
                    accepted, logical_edges, 0.0
                )
                accepted_visible = _visible_layout_signature(
                    accepted, logical_edges
                )
            candidate_report = assess_layout(candidate, logical_edges, 0.0)
            candidate_visible = _visible_layout_signature(
                candidate, logical_edges
            )
            dominates = (
                accepted_visible is not None
                and
                candidate_report["node_overlaps"] <= accepted_report["node_overlaps"]
                and candidate_report["edge_node_intersections"]
                <= accepted_report["edge_node_intersections"]
                and candidate_report["direction_violations"]
                <= accepted_report["direction_violations"]
                and candidate_visible[0] <= accepted_visible[0]
                and candidate_visible[1] <= accepted_visible[1]
                and candidate_report["ambiguous_overlaps"]
                <= accepted_report["ambiguous_overlaps"]
                and candidate_report["crossings"] <= accepted_report["crossings"]
                and candidate_report["bends_total"] < accepted_report["bends_total"]
                and candidate_report["manhattan_length"]
                <= accepted_report["manhattan_length"] + 1e-6
                and candidate_visible[2] <= accepted_visible[2] + 1e-6
                and candidate_visible[3] <= accepted_visible[3] + 1e-6
            )
            if not dominates:
                checks = {
                    "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
                    "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
                    "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
                    "visible-overlap": candidate_visible[0] <= accepted_visible[0],
                    "visible-edge-node": candidate_visible[1] <= accepted_visible[1],
                    "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
                    "crossing": candidate_report["crossings"] <= accepted_report["crossings"],
                    "bend": candidate_report["bends_total"] < accepted_report["bends_total"],
                    "length": candidate_report["manhattan_length"] <= accepted_report["manhattan_length"] + 1e-6,
                    "visible-width": candidate_visible[2] <= accepted_visible[2] + 1e-6,
                    "visible-height": candidate_visible[3] <= accepted_visible[3] + 1e-6,
                }
                blockers.update(name for name, passed in checks.items() if not passed)
                continue
            bends_removed += (
                accepted_report["bends_total"]
                - candidate_report["bends_total"]
            )
            accepted = candidate
            accepted_report = candidate_report
            accepted_visible = candidate_visible
            accepted_moves += 1
            changed = True
            moved_vertices.add(vertex_id)
            touched_edges.update(incident[vertex_id])
        if not changed:
            break
    return accepted, {
        "joint_coordinate_moves": accepted_moves,
        "joint_coordinate_bends_removed": bends_removed,
        "joint_coordinate_blockers": dict(sorted(blockers.items())),
    }


def _optimal_source_anchor_partitions(
    samples: list[tuple[float, int]], fixed_cost: float
) -> list[list[int]]:
    """Solve contiguous L1 facilities across independently justified gaps."""
    ordered = sorted(samples)
    count = len(ordered)
    if count <= 1:
        return [[item[1] for item in ordered]] if ordered else []
    values = [item[0] for item in ordered]
    # A rendering alias is reserved for a genuinely separated consumer band:
    # the empty interval at a cut must by itself repay one alias' complete
    # service cost.  This prevents a uniform tall fanout from degenerating
    # into hundreds of aliases while retaining exact DP inside admissible
    # distant-band boundaries.
    adjacent_gaps = [
        values[index] - values[index - 1]
        for index in range(1, count)
    ]
    local_gap = median(adjacent_gaps)
    admissible_left = {0} | {
        index
        for index in range(1, count)
        if (
            values[index] - values[index - 1] > fixed_cost
            if count == 2
            else values[index] - values[index - 1] - local_gap
            > fixed_cost
        )
    }
    prefix = [0.0]
    for value in values:
        prefix.append(prefix[-1] + value)

    def interval_cost(left: int, right: int) -> float:
        middle = (left + right - 1) // 2
        pivot = values[middle]
        lower = pivot * (middle - left) - (prefix[middle] - prefix[left])
        upper = (prefix[right] - prefix[middle + 1]) - pivot * (right - middle - 1)
        return lower + upper

    best = [float("inf")] * (count + 1)
    previous = [-1] * (count + 1)
    best[0] = -fixed_cost
    for right in range(1, count + 1):
        for left in range(right):
            if left not in admissible_left:
                continue
            score = best[left] + fixed_cost + interval_cost(left, right)
            if score < best[right] - 1e-9:
                best[right] = score
                previous[right] = left
    partitions: list[list[int]] = []
    right = count
    while right:
        left = previous[right]
        partitions.append([ordered[index][1] for index in range(left, right)])
        right = left
    partitions.reverse()
    return partitions


def _replicate_dispersed_roots(
    document: LayoutDocument,
    nodes,
    logical_edges,
    profile,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Add rendering anchors only when a zero-indegree source wins globally."""
    indegree = Counter(edge.target for edge in logical_edges)
    outgoing: dict[str, list[int]] = defaultdict(list)
    for index, logical in enumerate(logical_edges, 1):
        outgoing[logical.source].append(index)
    accepted = copy.deepcopy(document)
    accepted_report = assess_layout(accepted, logical_edges, 0.0)
    initial_report = dict(accepted_report)
    accepted_roots = 0
    accepted_replicas = 0
    candidate_roots = 0
    replica_blockers: Counter[str] = Counter()

    def edge_points(
        doc: LayoutDocument,
        edge_index: int,
        by_id=None,
        edge_by_id=None,
    ):
        if edge_by_id is None:
            edge_by_id = {edge.cell_id: edge for edge in doc.edges}
        edge = edge_by_id[f"e{edge_index}"]
        logical = logical_edges[edge_index - 1]
        if by_id is None:
            by_id = {vertex.cell_id: vertex for vertex in doc.vertices}
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
        return edge, source, target, _simplify([start, *edge.waypoints, end])

    for root in sorted(nodes):
        if indegree[root] or len(outgoing[root]) < 2:
            continue
        by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
        accepted_edge_by_id = {
            edge.cell_id: edge for edge in accepted.edges
        }
        original = by_id.get(nodes[root].cell_id)
        if original is None:
            continue
        desired: list[tuple[float, int]] = []
        horizontal_service: list[float] = []
        for edge_index in outgoing[root]:
            _, _, target, points = edge_points(
                accepted, edge_index, by_id, accepted_edge_by_id
            )
            logical = logical_edges[edge_index - 1]
            source_anchor = port_anchors(
                original.style, original.drawclock_type
            )[logical.source_port][1]
            desired.append((points[-1][1] - original.height * source_anchor, edge_index))
            horizontal_service.append(
                max(0.0, target.x - original.x - original.width)
            )
        fixed_cost = (
            median(horizontal_service or [profile.layer_spacing])
            + original.height
            + 2 * profile.route_clearance
        )
        partitions = _optimal_source_anchor_partitions(desired, fixed_cost)
        if len(partitions) <= 1:
            continue
        candidate_roots += 1
        candidate = copy.deepcopy(accepted)
        candidate_by_id = {vertex.cell_id: vertex for vertex in candidate.vertices}
        candidate_original = candidate_by_id[original.cell_id]
        anchors = [candidate_original]
        for replica_index in range(1, len(partitions)):
            replica = copy.copy(candidate_original)
            replica.name = f"{root}__anchor_{replica_index + 1}"
            replica.cell_id = f"{candidate_original.cell_id}a{replica_index + 1}"
            replica.logical_name = root
            anchors.append(replica)
            candidate.vertices.append(replica)

        anchor_ids = {anchor.cell_id for anchor in anchors}
        occupied: list[tuple[float, float]] = []
        for vertex in candidate.vertices:
            if vertex.cell_id in anchor_ids:
                continue
            box = vertex_visual_box(vertex)
            original_box = vertex_visual_box(candidate_original)
            if box.right <= original_box.left or box.left >= original_box.right:
                continue
            occupied.append((box.top, box.bottom))
        outgoing_set = set(outgoing[root])
        for other_edge_index in range(1, len(logical_edges) + 1):
            if other_edge_index in outgoing_set:
                continue
            _, _, _, other_points = edge_points(
                accepted,
                other_edge_index,
                by_id,
                accepted_edge_by_id,
            )
            for a, b in zip(other_points, other_points[1:]):
                left, right = sorted((a[0], b[0]))
                if right < original_box.left or left > original_box.right:
                    continue
                top, bottom = sorted((a[1], b[1]))
                occupied.append((
                    top - profile.grid,
                    bottom + profile.grid,
                ))
        placed: list[tuple[float, float]] = []
        for anchor, partition in zip(anchors, partitions):
            tops = [value for value, edge_index in desired if edge_index in partition]
            ordered_tops = sorted(tops)
            # Any point in the even-sample median interval is L1-optimal.
            # Selecting an actual consumer axis, rather than the arithmetic
            # midpoint, preserves that optimum and maximizes straight leads.
            wanted = ordered_tops[(len(ordered_tops) - 1) // 2]
            intervals = sorted(occupied + placed)
            top = wanted
            for low, high in intervals:
                if top + anchor.height + profile.grid > low and top < high + profile.grid:
                    before = low - profile.grid - anchor.height
                    after = high + profile.grid
                    top = min((before, after), key=lambda value: (abs(value - wanted), value))
            anchor.y = top
            placed.append((top, top + anchor.height))

        edge_by_id = {edge.cell_id: edge for edge in candidate.edges}
        for anchor, partition in zip(anchors, partitions):
            for edge_index in partition:
                edge = edge_by_id[f"e{edge_index}"]
                logical = logical_edges[edge_index - 1]
                old_edge, _, target, old_points = edge_points(
                    accepted,
                    edge_index,
                    by_id,
                    accepted_edge_by_id,
                )
                edge.source_id = anchor.cell_id
                start = abs_port_xy(
                    anchor.x, anchor.y, anchor.width, anchor.height,
                    anchor.style, anchor.drawclock_type, logical.source_port,
                )
                end = abs_port_xy(
                    target.x, target.y, target.width, target.height,
                    target.style, target.drawclock_type, logical.target_port,
                )
                if old_edge.waypoints:
                    channel_left = (
                        vertex_visual_box(anchor).right
                        + profile.route_clearance
                    )
                    channel_right = (
                        vertex_visual_box(target).left
                        - profile.route_clearance
                    )
                    first_x = old_points[1][0]
                    if channel_left <= channel_right + 1e-6:
                        first_x = min(
                            max(first_x, channel_left),
                            channel_right,
                        )
                    points = _simplify([
                        start,
                        (first_x, start[1]),
                        *old_points[2:-1],
                        end,
                    ])
                elif abs(start[1] - end[1]) <= 1e-6:
                    points = [start, end]
                else:
                    channel_left = (
                        vertex_visual_box(anchor).right
                        + profile.route_clearance
                    )
                    channel_right = (
                        vertex_visual_box(target).left
                        - profile.route_clearance
                    )
                    first_x = (
                        (channel_left + channel_right) / 2.0
                        if channel_left <= channel_right + 1e-6
                        else (start[0] + end[0]) / 2.0
                    )
                    points = _simplify([
                        start,
                        (first_x, start[1]),
                        (first_x, end[1]),
                        end,
                    ])
                edge.waypoints = tuple(points[1:-1])

        candidate.vertices.sort(key=lambda vertex: vertex.name)
        candidate_report = assess_layout(candidate, logical_edges, 0.0)
        replica_cost = fixed_cost * (len(partitions) - 1)
        improves_distribution = (
            candidate_report["crossings"] < accepted_report["crossings"]
            or candidate_report["manhattan_length"] + replica_cost
            < accepted_report["manhattan_length"] - 1e-6
        )
        checks = {
            "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
            "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
            "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
            "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
            "crossing": candidate_report["crossings"] <= accepted_report["crossings"],
            "bend": candidate_report["bends_total"] <= accepted_report["bends_total"],
            "area": candidate_report["area"] <= accepted_report["area"] + 1e-6,
            "distribution": improves_distribution,
        }
        if (
            checks["node-overlap"]
            and candidate_report["edge_node_intersections"]
            <= accepted_report["edge_node_intersections"]
            and candidate_report["direction_violations"]
            <= accepted_report["direction_violations"]
            and candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"]
            and candidate_report["crossings"] <= accepted_report["crossings"]
            and candidate_report["bends_total"] <= accepted_report["bends_total"]
            and candidate_report["area"] <= accepted_report["area"] + 1e-6
            and improves_distribution
        ):
            accepted = candidate
            accepted_report = candidate_report
            accepted_roots += 1
            accepted_replicas += len(partitions) - 1
        else:
            replica_blockers.update(
                name for name, passed in checks.items() if not passed
            )
    return accepted, {
        "source_replica_candidate_roots": candidate_roots,
        "source_replicated_roots": accepted_roots,
        "source_rendering_replicas": accepted_replicas,
        "source_replica_crossings_removed": (
            initial_report["crossings"] - accepted_report["crossings"]
        ),
        "source_replica_length_saved_px": round(
            initial_report["manhattan_length"]
            - accepted_report["manhattan_length"],
            3,
        ),
        "source_replica_blockers": dict(sorted(replica_blockers.items())),
    }


def generate_elk_layout(
    config: dict[str, dict[str, Any]],
    *,
    library_path: str | Path,
    component_hints: dict[str, str] | None = None,
    profile_name: str = "readable",
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Compute exact-rank, exact-port layout with one deterministic policy."""
    started = time.perf_counter()
    if profile_name not in PROFILES:
        raise ValueError(f"未知布局 profile: {profile_name}")
    validate_config(config, library_path=library_path)
    shapes = load_library_shapes(library_path)
    nodes = resolve_nodes(
        config, shapes, component_hints or {}, library_path=library_path
    )
    logical_edges = build_logical_edges(config, nodes, library_path)
    profile = PROFILES[profile_name]
    plan = select_layout_plan(nodes, logical_edges)
    indegree = {name: 0 for name in nodes}
    outdegree = Counter(edge.source for edge in logical_edges)
    for edge in logical_edges:
        indegree[edge.target] += 1
    root_count = sum(degree == 0 for degree in indegree.values())
    source_modes = ["adaptive-span"]
    candidates = []
    for source_mode in source_modes:
        document, report = _generate_scalable_layout(
            nodes,
            logical_edges,
            profile,
            time.perf_counter(),
            library_path,
            plan,
            source_position_mode=source_mode,
        )
        selection = report["selection"]
        score = (
            selection["route_overlaps"],
            selection["source_crossing_points"],
            selection["bends_total"],
            selection["visible_layout_area"],
            source_mode,
        )
        candidates.append((score, document, report))
    # Consumer-median placement is the general minimum-lead solution.  A
    # second full routing pass is warranted only when that solution cannot
    # satisfy the hard distinct-net overlap constraint; this keeps the common
    # path linear without a graph-size boundary.
    if (
        root_count > 1
        and plan.backbone
        and candidates[0][2]["selection"]["route_overlaps"] > 0
    ):
        document, report = _generate_scalable_layout(
            nodes,
            logical_edges,
            profile,
            time.perf_counter(),
            library_path,
            plan,
            source_position_mode="top-aligned",
        )
        selection = report["selection"]
        score = (
            selection["route_overlaps"],
            selection["source_crossing_points"],
            selection["bends_total"],
            selection["visible_layout_area"],
            "top-aligned",
        )
        candidates.append((score, document, report))
    _, document, report = min(candidates, key=lambda item: item[0])
    fanout_by_net = Counter(
        (edge.source, edge.source_port) for edge in logical_edges
    )
    source_ports: dict[str, set[str]] = defaultdict(set)
    incoming_edges: dict[str, list[Any]] = defaultdict(list)
    for edge in logical_edges:
        source_ports[edge.source].add(edge.source_port)
        incoming_edges[edge.target].append(edge)

    def joint_coordinate_safe(name: str) -> bool:
        return all(
            not (
                indegree[edge.source] == 0
                and fanout_by_net[(edge.source, edge.source_port)] > 1
            )
            and len(source_ports[edge.source]) <= 1
            for edge in incoming_edges[name]
        )

    non_root_vertex_ids = {
        vertex.cell_id
        for vertex in document.vertices
        if indegree[vertex.logical_name or vertex.name] > 0
        and outdegree[vertex.logical_name or vertex.name] <= 1
        and joint_coordinate_safe(vertex.logical_name or vertex.name)
    }
    document, joint_report = _refine_joint_coordinates(
        document,
        logical_edges,
        eligible_vertex_ids=non_root_vertex_ids,
        route_clearance=profile.route_clearance,
    )
    report["selection"].update(joint_report)
    document, replica_report = _replicate_dispersed_roots(
        document, nodes, logical_edges, profile
    )
    report["selection"].update(replica_report)
    refined = assess_layout(document, logical_edges, 0.0)
    report["selection"].update({
        "source_crossing_points": refined["source_crossing_points"],
        "route_overlaps": refined["ambiguous_overlaps"],
        "bends_total": refined["bends_total"],
        "visible_layout_area": refined["area"],
    })
    report["runtime_ms"] = round((time.perf_counter() - started) * 1000, 3)
    report["selection"]["source_position_candidates"] = [
        {
            "mode": candidate_report["selection"]["source_position_mode"],
            "route_overlaps": candidate_report["selection"]["route_overlaps"],
            "source_crossing_points": candidate_report["selection"]["source_crossing_points"],
            "bends_total": candidate_report["selection"]["bends_total"],
            "visible_layout_area": candidate_report["selection"]["visible_layout_area"],
        }
        for _, _, candidate_report in candidates
    ]
    return document, report


def _generate_elk_reference_layout(
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
    runtime = _elk_runtime()
    if runtime is None:
        raise ValueError("ELK 布局运行时不可用；发布包应包含 runtime/node 与 runtime/elk")
    node_executable, script, runtime_cwd = runtime

    validate_config(config, library_path=library_path)
    shapes = load_library_shapes(library_path)
    nodes = resolve_nodes(
        config, shapes, component_hints or {}, library_path=library_path
    )
    logical_edges = build_logical_edges(config, nodes, library_path)
    profile = PROFILES[profile_name]
    plan = select_layout_plan(nodes, logical_edges)
    rank = _ranks(nodes, logical_edges)
    if plan.mode == "domain":
        return _generate_scalable_layout(
            nodes, logical_edges, profile, started, library_path, plan
        )
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
            "rank": rank[name],
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
                cwd=runtime_cwd,
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
        vertices=_vertex_layouts(nodes, positions, library_path),
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
