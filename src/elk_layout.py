from __future__ import annotations

import heapq
import math
import copy
import sys
import time
from collections import Counter, defaultdict
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from statistics import median
from typing import Any

from auto_layout import (
    PROFILES,
    _mean,
    _layout_column_groups,
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
from drawio_library import LibrarySource, library_cache_key, load_library_shapes
from drawio_ports import EDGE_DRAW_STYLE, port_anchors
from drawio_ports import abs_port_xy
from validate_config import validate_config
from visual_geometry import estimated_label_width, vertex_visual_box, visual_box


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
    column_groups = _layout_column_groups(nodes)
    rank = _ranks(nodes, logical_edges, column_groups)
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
    column_groups = _layout_column_groups(nodes)
    rank = _ranks(nodes, logical_edges, column_groups)
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

    candidate_obstacle_cache: dict[
        tuple[str, tuple[tuple[float, float], ...]], frozenset[str]
    ] = {}

    def candidate_obstacle_hits(edge, points):
        cache_key = (edge.key, tuple(points))
        cached = candidate_obstacle_cache.get(cache_key)
        if cached is not None:
            return cached
        segments = [
            (a, b)
            for a, b in zip(points, points[1:])
            if a != b
        ]
        nearby_names: set[str] = set()
        for a, b in segments:
            for bucket in segment_bucket_keys(a, b):
                nearby_names.update(visible_buckets.get(bucket, ()))
        hits = frozenset(
            name
            for name in nearby_names
            for rect in (visible_rects[name],)
            if name not in (edge.source, edge.target)
            if any(
                _segment_hits_rect(a, b, rect)
                for a, b in segments
            )
        )
        candidate_obstacle_cache[cache_key] = hits
        return hits

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
    ordered_column_groups = sorted(column_groups.items())
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
            "layout_column_groups": len(column_groups),
            "layout_column_aligned": sum(
                len({rank[name] for name in names}) == 1
                for names in column_groups.values()
            ),
            "layout_column_order_violations": sum(
                max(rank[name] for name in left_names)
                >= min(rank[name] for name in right_names)
                for (_, left_names), (_, right_names) in zip(
                    ordered_column_groups,
                    ordered_column_groups[1:],
                )
            ),
            "layout_column_max_span": max(
                (
                    max(rank[name] for name in names)
                    - min(rank[name] for name in names)
                    for names in column_groups.values()
                ),
                default=0,
            ),
        },
    }


def _visible_layout_signature(
    document: LayoutDocument,
    logical_edges,
    edge_indices: set[int] | None = None,
    focus_vertex_ids: set[str] | None = None,
) -> tuple[int, int, float, float, frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
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
    if focus_vertex_ids is None:
        for indices in node_buckets.values():
            for offset, index in enumerate(indices):
                for other_index in indices[offset + 1:]:
                    overlap_pairs.add(tuple(sorted((index, other_index))))
    else:
        for index, vertex in enumerate(vertices):
            if vertex.cell_id not in focus_vertex_ids:
                continue
            box = boxes[vertex.cell_id]
            nearby = set()
            for key in keys(box.left, box.top, box.right, box.bottom):
                nearby.update(node_buckets.get(key, ()))
            overlap_pairs.update(
                tuple(sorted((index, other_index)))
                for other_index in nearby
                if other_index != index
            )
    visible_overlap_pairs = frozenset(
        tuple(sorted((vertices[left].cell_id, vertices[right].cell_id)))
        for left, right in overlap_pairs
        if (
            max(boxes[vertices[left].cell_id].left, boxes[vertices[right].cell_id].left)
            < min(boxes[vertices[left].cell_id].right, boxes[vertices[right].cell_id].right) - 1e-6
            and max(boxes[vertices[left].cell_id].top, boxes[vertices[right].cell_id].top)
            < min(boxes[vertices[left].cell_id].bottom, boxes[vertices[right].cell_id].bottom) - 1e-6
        )
    )
    by_id = {vertex.cell_id: vertex for vertex in vertices}
    edge_by_id = {edge.cell_id: edge for edge in document.edges}
    visible_hit_pairs: set[tuple[str, str]] = set()
    selected_indices = (
        range(1, len(logical_edges) + 1)
        if edge_indices is None else sorted(edge_indices)
    )
    for index in selected_indices:
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
                if _segment_hits_rect(
                    a, b, (box.left, box.top, box.right, box.bottom)
                ):
                    visible_hit_pairs.add((edge.cell_id, vertex.cell_id))
    min_x = min((box.left for box in boxes.values()), default=0.0)
    min_y = min((box.top for box in boxes.values()), default=0.0)
    max_x = max((box.right for box in boxes.values()), default=0.0)
    max_y = max((box.bottom for box in boxes.values()), default=0.0)
    return (
        len(visible_overlap_pairs),
        len(visible_hit_pairs),
        max_x - min_x,
        max_y - min_y,
        visible_overlap_pairs,
        frozenset(visible_hit_pairs),
    )


def _route_endpoint_signature(
    document: LayoutDocument,
    logical_edges,
    edge_indices: set[int],
    clearance: float,
) -> frozenset[tuple[str, str]]:
    """Return hard endpoint-clearance and micro-segment failures."""
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    edge_by_id = {edge.cell_id: edge for edge in document.edges}
    failures: set[tuple[str, str]] = set()
    for index in sorted(edge_indices):
        edge = edge_by_id[f"e{index}"]
        logical = logical_edges[index - 1]
        source = by_id[edge.source_id]
        target = by_id[edge.target_id]
        points = [
            abs_port_xy(
                source.x, source.y, source.width, source.height,
                source.style, source.drawclock_type, logical.source_port,
            ),
            *edge.waypoints,
            abs_port_xy(
                target.x, target.y, target.width, target.height,
                target.style, target.drawclock_type, logical.target_port,
            ),
        ]
        source_box = vertex_visual_box(source)
        target_box = vertex_visual_box(target)
        if len(points) >= 2 and abs(points[1][1] - points[0][1]) > 1e-6:
            failures.add(("source-lead-non-horizontal", edge.cell_id))
        if len(points) >= 2 and abs(points[-1][1] - points[-2][1]) > 1e-6:
            failures.add(("target-lead-non-horizontal", edge.cell_id))
        verticals = [
            (segment_index, a, b)
            for segment_index, (a, b) in enumerate(zip(points, points[1:]))
            if abs(a[0] - b[0]) <= 1e-6 and abs(a[1] - b[1]) > 1e-6
        ]
        if verticals:
            if verticals[0][1][0] < source_box.right + clearance - 1e-6:
                failures.add(("source-lead-clearance", edge.cell_id))
            if verticals[-1][1][0] > target_box.left - clearance + 1e-6:
                failures.add(("target-lead-clearance", edge.cell_id))
        for segment_index, (a, b) in enumerate(zip(points, points[1:])):
            dx = abs(b[0] - a[0])
            dy = abs(b[1] - a[1])
            length = dx + dy
            if dx > 1e-6 and dy > 1e-6:
                failures.add(("non-orthogonal", f"{edge.cell_id}:{segment_index}"))
            if length < 1.0:
                failures.add(("micro-segment", f"{edge.cell_id}:{segment_index}"))
    return frozenset(failures)


def _edges_hitting_focus_vertices(
    document: LayoutDocument,
    logical_edges,
    excluded_edge_indices: set[int],
    focus_vertex_ids: set[str],
) -> frozenset[tuple[str, str]]:
    """Find unchanged edges crossing only the moved/new visible boxes."""
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    edge_by_id = {edge.cell_id: edge for edge in document.edges}
    focus_boxes = {
        cell_id: vertex_visual_box(by_id[cell_id])
        for cell_id in focus_vertex_ids
        if cell_id in by_id
    }
    verticals = []
    horizontals = []
    diagonals = []
    for index, logical in enumerate(logical_edges, 1):
        if index in excluded_edge_indices:
            continue
        edge = edge_by_id[f"e{index}"]
        source = by_id[edge.source_id]
        target = by_id[edge.target_id]
        points = _simplify([
            abs_port_xy(
                source.x, source.y, source.width, source.height,
                source.style, source.drawclock_type, logical.source_port,
            ),
            *edge.waypoints,
            abs_port_xy(
                target.x, target.y, target.width, target.height,
                target.style, target.drawclock_type, logical.target_port,
            ),
        ])
        for a, b in zip(points, points[1:]):
            if abs(a[0] - b[0]) <= 1e-6:
                axis = (a[0] + b[0]) / 2.0
                payload = (
                    (axis, a[1]),
                    (axis, b[1]),
                    edge.cell_id,
                    edge.source_id,
                    edge.target_id,
                )
                verticals.append((a[0], payload))
            elif abs(a[1] - b[1]) <= 1e-6:
                axis = (a[1] + b[1]) / 2.0
                payload = (
                    (a[0], axis),
                    (b[0], axis),
                    edge.cell_id,
                    edge.source_id,
                    edge.target_id,
                )
                horizontals.append((a[1], payload))
            else:
                payload = (a, b, edge.cell_id, edge.source_id, edge.target_id)
                diagonals.append(payload)
    verticals.sort(key=lambda item: item[0])
    horizontals.sort(key=lambda item: item[0])
    vertical_axes = [item[0] for item in verticals]
    horizontal_axes = [item[0] for item in horizontals]
    hits = set()

    def test_payload(cell_id, box, payload):
        a, b, edge_id, source_id, target_id = payload
        if cell_id in (source_id, target_id):
            return
        if _segment_hits_rect(
            a, b, (box.left, box.top, box.right, box.bottom)
        ):
            hits.add((edge_id, cell_id))

    for cell_id, box in focus_boxes.items():
        for _, payload in verticals[
            bisect_left(vertical_axes, box.left):
            bisect_right(vertical_axes, box.right)
        ]:
            test_payload(cell_id, box, payload)
        for _, payload in horizontals[
            bisect_left(horizontal_axes, box.top):
            bisect_right(horizontal_axes, box.bottom)
        ]:
            test_payload(cell_id, box, payload)
        for payload in diagonals:
            test_payload(cell_id, box, payload)
    return frozenset(hits)


def _avoidable_source_facility_pairs(
    document: LayoutDocument,
    logical_edges,
    root: str,
    fixed_cost: float,
) -> frozenset[tuple[str, str]]:
    """Identify adjacent same-column source facilities whose merge is cheaper."""
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    edge_by_id = {edge.cell_id: edge for edge in document.edges}
    anchors = [
        vertex
        for vertex in document.vertices
        if (vertex.logical_name or vertex.name) == root
    ]
    assigned: dict[str, list[float]] = defaultdict(list)
    for index, logical in enumerate(logical_edges, 1):
        if logical.source != root:
            continue
        edge = edge_by_id[f"e{index}"]
        source = by_id[edge.source_id]
        target = by_id[edge.target_id]
        target_y = abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, logical.target_port,
        )[1]
        source_offset = source.height * port_anchors(
            source.style, source.drawclock_type
        )[logical.source_port][1]
        assigned[source.cell_id].append(target_y - source_offset)
    groups = [
        (anchor.cell_id, anchor.x, sorted(assigned[anchor.cell_id]))
        for anchor in anchors
        if assigned[anchor.cell_id]
    ]
    groups.sort(key=lambda item: median(item[2]))

    def l1_cost(values: list[float]) -> float:
        pivot = median(values)
        return sum(abs(value - pivot) for value in values)

    failures = set()
    actual_cost = sum(l1_cost(group) for _, _, group in groups) + fixed_cost * len(groups)
    for left, right in zip(groups, groups[1:]):
        if abs(left[1] - right[1]) > 1e-6:
            continue
        merged_cost = (
            actual_cost
            - l1_cost(left[2])
            - l1_cost(right[2])
            - fixed_cost
            + l1_cost(left[2] + right[2])
        )
        if merged_cost <= actual_cost + 1e-6:
            failures.add(tuple(sorted((left[0], right[0]))))
    return frozenset(failures)


def _source_facility_opening_cost(document: LayoutDocument) -> float:
    """Return three visual rows of geometry-derived facility cost."""
    raw_centers = sorted({
        round(vertex.y + vertex.height / 2.0, 6)
        for vertex in document.vertices
    })
    median_height = median(
        [vertex.height for vertex in document.vertices] or [1.0]
    )
    row_bands: list[list[float]] = []
    for axis in raw_centers:
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
    geometry_pitch = max(1.0, median_height * 2.0)
    row_pitch = (
        max(median_height, min(median(row_deltas), geometry_pitch))
        if row_deltas else geometry_pitch
    )
    return row_pitch * 3.0


def _refine_leaf_continuation_rows(
    document: LayoutDocument,
    logical_edges,
    *,
    route_clearance: float,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Move an exclusive source-to-leaf branch as a unit to remove doglegs.

    A leaf continuation can be straight only when its source port and sink
    port share a free horizontal row.  Moving either endpoint alone is not a
    complete search: the source may belong to an otherwise exclusive upstream
    chain.  This pass derives that movable chain from indegree/outdegree,
    considers obstacle-boundary rows, and accepts only a strict global bend
    improvement with every hard geometry metric non-regressing.
    """
    accepted = document
    indegree: Counter[str] = Counter(edge.target for edge in logical_edges)
    outdegree: Counter[str] = Counter(edge.source for edge in logical_edges)
    incoming: dict[str, list[int]] = defaultdict(list)
    outgoing_indices: dict[str, list[int]] = defaultdict(list)
    incident: dict[str, list[int]] = defaultdict(list)
    for index, logical in enumerate(logical_edges, 1):
        incoming[logical.target].append(index)
        outgoing_indices[logical.source].append(index)
        incident[logical.source].append(index)
        incident[logical.target].append(index)

    accepted_moves = 0
    bends_removed = 0
    blockers: Counter[str] = Counter()

    while True:
        by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
        by_name = {
            vertex.logical_name or vertex.name: vertex
            for vertex in accepted.vertices
        }
        edge_by_id = {edge.cell_id: edge for edge in accepted.edges}

        def edge_points(edge_index: int, doc_by_id=by_id, doc_edges=edge_by_id):
            logical = logical_edges[edge_index - 1]
            edge = doc_edges[f"e{edge_index}"]
            source = doc_by_id[edge.source_id]
            target = doc_by_id[edge.target_id]
            start = abs_port_xy(
                source.x, source.y, source.width, source.height,
                source.style, source.drawclock_type, logical.source_port,
            )
            end = abs_port_xy(
                target.x, target.y, target.width, target.height,
                target.style, target.drawclock_type, logical.target_port,
            )
            return _simplify([start, *edge.waypoints, end])

        column_xs = sorted({vertex.x for vertex in accepted.vertices})
        leaf_candidates = [
            (edge_index, logical)
            for edge_index, logical in enumerate(logical_edges, 1)
            if indegree[logical.target] == 1
            and outdegree[logical.target] == 0
            and outdegree[logical.source] > 1
            and indegree[logical.source] > 0
            and any(
                outdegree[logical_edges[other_index - 1].target] > 0
                for other_index in outgoing_indices[logical.source]
                if other_index != edge_index
            )
            and any(
                by_name[logical.source].x + by_name[logical.source].width + 1e-6
                < column_x
                < by_name[logical.target].x - 1e-6
                for column_x in column_xs
            )
            and max(0, len(edge_points(edge_index)) - 2) >= 2
        ]
        if not leaf_candidates:
            break
        base_report = assess_layout(accepted, logical_edges, 0.0)
        base_visible = _visible_layout_signature(accepted, logical_edges)
        improved = False

        for leaf_edge_index, logical in leaf_candidates:

            chain = {logical.source}
            cursor = logical.source
            while indegree[cursor] == 1:
                parent_edge = logical_edges[incoming[cursor][0] - 1]
                if outdegree[parent_edge.source] != 1:
                    break
                chain.add(parent_edge.source)
                cursor = parent_edge.source
            moved_names = chain | {logical.target}
            moved_ids = {by_name[name].cell_id for name in moved_names}
            source = by_name[logical.source]
            target = by_name[logical.target]
            source_anchor = port_anchors(
                source.style, source.drawclock_type
            )[logical.source_port][1]
            target_anchor = port_anchors(
                target.style, target.drawclock_type
            )[logical.target_port][1]
            source_axis = source.y + source.height * source_anchor

            left = min(source.x + source.width, target.x)
            right = max(source.x + source.width, target.x)
            axes: set[float] = set()
            for vertex in accepted.vertices:
                if vertex.cell_id in moved_ids:
                    continue
                box = vertex_visual_box(vertex)
                if box.right < left or box.left > right:
                    continue
                axes.add(box.top - route_clearance)
                axes.add(box.bottom + route_clearance)
            if not axes:
                continue

            affected_edges = {
                edge_index
                for name in moved_names
                for edge_index in incident[name]
            }
            internal_chain_edges = {
                edge_index
                for edge_index in affected_edges
                if logical_edges[edge_index - 1].source in chain
                and logical_edges[edge_index - 1].target in chain
            }

            for axis in sorted(axes, key=lambda value: (abs(value - source_axis), value)):
                chain_delta = axis - source_axis
                target_delta = (
                    axis - (target.y + target.height * target_anchor)
                )
                if abs(chain_delta) <= 1e-6 and abs(target_delta) <= 1e-6:
                    continue
                candidate = copy.deepcopy(accepted)
                candidate_by_id = {
                    vertex.cell_id: vertex for vertex in candidate.vertices
                }
                candidate_edges = {
                    edge.cell_id: edge for edge in candidate.edges
                }
                for name in chain:
                    candidate_by_id[by_name[name].cell_id].y += chain_delta
                candidate_by_id[target.cell_id].y += target_delta

                for edge_index in affected_edges:
                    edge = candidate_edges[f"e{edge_index}"]
                    if edge_index == leaf_edge_index:
                        edge.waypoints = ()
                        continue
                    if edge_index in internal_chain_edges:
                        edge.waypoints = tuple(
                            (x, y + chain_delta) for x, y in edge.waypoints
                        )
                        continue
                    edge_logical = logical_edges[edge_index - 1]
                    edge_source = candidate_by_id[edge.source_id]
                    edge_target = candidate_by_id[edge.target_id]
                    start = abs_port_xy(
                        edge_source.x, edge_source.y,
                        edge_source.width, edge_source.height,
                        edge_source.style, edge_source.drawclock_type,
                        edge_logical.source_port,
                    )
                    end = abs_port_xy(
                        edge_target.x, edge_target.y,
                        edge_target.width, edge_target.height,
                        edge_target.style, edge_target.drawclock_type,
                        edge_logical.target_port,
                    )
                    if abs(start[1] - end[1]) <= 1e-6:
                        edge.waypoints = ()
                        continue
                    old_points = edge_points(edge_index)
                    old_vertical = [
                        a[0]
                        for a, b in zip(old_points, old_points[1:])
                        if abs(a[0] - b[0]) <= 1e-6
                        and abs(a[1] - b[1]) > 1e-6
                    ]
                    channel_left = (
                        vertex_visual_box(edge_source).right + route_clearance
                    )
                    channel_right = (
                        vertex_visual_box(edge_target).left - route_clearance
                    )
                    if channel_left <= channel_right:
                        preferred = old_vertical[0] if old_vertical else (
                            channel_left + channel_right
                        ) / 2.0
                        route_x = min(channel_right, max(channel_left, preferred))
                    else:
                        route_x = old_vertical[0] if old_vertical else (
                            start[0] + end[0]
                        ) / 2.0
                    edge.waypoints = tuple(_simplify([
                        start,
                        (route_x, start[1]),
                        (route_x, end[1]),
                        end,
                    ])[1:-1])

                candidate_report = assess_layout(candidate, logical_edges, 0.0)
                candidate_visible = _visible_layout_signature(
                    candidate, logical_edges
                )
                dominates = (
                    candidate_report["node_overlaps"] <= base_report["node_overlaps"]
                    and candidate_report["edge_node_intersections"]
                    <= base_report["edge_node_intersections"]
                    and candidate_report["direction_violations"]
                    <= base_report["direction_violations"]
                    and candidate_visible[4].issubset(base_visible[4])
                    and candidate_visible[5].issubset(base_visible[5])
                    and candidate_report["ambiguous_overlaps"]
                    <= base_report["ambiguous_overlaps"]
                    and candidate_report["crossings"] <= base_report["crossings"]
                    and candidate_report["bends_total"] < base_report["bends_total"]
                )
                if not dominates:
                    blockers.update(name for name, passed in {
                        "node-overlap": candidate_report["node_overlaps"] <= base_report["node_overlaps"],
                        "edge-node": candidate_report["edge_node_intersections"] <= base_report["edge_node_intersections"],
                        "direction": candidate_report["direction_violations"] <= base_report["direction_violations"],
                        "visible-overlap": candidate_visible[4].issubset(base_visible[4]),
                        "visible-edge-node": candidate_visible[5].issubset(base_visible[5]),
                        "route-overlap": candidate_report["ambiguous_overlaps"] <= base_report["ambiguous_overlaps"],
                        "crossing": candidate_report["crossings"] <= base_report["crossings"],
                        "bend": candidate_report["bends_total"] < base_report["bends_total"],
                    }.items() if not passed)
                    continue
                bends_removed += (
                    base_report["bends_total"] - candidate_report["bends_total"]
                )
                accepted = candidate
                accepted_moves += 1
                improved = True
                break
            if improved:
                break
        if not improved:
            break

    return accepted, {
        "leaf_continuation_row_moves": accepted_moves,
        "leaf_continuation_bends_removed": bends_removed,
        "leaf_continuation_blockers": dict(sorted(blockers.items())),
    }


def _refine_exclusive_upstream_chain_axes(
    document: LayoutDocument,
    logical_edges,
    *,
    route_clearance: float,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Align a movable exclusive upstream chain with its downstream port."""
    indegree: Counter[str] = Counter(edge.target for edge in logical_edges)
    outdegree: Counter[str] = Counter(edge.source for edge in logical_edges)
    incoming: dict[str, list[int]] = defaultdict(list)
    incident: dict[str, list[int]] = defaultdict(list)
    for edge_index, logical in enumerate(logical_edges, 1):
        incoming[logical.target].append(edge_index)
        incident[logical.source].append(edge_index)
        incident[logical.target].append(edge_index)

    # Avoid copying and fully assessing a graph that has no structurally
    # eligible chain.  This is a necessary-condition preflight only; every
    # admitted candidate still passes the complete quality loop below.
    initial_by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    initial_edges = {edge.cell_id: edge for edge in document.edges}
    has_eligible_chain = False
    for edge_index, logical in enumerate(logical_edges, 1):
        if outdegree[logical.source] != 1:
            continue
        edge = initial_edges[f"e{edge_index}"]
        source = initial_by_id[edge.source_id]
        target = initial_by_id[edge.target_id]
        start = abs_port_xy(
            source.x, source.y, source.width, source.height,
            source.style, source.drawclock_type, logical.source_port,
        )
        end = abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, logical.target_port,
        )
        points = _simplify([start, *edge.waypoints, end])
        if len(points) - 2 != 2 or abs(points[-1][1] - points[0][1]) <= 1e-6:
            continue
        cursor = logical.source
        while indegree[cursor] == 1:
            parent = logical_edges[incoming[cursor][0] - 1].source
            if outdegree[parent] != 1:
                break
            cursor = parent
        if indegree[cursor] == 0:
            has_eligible_chain = True
            break
    if not has_eligible_chain:
        return document, {
            "exclusive_chain_axis_moves": 0,
            "exclusive_chain_bends_removed": 0,
            "exclusive_chain_axis_blockers": {},
        }

    accepted = copy.deepcopy(document)

    accepted_moves = 0
    bends_removed = 0
    blockers: Counter[str] = Counter()

    while True:
        by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
        by_name = {
            vertex.logical_name or vertex.name: vertex
            for vertex in accepted.vertices
        }
        edge_by_id = {edge.cell_id: edge for edge in accepted.edges}

        def points_for(edge_index: int):
            logical = logical_edges[edge_index - 1]
            edge = edge_by_id[f"e{edge_index}"]
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

        base_report = assess_layout(accepted, logical_edges, 0.0)
        base_visible = _visible_layout_signature(accepted, logical_edges)
        best_candidate = None
        best_signature = None
        best_removed = 0

        for main_edge_index, logical in enumerate(logical_edges, 1):
            main_points = points_for(main_edge_index)
            if len(main_points) - 2 != 2 or outdegree[logical.source] != 1:
                continue

            chain = {logical.source}
            cursor = logical.source
            while indegree[cursor] == 1:
                parent_edge_index = incoming[cursor][0]
                parent = logical_edges[parent_edge_index - 1].source
                if outdegree[parent] != 1:
                    break
                chain.add(parent)
                cursor = parent
            if indegree[cursor] != 0:
                continue

            delta = main_points[-1][1] - main_points[0][1]
            if abs(delta) <= 1e-6:
                continue
            affected_edges = {
                edge_index
                for name in chain
                for edge_index in incident[name]
            }
            internal_edges = {
                edge_index
                for edge_index in affected_edges
                if logical_edges[edge_index - 1].source in chain
                and logical_edges[edge_index - 1].target in chain
            }
            boundary_edges = sorted(
                affected_edges - internal_edges - {main_edge_index}
            )
            if len(boundary_edges) > 1:
                continue

            boundary_channels: list[float | None] = [None]
            if boundary_edges:
                boundary_index = boundary_edges[0]
                old_points = points_for(boundary_index)
                old_verticals = [
                    a[0]
                    for a, b in zip(old_points, old_points[1:])
                    if abs(a[0] - b[0]) <= 1e-6
                    and abs(a[1] - b[1]) > 1e-6
                ]
                boundary_edge = edge_by_id[f"e{boundary_index}"]
                boundary_source = by_id[boundary_edge.source_id]
                boundary_target = by_id[boundary_edge.target_id]
                channel_left = (
                    vertex_visual_box(boundary_source).right + route_clearance
                )
                channel_right = (
                    vertex_visual_box(boundary_target).left - route_clearance
                )
                channels = list(old_verticals)
                if channel_left <= channel_right + 1e-6:
                    channels.extend((
                        channel_left,
                        (channel_left + channel_right) / 2.0,
                        channel_right,
                    ))
                boundary_channels = list(dict.fromkeys(channels))
                if not boundary_channels:
                    boundary_channels = [
                        (old_points[0][0] + old_points[-1][0]) / 2.0
                    ]

            old_affected_bends = sum(
                max(0, len(points_for(edge_index)) - 2)
                for edge_index in affected_edges
            )
            moved_ids = {by_name[name].cell_id for name in chain}
            for boundary_channel in boundary_channels:
                candidate = copy.deepcopy(accepted)
                candidate_by_id = {
                    vertex.cell_id: vertex for vertex in candidate.vertices
                }
                candidate_edges = {
                    edge.cell_id: edge for edge in candidate.edges
                }
                for cell_id in moved_ids:
                    candidate_by_id[cell_id].y += delta
                for edge_index in affected_edges:
                    edge = candidate_edges[f"e{edge_index}"]
                    if edge_index == main_edge_index:
                        edge.waypoints = ()
                    elif edge_index in internal_edges:
                        edge.waypoints = tuple(
                            (x, y + delta) for x, y in edge.waypoints
                        )
                    else:
                        edge_logical = logical_edges[edge_index - 1]
                        source = candidate_by_id[edge.source_id]
                        target = candidate_by_id[edge.target_id]
                        start = abs_port_xy(
                            source.x, source.y, source.width, source.height,
                            source.style, source.drawclock_type,
                            edge_logical.source_port,
                        )
                        end = abs_port_xy(
                            target.x, target.y, target.width, target.height,
                            target.style, target.drawclock_type,
                            edge_logical.target_port,
                        )
                        if abs(start[1] - end[1]) <= 1e-6:
                            edge.waypoints = ()
                        else:
                            route_x = boundary_channel
                            if route_x is None:
                                route_x = (start[0] + end[0]) / 2.0
                            edge.waypoints = tuple(_simplify([
                                start,
                                (route_x, start[1]),
                                (route_x, end[1]),
                                end,
                            ])[1:-1])

                candidate_by_edge = {
                    edge.cell_id: edge for edge in candidate.edges
                }
                candidate_affected_bends = 0
                for edge_index in affected_edges:
                    edge = candidate_by_edge[f"e{edge_index}"]
                    edge_logical = logical_edges[edge_index - 1]
                    source = candidate_by_id[edge.source_id]
                    target = candidate_by_id[edge.target_id]
                    start = abs_port_xy(
                        source.x, source.y, source.width, source.height,
                        source.style, source.drawclock_type,
                        edge_logical.source_port,
                    )
                    end = abs_port_xy(
                        target.x, target.y, target.width, target.height,
                        target.style, target.drawclock_type,
                        edge_logical.target_port,
                    )
                    candidate_affected_bends += max(
                        0,
                        len(_simplify([start, *edge.waypoints, end])) - 2,
                    )
                if candidate_affected_bends >= old_affected_bends:
                    blockers["no-local-bend-dominance"] += 1
                    continue

                candidate_report = assess_layout(
                    candidate, logical_edges, 0.0
                )
                candidate_visible = _visible_layout_signature(
                    candidate, logical_edges
                )
                checks = {
                    "node-overlap": candidate_report["node_overlaps"] <= base_report["node_overlaps"],
                    "edge-node": candidate_report["edge_node_intersections"] <= base_report["edge_node_intersections"],
                    "direction": candidate_report["direction_violations"] <= base_report["direction_violations"],
                    "visible-overlap": candidate_visible[4].issubset(base_visible[4]),
                    "visible-edge-node": candidate_visible[5].issubset(base_visible[5]),
                    "route-overlap": candidate_report["ambiguous_overlaps"] <= base_report["ambiguous_overlaps"],
                    "crossing": candidate_report["crossings"] <= base_report["crossings"],
                    "bend": candidate_report["bends_total"] < base_report["bends_total"],
                }
                if not all(checks.values()):
                    blockers.update(
                        name for name, passed in checks.items() if not passed
                    )
                    continue
                signature = (
                    candidate_report["crossings"],
                    candidate_report["ambiguous_overlaps"],
                    candidate_report["bends_total"],
                    candidate_report["manhattan_length"],
                    tuple(sorted(chain)),
                    main_edge_index,
                    boundary_channel if boundary_channel is not None else 0.0,
                )
                if best_signature is None or signature < best_signature:
                    best_candidate = candidate
                    best_signature = signature
                    best_removed = (
                        base_report["bends_total"]
                        - candidate_report["bends_total"]
                    )

        if best_candidate is None:
            break
        accepted = best_candidate
        accepted_moves += 1
        bends_removed += best_removed

    return accepted, {
        "exclusive_chain_axis_moves": accepted_moves,
        "exclusive_chain_bends_removed": bends_removed,
        "exclusive_chain_axis_blockers": dict(sorted(blockers.items())),
    }


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
            for edge_index in incident[vertex_id]:
                edge = edge_by_id[f"e{edge_index}"]
                points = points_for(edge_index)
                old_bends += max(0, len(points) - 2)
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
            if best_bends < old_bends:
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
            if candidate_incident_bends >= old_incident_bends:
                blockers["no-local-bend-dominance"] += 1
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
                and candidate_visible[4].issubset(accepted_visible[4])
                and candidate_visible[5].issubset(accepted_visible[5])
                and candidate_report["ambiguous_overlaps"]
                <= accepted_report["ambiguous_overlaps"]
                and candidate_report["crossings"] <= accepted_report["crossings"]
                and candidate_report["bends_total"] < accepted_report["bends_total"]
            )
            if not dominates:
                checks = {
                    "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
                    "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
                    "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
                    "visible-overlap": candidate_visible[4].issubset(accepted_visible[4]),
                    "visible-edge-node": candidate_visible[5].issubset(accepted_visible[5]),
                    "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
                    "crossing": candidate_report["crossings"] <= accepted_report["crossings"],
                    "bend": candidate_report["bends_total"] < accepted_report["bends_total"],
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
    samples: list[tuple[float, int]],
    fixed_cost: float,
    *,
    row_axes: tuple[float, ...] = (),
    max_intervening_rows: int = 3,
) -> list[list[int]]:
    """Partition one shared trunk using an exact linear-time gap criterion.

    For a consecutive band, service cost is its vertical span plus one fixed
    anchor-opening charge.  Splitting at a gap changes the objective by
    ``fixed_cost - gap`` independently of every other gap, so every gap larger
    than the charge must be cut and no smaller/equal gap should be cut.
    """
    ordered = sorted(samples)
    if len(ordered) <= 1:
        return [[item[1] for item in ordered]] if ordered else []
    # Kept in the signature because callers and QA express the human-readable
    # row budget explicitly; the exact objective is fully determined by the
    # geometry-normalized fixed charge derived from those values.
    del row_axes, max_intervening_rows
    partitions: list[list[int]] = [[ordered[0][1]]]
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] - previous[0] > fixed_cost + 1e-9:
            partitions.append([])
        partitions[-1].append(current[1])
    return partitions


def _replicate_dispersed_roots(
    document: LayoutDocument,
    nodes,
    logical_edges,
    profile,
    *,
    include_assessment: bool = False,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Add rendering anchors only when a zero-indegree source wins globally."""
    indegree = Counter(edge.target for edge in logical_edges)
    outdegree = Counter(edge.source for edge in logical_edges)
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
    row_centers = tuple(median(band) for band in row_bands)
    row_deltas = [
        right - left
        for left, right in zip(row_centers, row_centers[1:])
        if right - left > 1e-6
    ]
    geometry_pitch = max(
        1.0,
        median_height + profile.node_spacing,
    )
    row_pitch = (
        max(median_height, min(median(row_deltas), geometry_pitch))
        if row_deltas else geometry_pitch
    )
    max_intervening_rows = 3
    partition_fixed_cost = row_pitch * max_intervening_rows

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
        partitions = _optimal_source_anchor_partitions(
            desired,
            partition_fixed_cost,
            row_axes=row_centers,
            max_intervening_rows=max_intervening_rows,
        )
        if len(partitions) <= 1:
            continue
        candidate_roots += 1
        outgoing_edge_ids = {f"e{edge_index}" for edge_index in outgoing[root]}
        candidate = LayoutDocument(
            version=accepted.version,
            vertices=list(accepted.vertices),
            edges=[
                copy.copy(edge) if edge.cell_id in outgoing_edge_ids else edge
                for edge in accepted.edges
            ],
        )
        candidate_by_id = {vertex.cell_id: vertex for vertex in candidate.vertices}
        candidate_original = copy.copy(candidate_by_id[original.cell_id])
        candidate.vertices[candidate.vertices.index(candidate_by_id[original.cell_id])] = (
            candidate_original
        )
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
        original_box = vertex_visual_box(candidate_original)
        for vertex in candidate.vertices:
            if vertex.cell_id in anchor_ids:
                continue
            box = vertex_visual_box(vertex)
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
                occupied.append((top - profile.grid, bottom + profile.grid))
        placed: list[tuple[float, float]] = []
        for anchor, partition in zip(anchors, partitions):
            tops = [value for value, edge_index in desired if edge_index in partition]
            ordered_tops = sorted(tops)
            # Any point in the even-sample median interval is L1-optimal.
            # Selecting an actual consumer axis, rather than the arithmetic
            # midpoint, preserves that optimum and maximizes straight leads.
            wanted = ordered_tops[(len(ordered_tops) - 1) // 2]
            top = wanted
            for low, high in sorted(occupied + placed):
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
                channel_left = (
                    vertex_visual_box(anchor).right
                    + profile.route_clearance
                )
                channel_right = (
                    vertex_visual_box(target).left
                    - profile.route_clearance
                )
                if old_edge.waypoints:
                    first_x = old_points[1][0]
                    if channel_left <= channel_right + 1e-6:
                        first_x = min(
                            max(first_x, channel_left),
                            channel_right,
                        )
                    interior = [
                        point for point in old_points[2:-1]
                        if start[0] - 1e-6 <= point[0] <= end[0] + 1e-6
                    ]
                    points = _simplify([
                        start,
                        (first_x, start[1]),
                        *interior,
                        end,
                    ])
                elif abs(start[1] - end[1]) <= 1e-6:
                    points = [start, end]
                else:
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
        candidate_report = assess_layout(
            candidate,
            logical_edges,
            0.0,
            reject_geometry_worse_than=(
                accepted_report["node_overlaps"],
                accepted_report["edge_node_intersections"],
            ),
        )
        if candidate_report.get("geometry_short_circuit"):
            if candidate_report["node_overlaps"] > accepted_report["node_overlaps"]:
                replica_blockers["node-overlap"] += 1
            if (
                candidate_report["edge_node_intersections"]
                > accepted_report["edge_node_intersections"]
            ):
                replica_blockers["edge-node"] += 1
            continue
        replica_cost = partition_fixed_cost * (len(partitions) - 1)
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
    report = {
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
        "source_replica_area_delta_px2": round(
            accepted_report["area"] - initial_report["area"], 3
        ),
        "source_replica_blockers": dict(sorted(replica_blockers.items())),
        "source_replica_row_budget": max_intervening_rows,
        "source_replica_row_pitch_px": round(row_pitch, 3),
    }
    if include_assessment:
        report["_accepted_assessment"] = accepted_report
    return accepted, report


def _clone_layout_geometry(document: LayoutDocument) -> LayoutDocument:
    """Copy mutable coordinates/routes without recursively copying payloads."""
    return LayoutDocument(
        version=document.version,
        vertices=[copy.copy(vertex) for vertex in document.vertices],
        edges=[copy.copy(edge) for edge in document.edges],
    )


def _normalize_fanout_routes_as_trees(
    document: LayoutDocument,
    nodes,
    logical_edges,
    *,
    route_clearance: float = 0.0,
    accepted_assessment: dict[str, Any] | None = None,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Remove split-rejoin cycles from each physical source-port network."""
    accepted = _clone_layout_geometry(document)
    accepted_report = (
        accepted_assessment
        if accepted_assessment is not None
        else assess_layout(accepted, logical_edges, 0.0)
    )
    by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
    edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
    def canonical(point: tuple[float, float]) -> tuple[float, float]:
        return round(point[0], 6), round(point[1], 6)

    def route_endpoints(
        index: int, local_by_id=None, local_edge_by_id=None,
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        vertices = local_by_id if local_by_id is not None else by_id
        edges = local_edge_by_id if local_edge_by_id is not None else edge_by_id
        edge = edges[f"e{index}"]
        logical = logical_edges[index - 1]
        source = vertices[edge.source_id]
        target = vertices[edge.target_id]
        start = abs_port_xy(
            source.x, source.y, source.width, source.height,
            source.style, source.drawclock_type, logical.source_port,
        )
        end = abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, logical.target_port,
        )
        return start, end

    def route_points(
        index: int, local_by_id=None, local_edge_by_id=None,
    ) -> list[tuple[float, float]]:
        edges = local_edge_by_id if local_edge_by_id is not None else edge_by_id
        edge = edges[f"e{index}"]
        start, end = route_endpoints(index, local_by_id, local_edge_by_id)
        return [canonical(point) for point in _simplify([start, *edge.waypoints, end])]

    def union_graph(
        indices: list[int],
        provided_paths: dict[int, list[tuple[float, float]]] | None = None,
        local_by_id=None,
        local_edge_by_id=None,
    ):
        raw = []
        for index in indices:
            points = (
                provided_paths[index]
                if provided_paths is not None
                else route_points(index, local_by_id, local_edge_by_id)
            )
            raw.extend(
                (a, b) for a, b in zip(points, points[1:]) if a != b
            )
        vertical: dict[float, list[tuple[float, float]]] = defaultdict(list)
        horizontal: dict[float, list[tuple[float, float]]] = defaultdict(list)
        vertical_breaks: dict[float, set[float]] = defaultdict(set)
        horizontal_breaks: dict[float, set[float]] = defaultdict(set)
        for a, b in raw:
            if abs(a[0] - b[0]) <= 1e-6:
                low, high = sorted((a[1], b[1]))
                vertical[a[0]].append((low, high))
                vertical_breaks[a[0]].update((low, high))
            else:
                low, high = sorted((a[0], b[0]))
                horizontal[a[1]].append((low, high))
                horizontal_breaks[a[1]].update((low, high))

        # Report every horizontal/vertical intersection in O((S + K) log S)
        # with a coordinate-compressed sweep.  This replaces the former
        # all-segment-pairs scan that made large fanout groups quadratic.
        y_values = sorted(horizontal)
        y_index = {value: index + 1 for index, value in enumerate(y_values)}
        bit = [0] * (len(y_values) + 1)
        active_counts: Counter[float] = Counter()

        def bit_add(index: int, value: int) -> None:
            while index < len(bit):
                bit[index] += value
                index += index & -index

        def bit_sum(index: int) -> int:
            result = 0
            while index:
                result += bit[index]
                index -= index & -index
            return result

        def bit_select(order: int) -> int:
            index = 0
            step = 1 << (len(bit).bit_length() - 1)
            while step:
                probe = index + step
                if probe < len(bit) and bit[probe] < order:
                    index = probe
                    order -= bit[probe]
                step >>= 1
            return index + 1

        starts: dict[float, list[float]] = defaultdict(list)
        ends: dict[float, list[float]] = defaultdict(list)
        for y, intervals in horizontal.items():
            for low, high in intervals:
                starts[low].append(y)
                ends[high].append(y)
        for x in sorted(set(starts) | set(ends) | set(vertical)):
            for y in starts.get(x, ()):
                active_counts[y] += 1
                if active_counts[y] == 1:
                    bit_add(y_index[y], 1)
            for low, high in vertical.get(x, ()):
                lower_index = bisect_left(y_values, low)
                upper_index = bisect_right(y_values, high)
                before = bit_sum(lower_index)
                through = bit_sum(upper_index)
                for order in range(before + 1, through + 1):
                    y = y_values[bit_select(order) - 1]
                    vertical_breaks[x].add(y)
                    horizontal_breaks[y].add(x)
            for y in ends.get(x, ()):
                active_counts[y] -= 1
                if active_counts[y] == 0:
                    bit_add(y_index[y], -1)

        def merged(intervals):
            result = []
            for low, high in sorted(intervals):
                if result and low <= result[-1][1] + 1e-6:
                    result[-1] = (result[-1][0], max(result[-1][1], high))
                else:
                    result.append((low, high))
            return result

        graph: dict[tuple[float, float], dict[tuple[float, float], float]] = defaultdict(dict)
        for x, intervals in vertical.items():
            breaks = sorted(vertical_breaks[x])
            for low, high in merged(intervals):
                points = breaks[bisect_left(breaks, low):bisect_right(breaks, high)]
                for first_y, second_y in zip(points, points[1:]):
                    first, second = (x, first_y), (x, second_y)
                    graph[first][second] = second_y - first_y
                    graph[second][first] = second_y - first_y
        for y, intervals in horizontal.items():
            breaks = sorted(horizontal_breaks[y])
            for low, high in merged(intervals):
                points = breaks[bisect_left(breaks, low):bisect_right(breaks, high)]
                for first_x, second_x in zip(points, points[1:]):
                    first, second = (first_x, y), (second_x, y)
                    graph[first][second] = second_x - first_x
                    graph[second][first] = second_x - first_x
        return graph

    def cycle_rank(graph) -> int:
        parent: dict[tuple[float, float], tuple[float, float]] = {}

        def find(point):
            parent.setdefault(point, point)
            while parent[point] != point:
                parent[point] = parent[parent[point]]
                point = parent[point]
            return point

        edge_count = 0
        for left in sorted(graph):
            for right in sorted(graph[left]):
                if left >= right:
                    continue
                edge_count += 1
                root_left, root_right = find(left), find(right)
                if root_left != root_right:
                    parent[root_left] = root_right
        vertices = set(graph)
        component_count = len({find(point) for point in vertices})
        return max(0, edge_count - len(vertices) + component_count)

    def has_cycle(graph) -> bool:
        return cycle_rank(graph) > 0

    def target_leaf_graph(graph, indices):
        """Keep every destination contact as a leaf of the shared tree."""
        result = {
            point: dict(neighbours) for point, neighbours in graph.items()
        }
        for index in indices:
            points = route_points(index)
            if len(points) < 2:
                continue
            previous_point, end = points[-2], points[-1]
            candidates = []
            for neighbour, length in result.get(end, {}).items():
                if abs(previous_point[0] - end[0]) <= 1e-6:
                    on_approach = (
                        abs(neighbour[0] - end[0]) <= 1e-6
                        and min(previous_point[1], end[1]) - 1e-6
                        <= neighbour[1]
                        <= max(previous_point[1], end[1]) + 1e-6
                    )
                else:
                    on_approach = (
                        abs(neighbour[1] - end[1]) <= 1e-6
                        and min(previous_point[0], end[0]) - 1e-6
                        <= neighbour[0]
                        <= max(previous_point[0], end[0]) + 1e-6
                    )
                if on_approach:
                    candidates.append((length, neighbour))
            if not candidates:
                continue
            allowed = min(candidates)[1]
            for neighbour in tuple(result.get(end, {})):
                if neighbour == allowed:
                    continue
                result[end].pop(neighbour, None)
                result[neighbour].pop(end, None)
        return result

    def routes_share_segment(left_index: int, right_index: int) -> bool:
        left = route_points(left_index)
        right = route_points(right_index)
        for a, b in zip(left, left[1:]):
            for c, d in zip(right, right[1:]):
                if abs(a[0] - b[0]) <= 1e-6 and abs(c[0] - d[0]) <= 1e-6:
                    if abs(a[0] - c[0]) <= 1e-6:
                        low = max(min(a[1], b[1]), min(c[1], d[1]))
                        high = min(max(a[1], b[1]), max(c[1], d[1]))
                        if high - low > 1e-6:
                            return True
                elif abs(a[1] - b[1]) <= 1e-6 and abs(c[1] - d[1]) <= 1e-6:
                    if abs(a[1] - c[1]) <= 1e-6:
                        low = max(min(a[0], b[0]), min(c[0], d[0]))
                        high = min(max(a[0], b[0]), max(c[0], d[0]))
                        if high - low > 1e-6:
                            return True
        return False

    alias_consolidations = 0
    alias_blockers: Counter[str] = Counter()
    logical_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, logical in enumerate(logical_edges, 1):
        logical_groups[(logical.source, logical.source_port)].append(index)
    for (logical_source, _), logical_indices in sorted(logical_groups.items()):
        baseline_rank = cycle_rank(union_graph(logical_indices))
        if len(logical_indices) < 2 or baseline_rank == 0:
            continue
        parent = {index: index for index in logical_indices}

        def find(index):
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        for offset, left in enumerate(logical_indices):
            for right in logical_indices[offset + 1:]:
                if (
                    edge_by_id[f"e{left}"].source_id != edge_by_id[f"e{right}"].source_id
                    and routes_share_segment(left, right)
                ):
                    root_left, root_right = find(left), find(right)
                    if root_left != root_right:
                        parent[root_right] = root_left
        components: dict[int, list[int]] = defaultdict(list)
        for index in logical_indices:
            components[find(index)].append(index)
        for component in sorted(components.values(), key=lambda value: tuple(value)):
            source_ids = sorted({edge_by_id[f"e{index}"].source_id for index in component})
            if len(source_ids) < 2:
                continue
            candidates = []
            for keep_source_id in source_ids:
                candidate = _clone_layout_geometry(accepted)
                candidate_by_id = {vertex.cell_id: vertex for vertex in candidate.vertices}
                candidate_edges = {edge.cell_id: edge for edge in candidate.edges}
                keep_source = candidate_by_id[keep_source_id]
                valid = True
                for index in component:
                    edge = candidate_edges[f"e{index}"]
                    logical = logical_edges[index - 1]
                    old_points = route_points(index)
                    target = candidate_by_id[edge.target_id]
                    start = abs_port_xy(
                        keep_source.x, keep_source.y, keep_source.width, keep_source.height,
                        keep_source.style, keep_source.drawclock_type, logical.source_port,
                    )
                    end = abs_port_xy(
                        target.x, target.y, target.width, target.height,
                        target.style, target.drawclock_type, logical.target_port,
                    )
                    edge.source_id = keep_source_id
                    if len(old_points) > 2:
                        points = _simplify([
                            start, (old_points[1][0], start[1]), *old_points[2:-1], end,
                        ])
                    elif abs(start[1] - end[1]) <= 1e-6:
                        points = [start, end]
                    else:
                        channel = (start[0] + end[0]) / 2.0
                        points = [start, (channel, start[1]), (channel, end[1]), end]
                    if any(
                        abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6
                        for a, b in zip(points, points[1:])
                    ):
                        valid = False
                        break
                    edge.waypoints = tuple(points[1:-1])
                if not valid:
                    alias_blockers["non-orthogonal"] += 1
                    continue
                used_source_ids = {edge.source_id for edge in candidate.edges}
                candidate.vertices = [
                    vertex for vertex in candidate.vertices
                    if (vertex.logical_name or vertex.name) != logical_source
                    or vertex.cell_id in used_source_ids
                ]
                candidate_by_id = {vertex.cell_id: vertex for vertex in candidate.vertices}
                candidate_edges = {edge.cell_id: edge for edge in candidate.edges}
                candidate_rank = cycle_rank(union_graph(
                    logical_indices,
                    local_by_id=candidate_by_id,
                    local_edge_by_id=candidate_edges,
                ))
                if candidate_rank > baseline_rank:
                    alias_blockers["logical-cycle"] += 1
                    continue
                candidate_report = assess_layout(candidate, logical_edges, 0.0)
                accepted_visible = _visible_layout_signature(accepted, logical_edges)
                candidate_visible = _visible_layout_signature(candidate, logical_edges)
                changed = set(component)
                accepted_endpoint = _route_endpoint_signature(
                    accepted, logical_edges, changed, route_clearance
                )
                candidate_endpoint = _route_endpoint_signature(
                    candidate, logical_edges, changed, route_clearance
                )
                checks = {
                    "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
                    "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
                    "visible-overlap": candidate_visible[4].issubset(accepted_visible[4]),
                    "visible-edge-node": candidate_visible[5].issubset(accepted_visible[5]),
                    "endpoint-route": candidate_endpoint.issubset(accepted_endpoint),
                    "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
                    "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
                    "crossing": candidate_report["crossings"] <= accepted_report["crossings"],
                    "bend": candidate_report["bends_total"] <= accepted_report["bends_total"],
                    "length": candidate_report["manhattan_length"] <= accepted_report["manhattan_length"] + 1e-6,
                }
                if all(checks.values()):
                    score = (
                        candidate_rank, candidate_report["crossings"], candidate_report["bends_total"],
                        candidate_report["manhattan_length"], keep_source_id,
                    )
                    candidates.append((score, candidate, candidate_report))
                else:
                    alias_blockers.update(name for name, passed in checks.items() if not passed)
            if candidates:
                _, accepted, accepted_report = min(candidates, key=lambda item: item[0])
                by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
                edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
                alias_consolidations += len(source_ids) - 1
                baseline_rank = cycle_rank(union_graph(logical_indices))

    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, logical in enumerate(logical_edges, 1):
        groups[(edge_by_id[f"e{index}"].source_id, logical.source_port)].append(index)

    normalized = 0
    cycles_before = 0
    blockers: Counter[str] = Counter()
    for indices in groups.values():
        if len(indices) < 2:
            continue
        graph = union_graph(indices)
        if not has_cycle(graph):
            continue
        cycles_before += 1
        routing_graph = target_leaf_graph(graph, indices)
        start = route_points(indices[0])[0]
        start_state = (start, "")
        distances = {start_state: (0.0, 0, 0)}
        previous: dict[
            tuple[tuple[float, float], str],
            tuple[tuple[float, float], str],
        ] = {}
        queue = [(0.0, 0, 0, start, "")]
        while queue:
            distance, bends, hops, point, incoming_axis = heapq.heappop(queue)
            state = (point, incoming_axis)
            if (distance, bends, hops) != distances.get(state):
                continue
            for neighbour, length in sorted(routing_graph.get(point, {}).items()):
                axis = "v" if abs(point[0] - neighbour[0]) <= 1e-6 else "h"
                turn = int(bool(incoming_axis) and incoming_axis != axis)
                candidate = (distance + length, bends + turn, hops + 1)
                neighbour_state = (neighbour, axis)
                if candidate < distances.get(
                    neighbour_state, (math.inf, sys.maxsize, sys.maxsize)
                ):
                    distances[neighbour_state] = candidate
                    previous[neighbour_state] = state
                    heapq.heappush(queue, (*candidate, neighbour, axis))
        candidate = _clone_layout_geometry(accepted)
        candidate_edges = {edge.cell_id: edge for edge in candidate.edges}
        chosen_paths: dict[int, list[tuple[float, float]]] = {}
        complete = True
        for index in indices:
            end = route_points(index)[-1]
            end_states = [
                state for state in ((end, "h"), (end, "v"), (end, ""))
                if state in distances
            ]
            if not end_states:
                complete = False
                break
            state = min(end_states, key=lambda item: (distances[item], item[1]))
            states = [state]
            while states[-1] != start_state:
                states.append(previous[states[-1]])
            states.reverse()
            path = [item[0] for item in states]
            chosen_paths[index] = path
            canonical_start, canonical_end = path[0], path[-1]
            actual_start, actual_end = route_endpoints(index)
            path[0], path[-1] = actual_start, actual_end
            if len(path) > 2:
                first = list(path[1])
                if abs(first[0] - canonical_start[0]) <= 1e-6:
                    first[0] = actual_start[0]
                if abs(first[1] - canonical_start[1]) <= 1e-6:
                    first[1] = actual_start[1]
                path[1] = tuple(first)
                last = list(path[-2])
                if abs(last[0] - canonical_end[0]) <= 1e-6:
                    last[0] = actual_end[0]
                if abs(last[1] - canonical_end[1]) <= 1e-6:
                    last[1] = actual_end[1]
                path[-2] = tuple(last)
            simplified = _simplify(path)
            if len(simplified) > 2:
                first = list(simplified[1])
                if abs(first[0] - actual_start[0]) <= 1e-6:
                    first[0] = actual_start[0]
                if abs(first[1] - actual_start[1]) <= 1e-6:
                    first[1] = actual_start[1]
                simplified[1] = tuple(first)
                last = list(simplified[-2])
                if abs(last[0] - actual_end[0]) <= 1e-6:
                    last[0] = actual_end[0]
                if abs(last[1] - actual_end[1]) <= 1e-6:
                    last[1] = actual_end[1]
                simplified[-2] = tuple(last)
            candidate_edges[f"e{index}"].waypoints = tuple(simplified[1:-1])
        if not complete:
            blockers["disconnected-union"] += 1
            continue
        if has_cycle(union_graph(indices, chosen_paths)):
            blockers["candidate-cycle"] += 1
            continue
        candidate_report = assess_layout(candidate, logical_edges, 0.0)
        checks = {
            "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
            "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
            "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
            "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
            "crossing": candidate_report["crossings"] <= accepted_report["crossings"],
            "bend": candidate_report["bends_total"] <= accepted_report["bends_total"],
            "length": candidate_report["manhattan_length"] <= accepted_report["manhattan_length"] + 1e-6,
        }
        # Every route now follows one predecessor map rooted at the physical
        # output port.  The union is therefore a subtree of that predecessor
        # tree; an additional cycle check against the still-accepted document
        # would inspect stale routes rather than this candidate.
        if all(checks.values()):
            accepted = candidate
            accepted_report = candidate_report
            by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
            edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
            normalized += 1
        else:
            blockers.update(name for name, passed in checks.items() if not passed)
    residual_logical_cycle_rank = sum(
        cycle_rank(union_graph(indices))
        for indices in logical_groups.values()
        if len(indices) > 1
    )
    return accepted, {
        "fanout_alias_consolidations": alias_consolidations,
        "fanout_alias_consolidation_blockers": dict(sorted(alias_blockers.items())),
        "fanout_cycle_candidates": cycles_before,
        "fanout_cycles_normalized": normalized,
        "fanout_residual_logical_cycle_rank": residual_logical_cycle_rank,
        "fanout_tree_normalization_blockers": dict(sorted(blockers.items())),
        "_accepted_assessment": accepted_report,
    }


def _nearest_clear_anchor_top(
    anchor,
    wanted: float,
    placed_boxes,
    clearance: float,
) -> float:
    """Return the closest non-negative y whose visible box clears obstacles."""
    zero_anchor = copy.copy(anchor)
    zero_anchor.y = 0.0
    zero_box = vertex_visual_box(zero_anchor)
    probe = vertex_visual_box(anchor)
    relevant = [
        box
        for box in placed_boxes
        if not (
            box.right + clearance <= probe.left
            or box.left >= probe.right + clearance
        )
    ]
    forbidden = [
        (
            box.top - clearance - zero_box.bottom,
            box.bottom + clearance - zero_box.top,
        )
        for box in relevant
    ]
    merged: list[list[float]] = []
    for low, high in sorted(forbidden):
        if not merged or low > merged[-1][1] + 1e-9:
            merged.append([low, high])
        else:
            merged[-1][1] = max(merged[-1][1], high)
    target = max(0.0, wanted)
    for low, high in merged:
        if target <= low + 1e-9:
            return target
        if target < high - 1e-9:
            candidates = [high]
            if low >= 0.0:
                candidates.append(low)
            return min(
                candidates,
                key=lambda top: (abs(top - wanted), top),
            )
    return target


def _relocate_root_rendering_anchors(
    document: LayoutDocument,
    nodes,
    logical_edges,
    profile,
    *,
    accepted_assessment: dict[str, Any] | None = None,
    include_assessment: bool = False,
    continuous_physical_search: bool = True,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Move each already justified root anchor to a non-dominated later column."""
    indegree = Counter(edge.target for edge in logical_edges)
    outdegree = Counter(edge.source for edge in logical_edges)
    accepted = _clone_layout_geometry(document)
    accepted_report = (
        accepted_assessment
        if accepted_assessment is not None
        else assess_layout(accepted, logical_edges, 0.0)
    )
    initial_report = dict(accepted_report)
    attempted_moves = 0
    accepted_moves = 0
    blockers: Counter[str] = Counter()

    def metric(report: dict[str, Any]) -> tuple[float, ...]:
        return (
            report["source_crossing_points"],
            report["distinct_crossing_points"],
            report["crossings"],
            report["bends_total"],
            report["manhattan_length"],
            report["area"],
        )

    for root in sorted(nodes):
        if indegree[root] or "layout_column" in nodes[root].item:
            continue
        logical_anchors = [
            vertex
            for vertex in accepted.vertices
            if (vertex.logical_name or vertex.name) == root
        ]
        if not logical_anchors:
            continue
        # A lone high-fanout root is owned by the preceding facility
        # partitioner.  Reassessing its complete edge set here duplicates
        # global work.  This stage adds the formerly missing one-use-root case
        # and still relocates every independently created physical facility.
        if len(logical_anchors) == 1 and outdegree[root] > 1:
            continue
        anchor_ids = {anchor.cell_id for anchor in logical_anchors}
        edge_indices_by_anchor: dict[str, list[int]] = defaultdict(list)
        for edge in accepted.edges:
            if edge.source_id in anchor_ids:
                edge_indices_by_anchor[edge.source_id].append(int(edge.cell_id[1:]))
        canonical_columns = sorted({vertex.x for vertex in accepted.vertices})

        scopes = list(dict.fromkeys(
            [tuple(sorted(anchor_ids))]
            + [(anchor_id,) for anchor_id in sorted(anchor_ids)]
        ))
        current_by_id = {
            vertex.cell_id: vertex for vertex in accepted.vertices
        }
        current_edge_by_id = {
            edge.cell_id: edge for edge in accepted.edges
        }
        for scope in scopes:
            # The all-anchor scope often reaches every facility's latest
            # feasible column at once.  Do not clone the complete document for
            # the following single-anchor scopes unless at least one member
            # still has a strictly later feasible column.
            scope_can_move = False
            for anchor_id in scope:
                anchor = current_by_id[anchor_id]
                indices = edge_indices_by_anchor.get(anchor_id, [])
                if not indices:
                    continue
                if continuous_physical_search and any(
                    current_edge_by_id[f"e{index}"].waypoints
                    for index in indices
                ):
                    scope_can_move = True
                    break
                targets = [
                    current_by_id[current_edge_by_id[f"e{index}"].target_id]
                    for index in indices
                ]
                target_left = min(
                    vertex_visual_box(target).left for target in targets
                )
                right_overhang = vertex_visual_box(anchor).right - anchor.x
                continuous_latest = (
                    target_left - profile.route_clearance - right_overhang
                )
                anchor_columns = (
                    [*canonical_columns, continuous_latest]
                    if (
                        len(indices) == 1 and continuous_physical_search
                    ) else canonical_columns
                )
                if any(
                    column_x > anchor.x + 1e-6
                    and all(column_x < target.x - 1e-6 for target in targets)
                    and (
                        vertex_visual_box(copy.copy(anchor)).right
                        + (column_x - anchor.x)
                        + profile.route_clearance
                        <= target_left + 1e-6
                    )
                    for column_x in anchor_columns
                ):
                    scope_can_move = True
                    break
            if not scope_can_move:
                continue
            candidate = _clone_layout_geometry(accepted)
            candidate_by_id = {vertex.cell_id: vertex for vertex in candidate.vertices}
            accepted_by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
            candidate_edge_by_id = {edge.cell_id: edge for edge in candidate.edges}
            accepted_edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
            moved_ids: set[str] = set()
            fixed_boxes = [
                vertex_visual_box(vertex)
                for vertex in candidate.vertices
                if vertex.cell_id not in scope
            ]
            dynamic_boxes = []
            fixed_column_boxes: dict[tuple[float, float], list[Any]] = {}

            def column_obstacles(anchor):
                probe_box = vertex_visual_box(anchor)
                key = (round(probe_box.left, 6), round(probe_box.right, 6))
                if key not in fixed_column_boxes:
                    fixed_column_boxes[key] = [
                        box
                        for box in fixed_boxes
                        if not (
                            box.right + profile.grid <= probe_box.left
                            or box.left >= probe_box.right + profile.grid
                        )
                    ]
                return fixed_column_boxes[key] + dynamic_boxes

            for anchor_id in scope:
                edge_indices = edge_indices_by_anchor.get(anchor_id, [])
                if not edge_indices:
                    continue
                anchor = candidate_by_id[anchor_id]
                targets = [
                    candidate_by_id[candidate_edge_by_id[f"e{index}"].target_id]
                    for index in edge_indices
                ]
                target_left = min(vertex_visual_box(target).left for target in targets)
                feasible = []
                right_overhang = vertex_visual_box(anchor).right - anchor.x
                continuous_latest = (
                    target_left - profile.route_clearance - right_overhang
                )
                anchor_columns = (
                    [*canonical_columns, continuous_latest]
                    if (
                        len(edge_indices) == 1 and continuous_physical_search
                    ) else canonical_columns
                )
                for column_x in anchor_columns:
                    probe = copy.copy(anchor)
                    probe.x = column_x
                    if (
                        column_x >= anchor.x - 1e-6
                        and all(column_x < target.x - 1e-6 for target in targets)
                        and vertex_visual_box(probe).right + profile.route_clearance
                        <= target_left + 1e-6
                    ):
                        feasible.append(column_x)
                if (
                    not feasible
                    or (
                        not continuous_physical_search
                        and max(feasible) <= anchor.x + 1e-6
                    )
                ):
                    continue
                source_port = logical_edges[edge_indices[0] - 1].source_port
                source_anchor_y = port_anchors(
                    anchor.style, anchor.drawclock_type
                )[source_port][1]
                desired_tops = []
                for index, target in zip(edge_indices, targets):
                    logical = logical_edges[index - 1]
                    target_anchor_y = port_anchors(
                        target.style, target.drawclock_type
                    )[logical.target_port][1]
                    desired_tops.append(
                        target.y + target.height * target_anchor_y
                        - anchor.height * source_anchor_y
                    )
                wanted = median(desired_tops)
                original_x, original_y = anchor.x, anchor.y
                if continuous_physical_search:
                    position_choices = []
                    for column_x in feasible:
                        anchor.x = column_x
                        anchor.y = _nearest_clear_anchor_top(
                            anchor, wanted, column_obstacles(anchor), profile.grid
                        )
                        reverse_hits = _edges_hitting_focus_vertices(
                            candidate,
                            logical_edges,
                            set(edge_indices),
                            {anchor_id},
                        )
                        column_displacement = abs(column_x - original_x)
                        position_choices.append((
                            len(reverse_hits),
                            abs(anchor.y - wanted),
                            column_displacement,
                            -column_x,
                            column_x,
                            anchor.y,
                        ))
                    anchor.x, anchor.y = original_x, original_y
                    selected_position = min(position_choices)
                    anchor.x = selected_position[4]
                    anchor.y = selected_position[5]
                else:
                    # The scalable tier searches only canonical columns.  Its
                    # rightmost feasible column is the structural optimum for
                    # route length; the unchanged whole-layout acceptance gate
                    # below rejects any move that worsens visible geometry.
                    anchor.x = max(feasible)
                    anchor.y = _nearest_clear_anchor_top(
                        anchor, wanted, column_obstacles(anchor), profile.grid
                    )
                if (
                    abs(anchor.x - original_x) <= 1e-6
                    and abs(anchor.y - original_y) <= 1e-6
                ):
                    continue
                dynamic_boxes.append(vertex_visual_box(anchor))
                moved_ids.add(anchor_id)

            if not moved_ids:
                continue
            attempted_moves += len(moved_ids)
            changed_edge_indices = {
                index
                for anchor_id in moved_ids
                for index in edge_indices_by_anchor[anchor_id]
            }
            for anchor_id in moved_ids:
                edge_indices = edge_indices_by_anchor[anchor_id]
                anchor = candidate_by_id[anchor_id]
                old_anchor = accepted_by_id[anchor_id]
                old_first_xs = []
                common_right = math.inf
                edge_data = []
                for index in edge_indices:
                    edge = candidate_edge_by_id[f"e{index}"]
                    old_edge = accepted_edge_by_id[f"e{index}"]
                    logical = logical_edges[index - 1]
                    target = candidate_by_id[edge.target_id]
                    old_target = accepted_by_id[old_edge.target_id]
                    old_start = abs_port_xy(
                        old_anchor.x, old_anchor.y, old_anchor.width, old_anchor.height,
                        old_anchor.style, old_anchor.drawclock_type, logical.source_port,
                    )
                    old_end = abs_port_xy(
                        old_target.x, old_target.y, old_target.width, old_target.height,
                        old_target.style, old_target.drawclock_type, logical.target_port,
                    )
                    old_points = _simplify([old_start, *old_edge.waypoints, old_end])
                    if len(old_points) > 2:
                        old_first_xs.append(old_points[1][0])
                    common_right = min(
                        common_right,
                        vertex_visual_box(target).left - profile.route_clearance,
                    )
                    edge_data.append((edge, logical, target, old_points))
                common_left = vertex_visual_box(anchor).right + profile.route_clearance
                preferred_x = median(old_first_xs) if old_first_xs else (
                    (common_left + common_right) / 2.0
                    if common_left <= common_right + 1e-6 else common_left
                )
                trunk_x = (
                    min(max(preferred_x, common_left), common_right)
                    if common_left <= common_right + 1e-6 else common_left
                )
                for edge, logical, target, old_points in edge_data:
                    start = abs_port_xy(
                        anchor.x, anchor.y, anchor.width, anchor.height,
                        anchor.style, anchor.drawclock_type, logical.source_port,
                    )
                    end = abs_port_xy(
                        target.x, target.y, target.width, target.height,
                        target.style, target.drawclock_type, logical.target_port,
                    )
                    if abs(start[1] - end[1]) <= 1e-6:
                        points = [start, end]
                    else:
                        interior = [
                            point for point in old_points[2:-1]
                            if trunk_x - 1e-6 <= point[0] <= end[0] + 1e-6
                        ]
                        points = _simplify([
                            start,
                            (trunk_x, start[1]),
                            *interior,
                            end,
                        ])
                    edge.waypoints = tuple(points[1:-1])

            candidate_report = assess_layout(
                candidate,
                logical_edges,
                0.0,
                reject_geometry_worse_than=(
                    accepted_report["node_overlaps"],
                    accepted_report["edge_node_intersections"],
                ),
            )
            if candidate_report.get("geometry_short_circuit"):
                if candidate_report["node_overlaps"] > accepted_report["node_overlaps"]:
                    blockers["node-overlap"] += 1
                if (
                    candidate_report["edge_node_intersections"]
                    > accepted_report["edge_node_intersections"]
                ):
                    blockers["edge-node"] += 1
                continue
            candidate_visible = _visible_layout_signature(
                candidate,
                logical_edges,
                changed_edge_indices,
                moved_ids,
            )
            candidate_reverse_hits = _edges_hitting_focus_vertices(
                candidate, logical_edges, changed_edge_indices, moved_ids
            )
            accepted_endpoint = _route_endpoint_signature(
                accepted,
                logical_edges,
                changed_edge_indices,
                profile.route_clearance,
            )
            candidate_endpoint = _route_endpoint_signature(
                candidate,
                logical_edges,
                changed_edge_indices,
                profile.route_clearance,
            )
            accepted_facilities = _avoidable_source_facility_pairs(
                accepted,
                logical_edges,
                root,
                _source_facility_opening_cost(accepted),
            )
            candidate_facilities = _avoidable_source_facility_pairs(
                candidate,
                logical_edges,
                root,
                _source_facility_opening_cost(candidate),
            )
            hard_checks = {
                "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
                "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
                "visible-overlap": not candidate_visible[4],
                "visible-edge-node": not candidate_visible[5],
                "reverse-visible-edge-node": not candidate_reverse_hits,
                "endpoint-route": candidate_endpoint.issubset(accepted_endpoint),
                "source-facility": candidate_facilities.issubset(accepted_facilities),
                "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
                "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
            }
            if all(hard_checks.values()) and metric(candidate_report) < metric(accepted_report):
                accepted = candidate
                accepted_report = candidate_report
                accepted_moves += len(moved_ids)
                current_by_id = {
                    vertex.cell_id: vertex for vertex in accepted.vertices
                }
                current_edge_by_id = {
                    edge.cell_id: edge for edge in accepted.edges
                }
                edge_indices_by_anchor = defaultdict(list)
                for edge in accepted.edges:
                    if edge.source_id in anchor_ids:
                        edge_indices_by_anchor[edge.source_id].append(int(edge.cell_id[1:]))
            else:
                blockers.update(name for name, passed in hard_checks.items() if not passed)
                if all(hard_checks.values()):
                    blockers["quality-vector"] += 1

    report = {
        "source_anchor_relocation_attempts": attempted_moves,
        "source_anchor_column_moves": accepted_moves,
        "source_anchor_crossings_removed": (
            initial_report["distinct_crossing_points"]
            - accepted_report["distinct_crossing_points"]
        ),
        "source_anchor_source_crossings_removed": (
            initial_report["source_crossing_points"]
            - accepted_report["source_crossing_points"]
        ),
        "source_anchor_length_saved_px": round(
            initial_report["manhattan_length"] - accepted_report["manhattan_length"], 3
        ),
        "source_anchor_relocation_blockers": dict(sorted(blockers.items())),
    }
    if include_assessment:
        report["_accepted_assessment"] = accepted_report
    return accepted, report


def _split_root_rendering_anchors_by_local_rows(
    document: LayoutDocument,
    nodes,
    logical_edges,
    profile,
    *,
    accepted_assessment: dict[str, Any] | None = None,
    include_assessment: bool = False,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Offer local-row root aliases, accepting only full-layout dominance."""
    indegree = Counter(edge.target for edge in logical_edges)
    outdegree = Counter(edge.source for edge in logical_edges)
    accepted = _clone_layout_geometry(document)
    accepted_report = (
        accepted_assessment
        if accepted_assessment is not None
        else assess_layout(accepted, logical_edges, 0.0)
    )
    initial_report = dict(accepted_report)
    median_height = median(
        [vertex.height for vertex in accepted.vertices] or [1.0]
    )
    centers = sorted({
        round(vertex.y + vertex.height / 2.0, 6)
        for vertex in accepted.vertices
    })
    deltas = [
        right - left
        for left, right in zip(centers, centers[1:])
        if right - left > 1e-6
    ]
    geometry_pitch = max(1.0, median_height + profile.node_spacing)
    row_pitch = (
        max(median_height, min(median(deltas), geometry_pitch))
        if deltas else geometry_pitch
    )
    local_gap_budget = row_pitch * 3.0
    # A second display facility is justified only after a consumer gap spans
    # several ordinary rows.  This is the same geometry-derived facility cost
    # used by the independent redundancy oracle; splitting every adjacent row
    # would merely trade one vertical trunk for visual duplication.
    attempts = 0
    accepted_roots = 0
    accepted_replicas = 0
    blockers: Counter[str] = Counter()

    def metric(report: dict[str, Any]) -> tuple[float, ...]:
        return (
            report["source_crossing_points"],
            report["distinct_crossing_points"],
            report["crossings"],
            report["bends_total"],
            report["manhattan_length"],
            report["area"],
        )

    for root in sorted(nodes):
        if indegree[root] or "layout_column" in nodes[root].item:
            continue
        by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
        edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
        root_anchors = [
            vertex
            for vertex in accepted.vertices
            if (vertex.logical_name or vertex.name) == root
        ]
        # Facility partitioning has one owner.  The earlier exact root
        # partitioner already optimized roots with multiple physical anchors;
        # cutting each of those partitions again can make two independently
        # created neighbours globally mergeable.  This rescue phase therefore
        # opens facilities only for roots that the first phase kept whole.
        # Existing aliases still receive independent column/row optimization
        # in `_relocate_root_rendering_anchors` below.
        if len(root_anchors) != 1:
            continue
        changed_root = False
        for source_anchor in list(root_anchors):
            edge_indices = sorted(
                int(edge.cell_id[1:])
                for edge in accepted.edges
                if edge.source_id == source_anchor.cell_id
            )
            if len(edge_indices) < 2:
                continue
            samples = []
            for index in edge_indices:
                logical = logical_edges[index - 1]
                target = by_id[edge_by_id[f"e{index}"].target_id]
                target_axis = abs_port_xy(
                    target.x, target.y, target.width, target.height,
                    target.style, target.drawclock_type, logical.target_port,
                )[1]
                source_offset = source_anchor.height * port_anchors(
                    source_anchor.style, source_anchor.drawclock_type
                )[logical.source_port][1]
                samples.append((target_axis - source_offset, index))
            ordered = sorted(samples)
            partitions: list[list[int]] = [[ordered[0][1]]]
            for previous, current in zip(ordered, ordered[1:]):
                if current[0] - previous[0] > local_gap_budget + 1e-9:
                    partitions.append([])
                partitions[-1].append(current[1])
            if len(partitions) <= 1:
                continue
            attempts += 1
            candidate = _clone_layout_geometry(accepted)
            candidate_by_id = {vertex.cell_id: vertex for vertex in candidate.vertices}
            candidate_edge_by_id = {edge.cell_id: edge for edge in candidate.edges}
            anchor = candidate_by_id[source_anchor.cell_id]
            anchors = [anchor]
            used_ids = {vertex.cell_id for vertex in candidate.vertices}
            used_names = {vertex.name for vertex in candidate.vertices}
            for replica_index in range(1, len(partitions)):
                replica = copy.copy(anchor)
                suffix = replica_index + 1
                while f"{anchor.cell_id}s{suffix}" in used_ids:
                    suffix += 1
                replica.cell_id = f"{anchor.cell_id}s{suffix}"
                replica.name = f"{root}__local_anchor_{suffix}"
                while replica.name in used_names:
                    suffix += 1
                    replica.cell_id = f"{anchor.cell_id}s{suffix}"
                    replica.name = f"{root}__local_anchor_{suffix}"
                replica.logical_name = root
                used_ids.add(replica.cell_id)
                used_names.add(replica.name)
                anchors.append(replica)
                candidate.vertices.append(replica)

            moving_ids = {item.cell_id for item in anchors}
            canonical_columns = sorted({
                vertex.x for vertex in candidate.vertices
                if vertex.cell_id not in moving_ids
            } | {anchor.x})
            fixed_boxes = [
                vertex_visual_box(vertex)
                for vertex in candidate.vertices
                if vertex.cell_id not in moving_ids
            ]
            dynamic_boxes = []
            fixed_column_boxes: dict[tuple[float, float], list[Any]] = {}
            obstacle_bucket_size = max(row_pitch, profile.node_spacing, 1.0)
            fixed_row_buckets: dict[int, list[int]] = defaultdict(list)
            for box_index, box in enumerate(fixed_boxes):
                for bucket in range(
                    math.floor(box.top / obstacle_bucket_size),
                    math.floor(box.bottom / obstacle_bucket_size) + 1,
                ):
                    fixed_row_buckets[bucket].append(box_index)

            def column_obstacles(anchor):
                probe_box = vertex_visual_box(anchor)
                key = (round(probe_box.left, 6), round(probe_box.right, 6))
                if key not in fixed_column_boxes:
                    fixed_column_boxes[key] = [
                        box
                        for box in fixed_boxes
                        if not (
                            box.right + profile.grid <= probe_box.left
                            or box.left >= probe_box.right + profile.grid
                        )
                    ]
                return fixed_column_boxes[key] + dynamic_boxes

            def route_obstacles(route):
                indices: set[int] = set()
                for a, b in zip(route, route[1:]):
                    low_y, high_y = sorted((a[1], b[1]))
                    for bucket in range(
                        math.floor(low_y / obstacle_bucket_size),
                        math.floor(high_y / obstacle_bucket_size) + 1,
                    ):
                        indices.update(fixed_row_buckets.get(bucket, ()))
                return [fixed_boxes[index] for index in indices] + dynamic_boxes

            for local_anchor, partition in zip(anchors, partitions):
                partition_targets = [
                    candidate_by_id[candidate_edge_by_id[f"e{index}"].target_id]
                    for index in partition
                ]
                target_left = min(
                    vertex_visual_box(target).left
                    for target in partition_targets
                )
                feasible_columns = []
                for column_x in canonical_columns:
                    probe = copy.copy(local_anchor)
                    probe.x = column_x
                    if (
                        all(column_x < target.x - 1e-6 for target in partition_targets)
                        and vertex_visual_box(probe).right + profile.route_clearance
                        <= target_left + 1e-6
                    ):
                        feasible_columns.append(column_x)
                desired = [value for value, index in samples if index in partition]
                wanted = median(desired)
                column_choices = []
                target_box_by_id = {
                    target.cell_id: vertex_visual_box(target)
                    for target in partition_targets
                }
                for column_x in sorted(feasible_columns, reverse=True):
                    probe = copy.copy(local_anchor)
                    probe.x = column_x
                    probe.y = wanted
                    probe.y = _nearest_clear_anchor_top(
                        probe, wanted, column_obstacles(probe), profile.grid
                    )
                    route_hits = 0
                    for index in partition:
                        logical = logical_edges[index - 1]
                        target = candidate_by_id[
                            candidate_edge_by_id[f"e{index}"].target_id
                        ]
                        start = abs_port_xy(
                            probe.x, probe.y, probe.width, probe.height,
                            probe.style, probe.drawclock_type,
                            logical.source_port,
                        )
                        end = abs_port_xy(
                            target.x, target.y, target.width, target.height,
                            target.style, target.drawclock_type,
                            logical.target_port,
                        )
                        if abs(start[1] - end[1]) <= 1e-6:
                            route = [start, end]
                        else:
                            left = vertex_visual_box(probe).right + profile.route_clearance
                            right = vertex_visual_box(target).left - profile.route_clearance
                            lane = (left + right) / 2.0 if left <= right else left
                            route = _simplify([
                                start,
                                (lane, start[1]),
                                (lane, end[1]),
                                end,
                            ])
                        route_hits += sum(
                            _segment_hits_rect(
                                a, b, (box.left, box.top, box.right, box.bottom)
                            )
                            for a, b in zip(route, route[1:])
                            for box in route_obstacles(route)
                            if box != target_box_by_id[target.cell_id]
                        )
                    column_choices.append((
                        route_hits,
                        -column_x,
                        abs(probe.y - wanted),
                        probe,
                    ))
                if column_choices:
                    selected_probe = min(column_choices, key=lambda item: item[:3])[3]
                    local_anchor.x = selected_probe.x
                    local_anchor.y = selected_probe.y
                else:
                    local_anchor.y = _nearest_clear_anchor_top(
                        local_anchor,
                        wanted,
                        column_obstacles(local_anchor),
                        profile.grid,
                    )
                dynamic_boxes.append(vertex_visual_box(local_anchor))

            accepted_edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
            accepted_by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
            for local_anchor, partition in zip(anchors, partitions):
                old_first_xs = []
                common_right = math.inf
                route_data = []
                for index in partition:
                    edge = candidate_edge_by_id[f"e{index}"]
                    old_edge = accepted_edge_by_id[f"e{index}"]
                    logical = logical_edges[index - 1]
                    target = candidate_by_id[edge.target_id]
                    old_target = accepted_by_id[old_edge.target_id]
                    old_start = abs_port_xy(
                        source_anchor.x, source_anchor.y,
                        source_anchor.width, source_anchor.height,
                        source_anchor.style, source_anchor.drawclock_type,
                        logical.source_port,
                    )
                    old_end = abs_port_xy(
                        old_target.x, old_target.y,
                        old_target.width, old_target.height,
                        old_target.style, old_target.drawclock_type,
                        logical.target_port,
                    )
                    old_points = _simplify([old_start, *old_edge.waypoints, old_end])
                    if len(old_points) > 2:
                        old_first_xs.append(old_points[1][0])
                    common_right = min(
                        common_right,
                        vertex_visual_box(target).left - profile.route_clearance,
                    )
                    route_data.append((edge, logical, target, old_points))
                common_left = vertex_visual_box(local_anchor).right + profile.route_clearance
                preferred_x = median(old_first_xs) if old_first_xs else (
                    (common_left + common_right) / 2.0
                    if common_left <= common_right + 1e-6 else common_left
                )
                trunk_x = (
                    min(max(preferred_x, common_left), common_right)
                    if common_left <= common_right + 1e-6 else common_left
                )
                for edge, logical, target, old_points in route_data:
                    edge.source_id = local_anchor.cell_id
                    start = abs_port_xy(
                        local_anchor.x, local_anchor.y,
                        local_anchor.width, local_anchor.height,
                        local_anchor.style, local_anchor.drawclock_type,
                        logical.source_port,
                    )
                    end = abs_port_xy(
                        target.x, target.y, target.width, target.height,
                        target.style, target.drawclock_type, logical.target_port,
                    )
                    if abs(start[1] - end[1]) <= 1e-6:
                        points = [start, end]
                    else:
                        # A physical source alias is a new routing facility,
                        # not a translated copy of the old route.  Reusing
                        # downstream waypoints from a different row/column can
                        # create a connector that cuts through an unrelated
                        # node before it reaches that old channel.  Recompute
                        # the minimum-bend orthogonal route from the exact new
                        # port; the whole-layout oracle below rejects it if the
                        # clean H-V-H candidate introduces a harder conflict.
                        points = _simplify([
                            start,
                            (trunk_x, start[1]),
                            (trunk_x, end[1]),
                            end,
                        ])
                    edge.waypoints = tuple(points[1:-1])

            candidate.vertices.sort(key=lambda vertex: vertex.name)
            changed_edge_indices = {
                index for _, index in samples
            }
            candidate_report = assess_layout(
                candidate,
                logical_edges,
                0.0,
                reject_geometry_worse_than=(
                    accepted_report["node_overlaps"],
                    accepted_report["edge_node_intersections"],
                ),
            )
            if candidate_report.get("geometry_short_circuit"):
                if candidate_report["node_overlaps"] > accepted_report["node_overlaps"]:
                    blockers["node-overlap"] += 1
                if (
                    candidate_report["edge_node_intersections"]
                    > accepted_report["edge_node_intersections"]
                ):
                    blockers["edge-node"] += 1
                continue
            candidate_focus_ids = {anchor.cell_id for anchor in anchors}
            candidate_visible = _visible_layout_signature(
                candidate,
                logical_edges,
                changed_edge_indices,
                candidate_focus_ids,
            )
            candidate_reverse_hits = _edges_hitting_focus_vertices(
                candidate,
                logical_edges,
                changed_edge_indices,
                candidate_focus_ids,
            )
            accepted_endpoint = _route_endpoint_signature(
                accepted,
                logical_edges,
                changed_edge_indices,
                profile.route_clearance,
            )
            candidate_endpoint = _route_endpoint_signature(
                candidate,
                logical_edges,
                changed_edge_indices,
                profile.route_clearance,
            )
            accepted_facilities = _avoidable_source_facility_pairs(
                accepted,
                logical_edges,
                root,
                _source_facility_opening_cost(accepted),
            )
            candidate_facilities = _avoidable_source_facility_pairs(
                candidate,
                logical_edges,
                root,
                _source_facility_opening_cost(candidate),
            )
            hard_checks = {
                "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
                "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
                "visible-overlap": not candidate_visible[4],
                "visible-edge-node": not candidate_visible[5],
                "reverse-visible-edge-node": not candidate_reverse_hits,
                "endpoint-route": candidate_endpoint.issubset(accepted_endpoint),
                "source-facility": candidate_facilities.issubset(accepted_facilities),
                "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
                "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
            }
            if all(hard_checks.values()) and metric(candidate_report) < metric(accepted_report):
                accepted = candidate
                accepted_report = candidate_report
                accepted_replicas += len(partitions) - 1
                changed_root = True
                by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
                edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
            else:
                blockers.update(name for name, passed in hard_checks.items() if not passed)
                if all(hard_checks.values()):
                    blockers["quality-vector"] += 1
        if changed_root:
            accepted_roots += 1

    report = {
        "source_local_partition_attempts": attempts,
        "source_local_partition_roots": accepted_roots,
        "source_local_partition_replicas": accepted_replicas,
        "source_local_partition_row_pitch_px": round(row_pitch, 3),
        "source_local_partition_gap_budget_px": round(local_gap_budget, 3),
        "source_local_partition_crossings_removed": (
            initial_report["distinct_crossing_points"]
            - accepted_report["distinct_crossing_points"]
        ),
        "source_local_partition_source_crossings_removed": (
            initial_report["source_crossing_points"]
            - accepted_report["source_crossing_points"]
        ),
        "source_local_partition_length_saved_px": round(
            initial_report["manhattan_length"] - accepted_report["manhattan_length"], 3
        ),
        "source_local_partition_blockers": dict(sorted(blockers.items())),
    }
    if include_assessment:
        report["_accepted_assessment"] = accepted_report
    return accepted, report


def _open_root_facility_corridors(
    document: LayoutDocument,
    nodes,
    logical_edges,
    profile,
    *,
    accepted_assessment: dict[str, Any] | None = None,
    include_assessment: bool = False,
    _batch_zero: bool = True,
    _sequential_fallback: bool = True,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Open a consumer-side corridor for a dominated one-edge root facility.

    A physical rendering anchor is the optimization unit.  Logical fanout is
    deliberately irrelevant: an already replicated root may have one edge per
    facility.  The corridor width comes from the anchor's complete visible box
    plus routing clearance, and every consumer rank at or to the right of the
    target moves together.  No component kind, name, row count, or sample size
    participates in the decision.
    """
    indegree = Counter(edge.target for edge in logical_edges)
    accepted = _clone_layout_geometry(document)
    accepted_report = (
        accepted_assessment
        if accepted_assessment is not None
        else assess_layout(accepted, logical_edges, 0.0)
    )
    initial_report = dict(accepted_report)
    attempts = 0
    moves = 0
    expanded_px = 0.0
    retired_facilities = 0
    blockers: Counter[str] = Counter()

    def facility_pairs(doc: LayoutDocument, root_names) -> frozenset:
        opening_cost = _source_facility_opening_cost(doc)
        return frozenset(
            (root_name, *pair)
            for root_name in root_names
            for pair in _avoidable_source_facility_pairs(
                doc, logical_edges, root_name, opening_cost
            )
        )

    def metric(report: dict[str, Any]) -> tuple[float, ...]:
        return (
            report["source_crossing_points"],
            report["distinct_crossing_points"],
            report["crossings"],
            report["bends_total"],
            report["manhattan_length"],
            report["area"],
        )

    outdegree = Counter(edge.source for edge in logical_edges)
    rank_outgoing: dict[str, list[str]] = defaultdict(list)
    rank_indegree = {name: 0 for name in nodes}
    for logical_edge in logical_edges:
        rank_outgoing[logical_edge.source].append(logical_edge.target)
        rank_indegree[logical_edge.target] += 1
    rank_queue = [name for name in nodes if rank_indegree[name] == 0]
    rank_order = []
    earliest_rank = {name: 0 for name in nodes}
    queue_index = 0
    while queue_index < len(rank_queue):
        name = rank_queue[queue_index]
        queue_index += 1
        rank_order.append(name)
        for child in rank_outgoing[name]:
            earliest_rank[child] = max(
                earliest_rank[child], earliest_rank[name] + 1
            )
            rank_indegree[child] -= 1
            if rank_indegree[child] == 0:
                rank_queue.append(child)
    logical_rank = {
        name: max(earliest_rank.values(), default=0) for name in nodes
    }
    for name in reversed(rank_order):
        if rank_outgoing[name]:
            logical_rank[name] = min(
                logical_rank[child] - 1 for child in rank_outgoing[name]
            )
    occupied_ranks = sorted(set(logical_rank.values()))
    previous_rank = {
        rank: occupied_ranks[index - 1]
        for index, rank in enumerate(occupied_ranks)
        if index > 0
    }

    def root_layer_inversions(doc: LayoutDocument) -> frozenset[str]:
        """Return free one-edge roots left of the preceding ALAP rank."""
        primary = {
            vertex.name: vertex
            for vertex in doc.vertices
            if vertex.name in nodes
        }
        max_axis_by_rank: dict[int, float] = {}
        for name, vertex in primary.items():
            box = vertex_visual_box(vertex)
            axis = (box.left + box.right) / 2.0
            rank = logical_rank[name]
            max_axis_by_rank[rank] = max(
                max_axis_by_rank.get(rank, -math.inf), axis
            )
        inversions = set()
        for name, vertex in primary.items():
            rank = logical_rank[name]
            if (
                indegree[name] != 0
                or outdegree[name] != 1
                or rank not in previous_rank
                or "layout_column" in nodes[name].item
            ):
                continue
            box = vertex_visual_box(vertex)
            axis = (box.left + box.right) / 2.0
            if axis <= max_axis_by_rank.get(previous_rank[rank], -math.inf) + 1e-6:
                inversions.add(name)
        return frozenset(inversions)

    def points_for(
        doc: LayoutDocument,
        edge_index: int,
        by_id=None,
        edge_by_id=None,
    ):
        if by_id is None:
            by_id = {vertex.cell_id: vertex for vertex in doc.vertices}
        if edge_by_id is None:
            edge_by_id = {edge.cell_id: edge for edge in doc.edges}
        edge = edge_by_id[f"e{edge_index}"]
        logical = logical_edges[edge_index - 1]
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

    def route_segment_hits_rect(a, b, rect) -> bool:
        """Snap numerical axis noise before the strict rectangle predicate."""
        if abs(a[0] - b[0]) <= 1e-6:
            b = (a[0], b[1])
        elif abs(a[1] - b[1]) <= 1e-6:
            b = (b[0], a[1])
        return _segment_hits_rect(a, b, rect)

    roots = {
        name for name in nodes
        if indegree[name] == 0 and "layout_column" not in nodes[name].item
    }
    anchor_ids = [
        vertex.cell_id for vertex in accepted.vertices
        if (vertex.logical_name or vertex.name) in roots
    ]
    jobs: list[tuple[str, int, bool]] = []
    job_by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
    job_edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
    job_statistics = assess_layout(
        accepted,
        logical_edges,
        0.0,
        include_routing_statistics=True,
        reuse_hard_metrics=accepted_report,
    )["routing_statistics"]["edges"]
    for anchor_id in anchor_ids:
        owned = [
            int(edge.cell_id[1:])
            for edge in accepted.edges if edge.source_id == anchor_id
        ]
        for edge_index in owned:
            route = points_for(
                accepted, edge_index, job_by_id, job_edge_by_id
            )
            if (
                len(route) - 2 >= 4
                or job_statistics[f"e{edge_index}"]["crossing_pair_incidents"] > 0
            ):
                jobs.append((anchor_id, edge_index, len(owned) > 1))

    jobs.sort(key=lambda job: (
        -job_statistics[f"e{job[1]}"]["crossing_pair_incidents"],
        -job_statistics[f"e{job[1]}"]["bends"],
        -job_statistics[f"e{job[1]}"]["manhattan_length_px"],
        job[1],
        job[0],
    ))

    segment_bucket_size = max(64.0, profile.node_spacing * 4.0)
    base_segments: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
    base_segment_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)

    def segment_bucket_keys(a, b):
        left, right = sorted((a[0], b[0]))
        top, bottom = sorted((a[1], b[1]))
        for bx in range(
            math.floor(left / segment_bucket_size),
            math.floor(right / segment_bucket_size) + 1,
        ):
            for by in range(
                math.floor(top / segment_bucket_size),
                math.floor(bottom / segment_bucket_size) + 1,
            ):
                yield bx, by

    for base_edge_index in range(1, len(logical_edges) + 1):
        base_points = points_for(
            accepted, base_edge_index, job_by_id, job_edge_by_id
        )
        for a, b in zip(base_points, base_points[1:]):
            segment_index = len(base_segments)
            base_segments.append((base_edge_index, a, b))
            for key in segment_bucket_keys(a, b):
                base_segment_buckets[key].append(segment_index)

    route_point_cache: dict[int, list[tuple[float, float]]] = {}
    pending_changed_edges: set[int] = set()
    pending_moves = 0
    pending_base = None
    pending_base_report = None
    pending_base_visible = None
    pending_first = None
    pending_checkpoints: list[tuple[int, LayoutDocument]] = []
    pending_roots: set[str] = set()
    for anchor_id, edge_index, needs_replica in jobs:
        by_id = {vertex.cell_id: vertex for vertex in accepted.vertices}
        edge_by_id = {edge.cell_id: edge for edge in accepted.edges}
        edge = edge_by_id[f"e{edge_index}"]
        if edge.source_id != anchor_id:
            continue
        attempts += 1
        best = None
        best_report = None
        best_expansion = 0.0
        best_deferred = False
        source = by_id[anchor_id]
        target = by_id[edge.target_id]
        source_box = vertex_visual_box(source)
        corridor_width = (
            source_box.right - source_box.left
            + 2.0 * profile.route_clearance
        )
        expansions = (0.0,) if pending_moves else (0.0, corridor_width)
        for expansion in expansions:
            candidate = _clone_layout_geometry(accepted)
            candidate_by_id = {
                vertex.cell_id: vertex for vertex in candidate.vertices
            }
            candidate_edge_by_id = {
                item.cell_id: item for item in candidate.edges
            }
            candidate_source = candidate_by_id[anchor_id]
            candidate_edge = candidate_edge_by_id[f"e{edge_index}"]
            if needs_replica:
                replica = copy.copy(candidate_source)
                suffix = edge_index
                used_ids = set(candidate_by_id)
                used_names = {vertex.name for vertex in candidate.vertices}
                while f"{anchor_id}c{suffix}" in used_ids:
                    suffix += len(logical_edges) + 1
                replica.cell_id = f"{anchor_id}c{suffix}"
                replica.name = f"{source.name}__corridor_{suffix}"
                while replica.name in used_names:
                    suffix += len(logical_edges) + 1
                    replica.cell_id = f"{anchor_id}c{suffix}"
                    replica.name = f"{source.name}__corridor_{suffix}"
                replica.logical_name = source.logical_name or source.name
                candidate.vertices.append(replica)
                candidate_by_id[replica.cell_id] = replica
                candidate_source = replica
                candidate_edge.source_id = replica.cell_id
            candidate_target = candidate_by_id[candidate_edge.target_id]
            suffix_x = target.x
            if expansion > 0.0:
                for vertex in candidate.vertices:
                    if (
                        vertex.cell_id != candidate_source.cell_id
                        and vertex.x >= suffix_x - 1e-6
                    ):
                        vertex.x += expansion
                for layout_edge in candidate.edges:
                    layout_edge.waypoints = tuple(
                        (
                            x + (expansion if x >= suffix_x - 1e-6 else 0.0),
                            y,
                        )
                        for x, y in layout_edge.waypoints
                    )
            logical = logical_edges[edge_index - 1]
            target_box = vertex_visual_box(candidate_target)
            right_overhang = (
                vertex_visual_box(candidate_source).right - candidate_source.x
            )
            candidate_source.x = (
                target_box.left - profile.route_clearance - right_overhang
            )
            source_anchor = port_anchors(
                candidate_source.style, candidate_source.drawclock_type
            )[logical.source_port]
            target_anchor = port_anchors(
                candidate_target.style, candidate_target.drawclock_type
            )[logical.target_port]
            candidate_source.y = (
                candidate_target.y + candidate_target.height * target_anchor[1]
                - candidate_source.height * source_anchor[1]
            )
            start = abs_port_xy(
                candidate_source.x, candidate_source.y,
                candidate_source.width, candidate_source.height,
                candidate_source.style, candidate_source.drawclock_type,
                logical.source_port,
            )
            end = abs_port_xy(
                candidate_target.x, candidate_target.y,
                candidate_target.width, candidate_target.height,
                candidate_target.style, candidate_target.drawclock_type,
                logical.target_port,
            )
            candidate_edge.waypoints = tuple(_simplify([start, end])[1:-1])
            source_visible = vertex_visual_box(candidate_source)
            source_rect = (
                source_visible.left,
                source_visible.top,
                source_visible.right,
                source_visible.bottom,
            )
            visible_overlap = False
            candidate_edge_hit = False
            for vertex in candidate.vertices:
                if vertex.cell_id in (
                    candidate_source.cell_id, candidate_target.cell_id
                ):
                    continue
                box = vertex_visual_box(vertex)
                if (
                    max(source_visible.left, box.left)
                    < min(source_visible.right, box.right) - 1e-6
                    and max(source_visible.top, box.top)
                    < min(source_visible.bottom, box.bottom) - 1e-6
                ):
                    visible_overlap = True
                if route_segment_hits_rect(
                    start, end, (box.left, box.top, box.right, box.bottom)
                ):
                    candidate_edge_hit = True
                if visible_overlap and candidate_edge_hit:
                    break
            reverse_hit = False
            if not visible_overlap and not candidate_edge_hit:
                if expansion == 0.0:
                    nearby_segments: set[int] = set()
                    for key in segment_bucket_keys(
                        (source_visible.left, source_visible.top),
                        (source_visible.right, source_visible.bottom),
                    ):
                        nearby_segments.update(
                            base_segment_buckets.get(key, ())
                        )
                    reverse_hit = any(
                        owner != edge_index
                        and owner not in pending_changed_edges
                        and route_segment_hits_rect(a, b, source_rect)
                        for segment_index in nearby_segments
                        for owner, a, b in (base_segments[segment_index],)
                    )
                    if not reverse_hit:
                        for changed_index in pending_changed_edges:
                            changed_points = points_for(
                                accepted, changed_index, by_id, edge_by_id
                            )
                            if any(
                                route_segment_hits_rect(a, b, source_rect)
                                for a, b in zip(
                                    changed_points, changed_points[1:]
                                )
                            ):
                                reverse_hit = True
                                break
                else:
                    for other_index in range(1, len(logical_edges) + 1):
                        if other_index == edge_index:
                            continue
                        if other_index not in route_point_cache:
                            route_point_cache[other_index] = points_for(
                                accepted, other_index, by_id, edge_by_id
                            )
                        old_points = route_point_cache[other_index]
                        transformed_points = [
                            (
                                x + (
                                    expansion
                                    if x >= suffix_x - 1e-6 else 0.0
                                ),
                                y,
                            )
                            for x, y in old_points
                        ]
                        if any(
                            route_segment_hits_rect(a, b, source_rect)
                            for a, b in zip(
                                transformed_points, transformed_points[1:]
                            )
                        ):
                            reverse_hit = True
                            break
            if visible_overlap or candidate_edge_hit or reverse_hit:
                if visible_overlap:
                    blockers["visible-overlap"] += 1
                if candidate_edge_hit or reverse_hit:
                    blockers["visible-edge-node"] += 1
                continue
            if expansion == 0.0 and _batch_zero:
                # Zero-width moves alter only this root facility and its one
                # direct edge.  Accumulate locally safe moves, then validate
                # their union once against the complete layout.  Expanded
                # suffix moves remain individually transactional.
                best = candidate
                best_deferred = True
                break
            candidate_report = assess_layout(
                candidate,
                logical_edges,
                0.0,
                reuse_hard_metrics=accepted_report,
            )
            root_name = logical.source
            accepted_facilities = facility_pairs(accepted, {root_name})
            candidate_facilities = facility_pairs(candidate, {root_name})
            hard_checks = {
                "node-overlap": candidate_report["node_overlaps"] <= accepted_report["node_overlaps"],
                "edge-node": candidate_report["edge_node_intersections"] <= accepted_report["edge_node_intersections"],
                "direction": candidate_report["direction_violations"] <= accepted_report["direction_violations"],
                "route-overlap": candidate_report["ambiguous_overlaps"] <= accepted_report["ambiguous_overlaps"],
                "source-facility": candidate_facilities.issubset(accepted_facilities),
                "root-layer": root_layer_inversions(candidate).issubset(
                    root_layer_inversions(accepted)
                ),
            }
            if not all(hard_checks.values()):
                blockers.update(name for name, passed in hard_checks.items() if not passed)
                continue
            if metric(candidate_report) >= metric(accepted_report):
                blockers["quality-vector"] += 1
                continue
            if best_report is None or metric(candidate_report) < metric(best_report):
                best = candidate
                best_report = candidate_report
                best_expansion = expansion
        if best is not None:
            if best_deferred:
                if pending_moves == 0:
                    pending_base = _clone_layout_geometry(accepted)
                    pending_base_report = accepted_report
                    pending_base_visible = _visible_layout_signature(
                        accepted, logical_edges
                    )
                    pending_first = _clone_layout_geometry(candidate)
                accepted = best
                pending_moves += 1
                pending_roots.add(logical.source)
                pending_changed_edges.add(edge_index)
                if pending_moves % 16 == 0:
                    pending_checkpoints.append((
                        pending_moves,
                        _clone_layout_geometry(accepted),
                    ))
                route_point_cache.clear()
                continue
            accepted = best
            accepted_report = best_report
            route_point_cache.clear()
            moves += 1
            expanded_px += best_expansion
            # An expanded suffix invalidates the base spatial index.  Commit
            # one such coordinate transaction per convergence pass, then let
            # the caller rebuild exact indices for the new geometry.
            if best_expansion > 0.0:
                break

    if pending_moves:
        pending_report = assess_layout(accepted, logical_edges, 0.0)
        pending_visible = _visible_layout_signature(accepted, logical_edges)
        pending_checks = {
            "node-overlap": pending_report["node_overlaps"] <= pending_base_report["node_overlaps"],
            "edge-node": pending_report["edge_node_intersections"] <= pending_base_report["edge_node_intersections"],
            "visible-overlap": pending_visible[4].issubset(pending_base_visible[4]),
            "visible-edge-node": pending_visible[5].issubset(pending_base_visible[5]),
            "direction": pending_report["direction_violations"] <= pending_base_report["direction_violations"],
            "route-overlap": pending_report["ambiguous_overlaps"] <= pending_base_report["ambiguous_overlaps"],
            "source-facility": facility_pairs(accepted, pending_roots).issubset(
                facility_pairs(pending_base, pending_roots)
            ),
            "root-layer": root_layer_inversions(accepted).issubset(
                root_layer_inversions(pending_base)
            ),
            "quality-vector": metric(pending_report) < metric(pending_base_report),
        }
        if all(pending_checks.values()):
            accepted_report = pending_report
            moves += pending_moves
        else:
            accepted = pending_base
            accepted_report = pending_base_report
            blockers.update(
                f"batch-{name}"
                for name, passed in pending_checks.items() if not passed
            )
            if not _sequential_fallback:
                report = {
                    "source_corridor_attempts": attempts,
                    "source_corridor_moves": moves,
                    "source_corridor_retired_facilities": 0,
                    "source_corridor_expanded_px": round(expanded_px, 3),
                    "source_corridor_crossings_removed": (
                        initial_report["distinct_crossing_points"]
                        - accepted_report["distinct_crossing_points"]
                    ),
                    "source_corridor_bends_removed": (
                        initial_report["bends_total"]
                        - accepted_report["bends_total"]
                    ),
                    "source_corridor_blockers": dict(sorted(blockers.items())),
                }
                if include_assessment:
                    report["_accepted_assessment"] = accepted_report
                return accepted, report
            accepted_prefix = None
            accepted_prefix_report = None
            accepted_prefix_count = 0
            for prefix_count, prefix_document in pending_checkpoints:
                prefix_report = assess_layout(
                    prefix_document, logical_edges, 0.0
                )
                prefix_visible = _visible_layout_signature(
                    prefix_document, logical_edges
                )
                prefix_checks = {
                    "node-overlap": prefix_report["node_overlaps"] <= pending_base_report["node_overlaps"],
                    "edge-node": prefix_report["edge_node_intersections"] <= pending_base_report["edge_node_intersections"],
                    "visible-overlap": prefix_visible[4].issubset(pending_base_visible[4]),
                    "visible-edge-node": prefix_visible[5].issubset(pending_base_visible[5]),
                    "direction": prefix_report["direction_violations"] <= pending_base_report["direction_violations"],
                    "route-overlap": prefix_report["ambiguous_overlaps"] <= pending_base_report["ambiguous_overlaps"],
                    "source-facility": facility_pairs(
                        prefix_document, pending_roots
                    ).issubset(facility_pairs(pending_base, pending_roots)),
                    "root-layer": root_layer_inversions(prefix_document).issubset(
                        root_layer_inversions(pending_base)
                    ),
                    "quality-vector": metric(prefix_report) < metric(pending_base_report),
                }
                if not all(prefix_checks.values()):
                    break
                accepted_prefix = prefix_document
                accepted_prefix_report = prefix_report
                accepted_prefix_count = prefix_count
            if accepted_prefix is not None:
                accepted = accepted_prefix
                accepted_report = accepted_prefix_report
                moves += accepted_prefix_count
            else:
                first_report = assess_layout(pending_first, logical_edges, 0.0)
                first_visible = _visible_layout_signature(
                    pending_first, logical_edges
                )
                first_checks = {
                    "node-overlap": first_report["node_overlaps"] <= pending_base_report["node_overlaps"],
                    "edge-node": first_report["edge_node_intersections"] <= pending_base_report["edge_node_intersections"],
                    "visible-overlap": first_visible[4].issubset(pending_base_visible[4]),
                    "visible-edge-node": first_visible[5].issubset(pending_base_visible[5]),
                    "direction": first_report["direction_violations"] <= pending_base_report["direction_violations"],
                    "route-overlap": first_report["ambiguous_overlaps"] <= pending_base_report["ambiguous_overlaps"],
                    "source-facility": facility_pairs(
                        pending_first, pending_roots
                    ).issubset(facility_pairs(pending_base, pending_roots)),
                    "root-layer": root_layer_inversions(pending_first).issubset(
                        root_layer_inversions(pending_base)
                    ),
                    "quality-vector": metric(first_report) < metric(pending_base_report),
                }
                if all(first_checks.values()):
                    accepted = pending_first
                    accepted_report = first_report
                    moves += 1
                else:
                    blockers.update(
                        f"sequential-{name}"
                        for name, passed in first_checks.items() if not passed
                    )
                    sequential_document, sequential_report = (
                        _open_root_facility_corridors(
                            pending_base,
                            nodes,
                            logical_edges,
                            profile,
                            accepted_assessment=pending_base_report,
                            include_assessment=include_assessment,
                            _batch_zero=False,
                            _sequential_fallback=_sequential_fallback,
                        )
                    )
                    sequential_report["source_corridor_attempts"] += attempts
                    sequential_report["source_corridor_moves"] += moves
                    sequential_report["source_corridor_expanded_px"] = round(
                        sequential_report["source_corridor_expanded_px"]
                        + expanded_px,
                        3,
                    )
                    merged_blockers = Counter(blockers)
                    merged_blockers.update(
                        sequential_report["source_corridor_blockers"]
                    )
                    sequential_report["source_corridor_blockers"] = dict(
                        sorted(merged_blockers.items())
                    )
                    return sequential_document, sequential_report

    served_ids = {edge.source_id for edge in accepted.edges}
    served_logical = {
        vertex.logical_name or vertex.name
        for vertex in accepted.vertices
        if vertex.cell_id in served_ids
    }
    for logical_name in sorted(roots):
        primary = next(
            (
                vertex for vertex in accepted.vertices
                if vertex.name == logical_name
                and (vertex.logical_name or vertex.name) == logical_name
            ),
            None,
        )
        if (
            primary is not None
            and primary.cell_id not in served_ids
            and logical_name in served_logical
        ):
            replacement = min(
                (
                    vertex for vertex in accepted.vertices
                    if vertex.cell_id in served_ids
                    and (vertex.logical_name or vertex.name) == logical_name
                ),
                key=lambda vertex: vertex.cell_id,
            )
            replacement.name = logical_name
    kept_vertices = []
    for vertex in accepted.vertices:
        logical_name = vertex.logical_name or vertex.name
        if (
            logical_name in roots
            and vertex.cell_id not in served_ids
            and logical_name in served_logical
        ):
            retired_facilities += 1
            continue
        kept_vertices.append(vertex)
    if retired_facilities:
        accepted.vertices = kept_vertices
        accepted_report = assess_layout(accepted, logical_edges, 0.0)

    report = {
        "source_corridor_attempts": attempts,
        "source_corridor_moves": moves,
        "source_corridor_retired_facilities": retired_facilities,
        "source_corridor_expanded_px": round(expanded_px, 3),
        "source_corridor_crossings_removed": (
            initial_report["distinct_crossing_points"]
            - accepted_report["distinct_crossing_points"]
        ),
        "source_corridor_bends_removed": (
            initial_report["bends_total"] - accepted_report["bends_total"]
        ),
        "source_corridor_blockers": dict(sorted(blockers.items())),
    }
    if include_assessment:
        report["_accepted_assessment"] = accepted_report
    return accepted, report


def generate_elk_layout(
    config: dict[str, dict[str, Any]],
    *,
    library_path: LibrarySource,
    component_hints: dict[str, str] | None = None,
    profile_name: str = "readable",
    include_statistics: bool = False,
) -> tuple[LayoutDocument, dict[str, Any]]:
    """Compute exact-rank, exact-port layout with one deterministic policy."""
    started = time.perf_counter()
    if profile_name not in PROFILES:
        raise ValueError(f"未知布局 profile: {profile_name}")
    library_path = library_cache_key(library_path)
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
    if plan.mode == "quality":
        document, leaf_row_report = _refine_leaf_continuation_rows(
            document,
            logical_edges,
            route_clearance=profile.route_clearance,
        )
    else:
        leaf_row_report = {
            "leaf_continuation_row_moves": 0,
            "leaf_continuation_bends_removed": 0,
            "leaf_continuation_blockers": {},
        }
    report["selection"].update(leaf_row_report)
    document, chain_axis_report = _refine_exclusive_upstream_chain_axes(
        document,
        logical_edges,
        route_clearance=profile.route_clearance,
    )
    report["selection"].update(chain_axis_report)
    document, joint_report = _refine_joint_coordinates(
        document,
        logical_edges,
        eligible_vertex_ids=non_root_vertex_ids,
        route_clearance=profile.route_clearance,
    )
    report["selection"].update(joint_report)
    document, replica_report = _replicate_dispersed_roots(
        document,
        nodes,
        logical_edges,
        profile,
        include_assessment=True,
    )
    source_assessment = replica_report.pop("_accepted_assessment")
    report["selection"].update(replica_report)
    document, local_partition_report = _split_root_rendering_anchors_by_local_rows(
        document,
        nodes,
        logical_edges,
        profile,
        accepted_assessment=source_assessment,
        include_assessment=True,
    )
    source_assessment = local_partition_report.pop("_accepted_assessment")
    report["selection"].update(local_partition_report)
    precise_root_search_allowed = (
        plan.gap_pair_work
        <= 64 * max(1, len(nodes) + plan.edge_span_load)
    )
    document, anchor_relocation_report = _relocate_root_rendering_anchors(
        document,
        nodes,
        logical_edges,
        profile,
        accepted_assessment=source_assessment,
        include_assessment=True,
        continuous_physical_search=precise_root_search_allowed,
    )
    accepted_assessment = anchor_relocation_report.pop("_accepted_assessment")
    anchor_numeric_keys = (
        "source_anchor_relocation_attempts",
        "source_anchor_column_moves",
        "source_anchor_crossings_removed",
        "source_anchor_source_crossings_removed",
        "source_anchor_length_saved_px",
    )
    anchor_totals = {
        key: anchor_relocation_report[key] for key in anchor_numeric_keys
    }
    pre_corridor_anchor_totals = dict(anchor_totals)
    anchor_blockers: Counter[str] = Counter(
        anchor_relocation_report["source_anchor_relocation_blockers"]
    )
    corridor_totals = {
        "source_corridor_attempts": 0,
        "source_corridor_moves": 0,
        "source_corridor_retired_facilities": 0,
        "source_corridor_expanded_px": 0.0,
        "source_corridor_crossings_removed": 0,
        "source_corridor_bends_removed": 0,
    }
    pre_corridor_document = _clone_layout_geometry(document)
    pre_corridor_assessment = accepted_assessment
    corridor_blockers: Counter[str] = Counter()
    # A move can expose a later physical facility to a newly opened corridor.
    # Rebuild the facility-edge job set after every improving pass.  Each
    # accepted move strictly lowers the finite lexicographic quality vector,
    # so convergence needs no diagram-size cutoff.
    corridor_search_allowed = precise_root_search_allowed
    if corridor_search_allowed:
        while True:
            document, corridor_report = _open_root_facility_corridors(
                document,
                nodes,
                logical_edges,
                profile,
                accepted_assessment=accepted_assessment,
                include_assessment=True,
            )
            accepted_assessment = corridor_report.pop("_accepted_assessment")
            corridor_blockers.update(
                corridor_report.pop("source_corridor_blockers")
            )
            for key in corridor_totals:
                corridor_totals[key] += corridor_report[key]
            corridor_moves = corridor_report["source_corridor_moves"]
            document, followup_anchor_report = _relocate_root_rendering_anchors(
                document,
                nodes,
                logical_edges,
                profile,
                # The corridor owner evaluates suffix translations with
                # incrementally reused hard metrics.  Rebuild the complete
                # baseline before handing coordinates back to the anchor
                # owner; otherwise a valid move newly exposed by the corridor
                # can be compared with a stale route/coordinate cache.
                accepted_assessment=None,
                include_assessment=True,
                continuous_physical_search=True,
            )
            accepted_assessment = followup_anchor_report.pop(
                "_accepted_assessment"
            )
            anchor_blockers.update(
                followup_anchor_report["source_anchor_relocation_blockers"]
            )
            for key in anchor_numeric_keys:
                anchor_totals[key] += followup_anchor_report[key]
            if (
                corridor_moves == 0
                and followup_anchor_report["source_anchor_column_moves"] == 0
            ):
                break
    else:
        corridor_blockers["topology-work-budget"] = 1
    corridor_totals["source_corridor_expanded_px"] = round(
        corridor_totals["source_corridor_expanded_px"], 3
    )
    corridor_totals["source_corridor_blockers"] = dict(
        sorted(corridor_blockers.items())
    )
    anchor_totals["source_anchor_length_saved_px"] = round(
        anchor_totals["source_anchor_length_saved_px"], 3
    )
    anchor_totals["source_anchor_relocation_blockers"] = dict(
        sorted(anchor_blockers.items())
    )
    report["selection"].update(anchor_totals)
    report["selection"].update(corridor_totals)
    report["selection"]["source_corridor_search_allowed"] = (
        corridor_search_allowed
    )
    document, tree_report = _normalize_fanout_routes_as_trees(
        document,
        nodes,
        logical_edges,
        route_clearance=profile.route_clearance,
        accepted_assessment=accepted_assessment,
    )
    if tree_report["fanout_residual_logical_cycle_rank"] > 0:
        fallback_document, fallback_tree_report = (
            _normalize_fanout_routes_as_trees(
                pre_corridor_document,
                nodes,
                logical_edges,
                route_clearance=profile.route_clearance,
                accepted_assessment=pre_corridor_assessment,
            )
        )
        if (
            fallback_tree_report["fanout_residual_logical_cycle_rank"]
            < tree_report["fanout_residual_logical_cycle_rank"]
        ):
            document = fallback_document
            tree_report = fallback_tree_report
            report["selection"]["source_corridor_rollback_cycle_rank"] = 1
            for key in (
                "source_corridor_moves",
                "source_corridor_retired_facilities",
                "source_corridor_expanded_px",
                "source_corridor_crossings_removed",
                "source_corridor_bends_removed",
            ):
                report["selection"][key] = 0
            for key, value in pre_corridor_anchor_totals.items():
                report["selection"][key] = value
        else:
            report["selection"]["source_corridor_rollback_cycle_rank"] = 0
    else:
        report["selection"]["source_corridor_rollback_cycle_rank"] = 0
    accepted_assessment = tree_report.pop("_accepted_assessment")
    report["selection"].update(tree_report)
    report["selection"]["source_rendering_replicas"] = (
        len(document.vertices) - len(nodes)
    )
    refined = assess_layout(
        document,
        logical_edges,
        0.0,
        include_routing_statistics=include_statistics,
        reuse_hard_metrics=accepted_assessment,
    )
    refined_selection = {
        "source_crossing_points": refined["source_crossing_points"],
        "route_overlaps": refined["ambiguous_overlaps"],
        "bends_total": refined["bends_total"],
        "visible_layout_area": refined["area"],
    }
    if include_statistics:
        refined_selection["routing_statistics"] = refined["routing_statistics"]
    report["selection"].update(refined_selection)
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
