from __future__ import annotations

import copy
import time
from collections import Counter
from pathlib import Path

import pytest

from auto_layout import (
    PROFILES,
    _layout_column_groups,
    _ranks,
    build_logical_edges,
    load_clock_tree,
    resolve_nodes,
)
from drawio_library import load_library_shapes
from elk_layout import (
    _replicate_dispersed_roots,
    generate_elk_layout,
    select_layout_plan,
)
from auto_layout import LogicalEdge
from layout_quality import inspect_layout_quality
from scripts.build_stress_examples import build_dual_from_reuse
from scripts.build_stress_examples import build_adversarial_weave
from scripts.build_stress_examples import build_multi_from_clusters
from scripts.build_stress_examples import build_terminal_fanout_crossing
from scripts.build_stress_examples import build_asymmetric_merge_columns
from scripts.build_stress_examples import build_dispersed_root_fanout
from scripts.build_stress_examples import build_asymmetric_merge_route_bulge
from drawio_ports import abs_port_xy, edge_attachment, infer_port_from_attachment
from drawio_layout import layout_from_dict, layout_to_dict


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock"
EXAMPLES = ROOT / "example" / "auto-layout"


def _forced_dispersed_root_layout(config):
    """Create a true distant-band artifact before testing root facilities."""
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    logical_edges = build_logical_edges(config, nodes, LIBRARY)
    moved_ids = set()
    for vertex in document.vertices:
        if "_bottom_" in vertex.name:
            vertex.y += 5000.0
            moved_ids.add(vertex.cell_id)
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    for index, logical in enumerate(logical_edges, 1):
        edge = next(edge for edge in document.edges if edge.cell_id == f"e{index}")
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
        if edge.source_id in moved_ids and edge.target_id in moved_ids:
            edge.waypoints = tuple((x, y + 5000.0) for x, y in edge.waypoints)
        elif edge.source_id in moved_ids or edge.target_id in moved_ids:
            lane_x = (start[0] + end[0]) / 2.0
            edge.waypoints = ((lane_x, start[1]), (lane_x, end[1]))
    return _replicate_dispersed_roots(
        document, nodes, logical_edges, PROFILES["readable"]
    )


def _minimal_dispersed_config(root_kind="from"):
    return {
        "wide_root": {"kind": root_kind},
        "wide_gate_top_0": {"kind": "gate", "source": "wide_root"},
        "wide_clock_top_0": {"kind": "clock", "source": "wide_gate_top_0"},
        "wide_gate_top_1": {"kind": "gate", "source": "wide_root"},
        "wide_clock_top_1": {"kind": "clock", "source": "wide_gate_top_1"},
        "wide_gate_bottom_0": {"kind": "gate", "source": "wide_root"},
        "wide_clock_bottom_0": {"kind": "clock", "source": "wide_gate_bottom_0"},
    }


def test_strategy_depends_on_structure_not_node_count() -> None:
    small_star_nodes = {f"n{i}": None for i in range(20)}
    small_star_edges = [
        LogicalEdge("n0", f"n{i}", "right", "left") for i in range(1, 20)
    ]
    large_chain_nodes = {f"n{i}": None for i in range(2500)}
    large_chain_edges = [
        LogicalEdge(f"n{i}", f"n{i + 1}", "right", "left")
        for i in range(2499)
    ]
    assert select_layout_plan(small_star_nodes, small_star_edges).mode == "domain"
    assert select_layout_plan(large_chain_nodes, large_chain_edges).mode == "quality"


@pytest.mark.parametrize(
    ("name", "clock_count", "node_count", "edge_count", "budget_seconds"),
    [
        ("09-stress-1024-clocks", 1024, 2086, 2596, 5.0),
        ("10-stress-2048-clocks", 2048, 4166, 5188, 10.0),
        ("11-stress-4096-clocks", 4096, 8326, 10372, 30.0),
    ],
)
def test_scalable_stress_generation_is_linear_and_complete(
    name: str,
    clock_count: int,
    node_count: int,
    edge_count: int,
    budget_seconds: float,
) -> None:
    config = load_clock_tree(EXAMPLES / f"{name}.json")
    started = time.perf_counter()
    document, report = generate_elk_layout(
        config,
        library_path=LIBRARY,
    )
    elapsed = time.perf_counter() - started
    assert report["engine"] == "constraint-layered"
    assert sum(item.get("kind") == "clock" for item in config.values()) == clock_count
    # Rendering-only aliases may repeat a zero-indegree logical source near a
    # distant consumer cluster.  They must not change the logical graph size.
    assert len({vertex.logical_name or vertex.name for vertex in document.vertices}) == node_count
    assert (
        len(document.vertices) - node_count
        == report["selection"]["source_rendering_replicas"]
    )
    assert len(document.edges) == edge_count
    assert elapsed < budget_seconds


def test_scalable_1024_hard_geometry_gate() -> None:
    name = "09-stress-1024-clocks"
    config = load_clock_tree(EXAMPLES / f"{name}.json")
    document, _ = generate_elk_layout(
        config,
        library_path=LIBRARY,
    )
    quality = inspect_layout_quality(
        config,
        document,
        library_path=LIBRARY,
        grid=0.0001,
        tolerance=0.01,
    )
    line = quality["line_integrity"]
    assert quality["passed"] is True
    assert quality["alignment"]["port_alignment_error_max_px"] == 0
    assert line["edge_node_intersections"] == []
    assert line["ambiguous_overlaps"] == []
    assert line["non_orthogonal_segments"] == []


def test_latest_feasible_layers_move_shorter_source_inward() -> None:
    config = build_dual_from_reuse(4)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges)

    assert ranks["from_a"] == 0
    assert ranks["from_b"] == 1
    assert ranks["gate_b_00"] + 1 == ranks["sel_00"]
    assert len({ranks[name] for name, item in config.items() if item["kind"] == "clock"}) == 1


@pytest.mark.parametrize("reverse_input", [False, True])
def test_layout_column_aligns_different_branch_depths(
    reverse_input: bool,
) -> None:
    config = load_clock_tree(EXAMPLES / "21-layout-column-preference.json")
    if reverse_input:
        config = dict(reversed(config.items()))
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    selected = ["sel_00", "sel_01", "sel_02"]

    without_preference = copy.deepcopy(config)
    for item in without_preference.values():
        item.pop("layout_column", None)
    plain_nodes = resolve_nodes(
        without_preference, shapes, {}, library_path=LIBRARY
    )
    plain_edges = build_logical_edges(without_preference, plain_nodes, LIBRARY)
    plain_ranks = _ranks(plain_nodes, plain_edges)
    assert len({plain_ranks[name] for name in selected}) == 3

    ranks = _ranks(nodes, edges, _layout_column_groups(config))
    assert len({ranks[name] for name in selected}) == 1
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    x_by_name = {vertex.name: vertex.x for vertex in document.vertices}
    assert len({x_by_name[name] for name in selected}) == 1
    assert all(
        "layout_column" not in vertex.object_attrs
        for vertex in document.vertices
    )
    assert report["selection"]["layout_column_groups"] == 3
    assert report["selection"]["layout_column_aligned"] == 3
    assert report["selection"]["layout_column_order_violations"] == 0
    assert report["selection"]["layout_column_max_span"] == 0

    grouped_names = {
        10: ["root_a", "root_b", "root_c", "root_d"],
        20: selected,
        30: ["clk_00", "clk_01", "clk_02"],
    }
    group_x = {
        level: {x_by_name[name] for name in names}
        for level, names in grouped_names.items()
    }
    assert all(len(xs) == 1 for xs in group_x.values())
    assert next(iter(group_x[10])) < next(iter(group_x[20]))
    assert next(iter(group_x[20])) < next(iter(group_x[30]))

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert quality["passed"] is True
    assert quality["alignment"]["layout_column_misalignments"] == []
    assert quality["alignment"]["layout_column_order_violations"] == []


def test_layout_column_quality_gate_rejects_shifted_member() -> None:
    config = load_clock_tree(EXAMPLES / "21-layout-column-preference.json")
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shifted = copy.deepcopy(document)
    next(vertex for vertex in shifted.vertices if vertex.name == "sel_01").x += 20
    quality = inspect_layout_quality(
        config, shifted, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert quality["passed"] is False
    assert "layout-column-misalignment" in quality["hard_failures"]
    assert quality["alignment"]["layout_column_misalignments"] == [{
        "level": 20,
        "nodes": ["sel_00", "sel_01", "sel_02"],
        "spread_px": 20.0,
    }]


def test_layout_column_quality_gate_rejects_reversed_numeric_order() -> None:
    config = load_clock_tree(EXAMPLES / "21-layout-column-preference.json")
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shifted = copy.deepcopy(document)
    roots = [
        vertex for vertex in shifted.vertices
        if vertex.name in {"root_a", "root_b", "root_c", "root_d"}
    ]
    mux_x = next(
        vertex.x for vertex in shifted.vertices if vertex.name == "sel_00"
    )
    for vertex in roots:
        vertex.x = mux_x + 20
    quality = inspect_layout_quality(
        config, shifted, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert quality["passed"] is False
    assert "layout-column-order" in quality["hard_failures"]
    assert quality["alignment"]["layout_column_order_violations"][0][
        "left_level"
    ] == 10
    assert quality["alignment"]["layout_column_order_violations"][0][
        "right_level"
    ] == 20


def test_layout_column_does_not_collapse_causal_nodes() -> None:
    config = {
        "root": {"kind": "from"},
        "first": {
            "kind": "gate", "layout_column": 20, "source": "root",
        },
        "second": {
            "kind": "div", "layout_column": 20, "source": "first",
        },
        "clock": {"kind": "clock", "source": "second"},
    }
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges, _layout_column_groups(config))
    assert ranks["first"] < ranks["second"]

    document, report = generate_elk_layout(config, library_path=LIBRARY)
    assert report["selection"]["layout_column_groups"] == 1
    assert report["selection"]["layout_column_aligned"] == 0
    assert report["selection"]["layout_column_order_violations"] == 0
    assert report["selection"]["layout_column_max_span"] == 1
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert quality["passed"] is True


def test_layout_column_is_independent_of_component_kind() -> None:
    config = {
        "root_a": {"kind": "from"},
        "preferred_gate": {
            "kind": "gate", "layout_column": 7, "source": "root_a",
        },
        "cell_a": {"kind": "cell", "source": "preferred_gate"},
        "clock_a": {"kind": "clock", "source": "cell_a"},
        "root_b": {"kind": "from"},
        "gate_b": {"kind": "gate", "source": "root_b"},
        "preferred_div": {
            "kind": "div", "layout_column": 7, "source": "gate_b",
        },
        "clock_b": {"kind": "clock", "source": "preferred_div"},
    }
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    x_by_name = {vertex.name: vertex.x for vertex in document.vertices}
    assert x_by_name["preferred_gate"] == x_by_name["preferred_div"]
    assert report["selection"]["layout_column_aligned"] == 1

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert quality["passed"] is True
    assert quality["alignment"]["layout_column_misalignments"] == []


def test_layout_column_numeric_distance_does_not_reserve_empty_columns() -> None:
    config = {
        "root": {"kind": "from", "layout_column": 10},
        "gate": {"kind": "gate", "source": "root"},
        "clock": {"kind": "clock", "layout_column": 100, "source": "gate"},
    }
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges, _layout_column_groups(config))

    assert ranks == {"root": 0, "gate": 1, "clock": 2}


def test_layout_column_4096_unique_levels_stays_linear() -> None:
    count = 4096
    names = [f"node_{index:04d}" for index in range(count)]
    edges = [
        LogicalEdge(names[index], names[index + 1], "out", "in")
        for index in range(count - 1)
    ]
    columns = {index * 10: [name] for index, name in enumerate(names)}

    started = time.perf_counter()
    ranks = _ranks(names, edges, columns)
    elapsed = time.perf_counter() - started

    assert ranks[names[0]] == 0
    assert ranks[names[-1]] == count - 1
    assert elapsed < 1.0


def test_layout_column_reverse_topology_remains_forward() -> None:
    config = {
        "root": {"kind": "from", "layout_column": 30},
        "gate": {"kind": "gate", "layout_column": 10, "source": "root"},
        "clock": {"kind": "clock", "source": "gate"},
    }
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges, _layout_column_groups(config))
    assert ranks["root"] < ranks["gate"]

    document, report = generate_elk_layout(config, library_path=LIBRARY)
    assert report["selection"]["layout_column_order_violations"] == 1
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert quality["passed"] is True


def test_dual_from_reuse_has_no_avoidable_outer_detours() -> None:
    config = build_dual_from_reuse(32)
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    positions = {vertex.name: vertex.x for vertex in document.vertices}

    assert report["engine"] == "constraint-layered"
    assert positions["from_b"] > positions["from_a"]
    assert quality["line_integrity"]["avoidable_outer_detours"] == []
    assert quality["readability"]["route_inefficiency_max"] == 1.0
    assert quality["readability"]["chain_axis_dogleg_edges"] == []
    assert quality["readability"]["local_axis_offset_max_px"] <= 8.5
    assert quality["passed"] is True


@pytest.mark.parametrize(
    ("domains", "clocks_per_domain", "long_names", "clock_count"),
    [
        (16, 2, True, 32),
        (64, 2, False, 128),
        (64, 8, True, 512),
    ],
)
def test_adversarial_weave_quality_corpus(
    domains: int,
    clocks_per_domain: int,
    long_names: bool,
    clock_count: int,
) -> None:
    config = build_adversarial_weave(
        domains,
        clocks_per_domain=clocks_per_domain,
        long_names=long_names,
    )
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config,
        document,
        library_path=LIBRARY,
        grid=0.0001,
        tolerance=0.01,
        joint_coordinate_oracle=clock_count < 512,
    )
    line = quality["line_integrity"]

    assert sum(item.get("kind") == "clock" for item in config.values()) == clock_count
    assert quality["passed"] is True
    assert line["edge_node_intersections"] == []
    assert line["edge_label_intersections"] == []
    assert line["source_lead_inside_visual"] == []
    assert line["target_lead_inside_visual"] == []
    assert line["avoidable_bend_edges"] == []
    assert line["avoidable_crossing_edges"] == []
    assert line["bends_max_per_edge"] <= 4


def test_multiple_source_placement_selects_best_valid_candidate() -> None:
    config = build_adversarial_weave(64, clocks_per_domain=2, long_names=False)
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    candidates = report["selection"]["source_position_candidates"]
    valid = [
        item for item in candidates
        if item["route_overlaps"] == 0
    ]

    assert quality["passed"] is True
    assert valid
    assert report["selection"]["source_crossing_points"] == min(
        item["source_crossing_points"] for item in valid
    )
    assert quality["line_integrity"]["source_induced_crossing_points"] == report["selection"]["source_crossing_points"]


def test_multi_from_roots_are_distributed_by_their_consumers() -> None:
    config = build_multi_from_clusters()
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    source_tops = [
        vertex.y for vertex in document.vertices if vertex.name.startswith("from_")
    ]

    assert quality["passed"] is True
    assert report["selection"]["source_position_mode"] == "adaptive-span"
    assert quality["readability"]["fanout_trunk_clusters"] == {}
    assert quality["readability"]["fragmented_fanout_sources"] == {}
    assert len(set(source_tops)) == 4
    assert max(source_tops) - min(source_tops) > max(
        vertex.height
        for vertex in document.vertices
        if vertex.name.startswith("from_")
    )


def test_terminal_fanout_order_removes_avoidable_last_gap_crossing() -> None:
    config = build_terminal_fanout_crossing()
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert quality["passed"] is True
    assert quality["layout_order"]["terminal_order_inversions"] == 0
    assert quality["layout_order"]["avoidable_terminal_crossings"] == 0
    assert quality["line_integrity"]["distinct_crossing_points"] == 0
    assert report["selection"]["bends_total"] <= 8


def test_equivalent_merge_cohorts_share_one_constraint_derived_column() -> None:
    config = build_asymmetric_merge_columns()
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    merge_names = [name for name in config if name.startswith("merge_")]
    merge_x = {
        round(vertex.x, 6) for vertex in document.vertices if vertex.name in merge_names
    }

    assert len({ranks[name] for name in merge_names}) == 1
    assert len(merge_x) == 1
    assert quality["passed"] is True


def test_dispersed_root_uses_top_entry_and_justified_local_trunks() -> None:
    config = _minimal_dispersed_config()
    document, report = _forced_dispersed_root_layout(config)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    vertices = {vertex.name: vertex for vertex in document.vertices}
    root_anchors = [
        vertex for vertex in document.vertices
        if (vertex.logical_name or vertex.name) == "wide_root"
    ]
    wide_targets = [
        vertex for name, vertex in vertices.items() if name.startswith("wide_gate_")
    ]
    root_anchor_ids = {vertex.cell_id for vertex in root_anchors}
    used_anchor_ids = set()
    for target in wide_targets:
        edge = next(
            edge for edge in document.edges
            if edge.target_id == target.cell_id and edge.source_id in root_anchor_ids
        )
        used_anchor_ids.add(edge.source_id)

    assert quality["passed"] is True
    assert report["source_rendering_replicas"] >= 1
    assert report["source_replica_length_saved_px"] > 0
    assert used_anchor_ids == root_anchor_ids
    assert quality["alignment"]["invalid_rendering_replicas"] == []
    assert quality["alignment"]["unused_rendering_replicas"] == []
    assert quality["readability"]["fragmented_fanout_sources"] == {}
    assert quality["readability"]["root_consumer_interleavings"]["wide_root"] == 0


def test_root_replication_is_zero_indegree_driven_not_component_kind() -> None:
    config = _minimal_dispersed_config("gate")
    document, _ = _forced_dispersed_root_layout(config)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    anchors = [
        vertex for vertex in document.vertices
        if (vertex.logical_name or vertex.name) == "wide_root"
    ]

    assert len(anchors) > 1
    assert {vertex.drawclock_type for vertex in anchors} == {"gate"}
    assert quality["passed"] is True


def test_rendering_replica_identity_survives_layout_serialization() -> None:
    config = _minimal_dispersed_config()
    document, _ = _forced_dispersed_root_layout(config)
    restored = layout_from_dict(layout_to_dict(document))

    assert layout_to_dict(restored) == layout_to_dict(document)
    assert any(vertex.logical_name for vertex in restored.vertices)


def test_replica_quality_gate_fault_injection_covers_graph_identity() -> None:
    config = _minimal_dispersed_config()
    document, _ = _forced_dispersed_root_layout(config)

    non_root = copy.deepcopy(document)
    gate = next(vertex for vertex in non_root.vertices if vertex.name.startswith("wide_gate_"))
    invalid = copy.deepcopy(gate)
    invalid.name += "__invalid_replica"
    invalid.cell_id += "_invalid"
    invalid.logical_name = gate.name
    non_root.vertices.append(invalid)
    invalid_quality = inspect_layout_quality(
        config, non_root, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert invalid.name in invalid_quality["alignment"]["invalid_rendering_replicas"]
    assert invalid_quality["passed"] is False

    unused = copy.deepcopy(document)
    root = next(vertex for vertex in unused.vertices if vertex.name == "wide_root")
    orphan = copy.copy(root)
    orphan.name = "wide_root__unused"
    orphan.cell_id = "wide_root_unused"
    orphan.logical_name = "wide_root"
    unused.vertices.append(orphan)
    unused_quality = inspect_layout_quality(
        config, unused, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert orphan.name in unused_quality["alignment"]["unused_rendering_replicas"]
    assert unused_quality["passed"] is False

    wrong_identity = copy.deepcopy(document)
    replica = next(vertex for vertex in wrong_identity.vertices if vertex.logical_name == "wide_root")
    replica.width += 1.0
    identity_quality = inspect_layout_quality(
        config, wrong_identity, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert replica.name in identity_quality["alignment"]["replica_identity_errors"]
    assert identity_quality["passed"] is False

    missing_edge = copy.deepcopy(document)
    missing_edge.edges.pop()
    edge_quality = inspect_layout_quality(
        config, missing_edge, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert edge_quality["line_integrity"]["missing_edges"]
    assert edge_quality["passed"] is False

    redundant = copy.deepcopy(document)
    outgoing = Counter(edge.source_id for edge in redundant.edges)
    anchor = next(
        vertex for vertex in redundant.vertices
        if (vertex.logical_name or vertex.name) == "wide_root"
        and outgoing[vertex.cell_id] >= 2
    )
    duplicate = copy.copy(anchor)
    duplicate.name = "wide_root__redundant"
    duplicate.cell_id = "wide_root_redundant"
    duplicate.logical_name = "wide_root"
    redundant.vertices.append(duplicate)
    next(edge for edge in redundant.edges if edge.source_id == anchor.cell_id).source_id = duplicate.cell_id
    redundant_quality = inspect_layout_quality(
        config, redundant, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    assert redundant_quality["alignment"]["avoidable_source_replicas"]
    assert redundant_quality["passed"] is False


@pytest.mark.parametrize("long_branch", ["a", "b"])
def test_asymmetric_merge_inputs_follow_fixed_port_order_without_crossing(
    long_branch: str,
) -> None:
    config = build_asymmetric_merge_route_bulge(long_branch=long_branch)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert quality["passed"] is True
    assert quality["line_integrity"]["avoidable_local_merge_input_crossings"] == []
    assert quality["line_integrity"]["avoidable_merge_input_detours"] == []
    assert quality["line_integrity"]["avoidable_joint_coordinate_bend_edges"] == []
    tap_edge = next(
        edge for edge in document.edges
        if next(
            vertex for vertex in document.vertices
            if vertex.cell_id == edge.target_id
        ).name.endswith("_tap")
    )
    assert tap_edge.waypoints == ()
    assert tap_edge.cell_id not in quality["line_integrity"][
        "joint_coordinate_bend_tradeoffs"
    ]
    long_parent = f"div_{long_branch}"
    merge_edge = next(
        edge for edge in document.edges
        if next(
            vertex for vertex in document.vertices
            if vertex.cell_id == edge.source_id
        ).name == long_parent
        and next(
            vertex for vertex in document.vertices
            if vertex.cell_id == edge.target_id
        ).name == "sel"
    )
    assert merge_edge.waypoints == ()


def test_joint_coordinate_refinement_accepts_only_a_global_dominance() -> None:
    config = build_asymmetric_merge_route_bulge(long_branch="b")
    config["independent_floor_anchor"] = {"kind": "from"}
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert report["selection"]["leaf_continuation_row_moves"] == 1
    assert report["selection"]["leaf_continuation_bends_removed"] == 4
    assert report["selection"]["exclusive_chain_axis_moves"] == 1
    assert report["selection"]["exclusive_chain_bends_removed"] == 2
    assert report["selection"]["joint_coordinate_moves"] == 0
    assert quality["line_integrity"]["bends_total"] == 2
    assert quality["line_integrity"]["avoidable_joint_coordinate_bend_edges"] == []
    assert quality["passed"] is True


def test_quality_gate_rejects_movable_exclusive_chain_dogleg() -> None:
    config = build_asymmetric_merge_route_bulge(long_branch="b")
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    by_name = {vertex.name: vertex for vertex in document.vertices}
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    for name in ("from_b", "gate_b", "div_b"):
        by_name[name].y += 20.0
    edge = next(
        item for item in document.edges
        if by_id[item.source_id].name == "div_b"
        and by_id[item.target_id].name == "sel"
    )
    source = by_id[edge.source_id]
    target = by_id[edge.target_id]
    exit_xy = edge_attachment(edge.style, end="exit")
    entry_xy = edge_attachment(edge.style, end="entry")
    assert exit_xy is not None and entry_xy is not None
    start = (
        source.x + source.width * exit_xy[0],
        source.y + source.height * exit_xy[1],
    )
    end = (
        target.x + target.width * entry_xy[0],
        target.y + target.height * entry_xy[1],
    )
    channel = (start[0] + end[0]) / 2.0
    edge.waypoints = (
        (channel, start[1]),
        (channel, end[1]),
    )

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert quality["passed"] is False
    assert quality["line_integrity"][
        "avoidable_exclusive_chain_bend_edges"
    ] == [edge.cell_id]


@pytest.mark.parametrize("long_branch", ["a", "b"])
def test_exclusive_chain_axis_refinement_ignores_names_and_input_order(
    long_branch: str,
) -> None:
    original = build_asymmetric_merge_route_bulge(long_branch=long_branch)
    names = list(original)
    renamed = {
        name: f"device_{index:02d}_with_unrelated_name"
        for index, name in enumerate(names)
    }
    config: dict[str, dict[str, object]] = {}
    for name in reversed(names):
        item = copy.deepcopy(original[name])
        source = item.get("source")
        if isinstance(source, str):
            item["source"] = renamed[source]
        elif isinstance(source, dict):
            item["source"] = {
                port: renamed[parent]
                for port, parent in source.items()
            }
        config[renamed[name]] = item

    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    edge = next(
        item for item in document.edges
        if by_id[item.source_id].name == renamed[f"div_{long_branch}"]
        and by_id[item.target_id].name == renamed["sel"]
    )
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert edge.waypoints == ()
    assert quality["line_integrity"][
        "avoidable_exclusive_chain_bend_edges"
    ] == []
    assert quality["passed"] is True


def test_quality_gate_rejects_unused_inter_rank_whitespace() -> None:
    config = build_dual_from_reuse(4)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges)
    widened = copy.deepcopy(document)
    boundary = min(
        vertex.x
        for vertex in widened.vertices
        if ranks[vertex.logical_name or vertex.name] == 2
    )
    for vertex in widened.vertices:
        if ranks[vertex.logical_name or vertex.name] >= 2:
            vertex.x += 40
    for edge in widened.edges:
        edge.waypoints = tuple(
            (x + 40 if x >= boundary else x, y)
            for x, y in edge.waypoints
        )
    quality = inspect_layout_quality(
        config, widened, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert quality["layout_order"]["avoidable_inter_rank_gap_total_px"] >= 40
