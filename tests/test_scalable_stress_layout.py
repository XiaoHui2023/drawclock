from __future__ import annotations

import copy
import time
from pathlib import Path

import pytest

from auto_layout import _ranks, build_logical_edges, load_clock_tree, resolve_nodes
from drawio_library import load_library_shapes
from elk_layout import generate_elk_layout, select_layout_plan
from auto_layout import LogicalEdge
from layout_quality import inspect_layout_quality
from scripts.build_stress_examples import build_dual_from_reuse
from scripts.build_stress_examples import build_adversarial_weave
from scripts.build_stress_examples import build_multi_from_clusters
from scripts.build_stress_examples import build_terminal_fanout_crossing
from scripts.build_stress_examples import build_asymmetric_merge_columns
from scripts.build_stress_examples import build_dispersed_root_fanout
from scripts.build_stress_examples import build_asymmetric_merge_route_bulge
from drawio_ports import abs_port_xy, infer_port_from_attachment


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
EXAMPLES = ROOT / "example" / "auto-layout"


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
        ("11-stress-4096-clocks", 4096, 8326, 10372, 20.0),
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
    assert len(document.vertices) == node_count
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
        (128, 4, True, 512),
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
    config = build_dispersed_root_fanout()
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    vertices = {vertex.name: vertex for vertex in document.vertices}
    root = vertices["wide_root"]
    wide_targets = [
        vertex for name, vertex in vertices.items() if name.startswith("wide_gate_")
    ]
    root_axis = abs_port_xy(
        root.x, root.y, root.width, root.height,
        root.style, root.drawclock_type, "right",
    )[1]
    target_axes = []
    for target in wide_targets:
        edge = next(
            edge for edge in document.edges
            if edge.target_id == target.cell_id and edge.source_id == root.cell_id
        )
        port = infer_port_from_attachment(target.style, edge.style, end="entry")
        assert port is not None
        target_axes.append(abs_port_xy(
            target.x, target.y, target.width, target.height,
            target.style, target.drawclock_type, port,
        )[1])

    assert quality["passed"] is True
    assert report["selection"]["boundary_placed_roots"] >= 1
    assert abs(root_axis - min(target_axes)) <= 0.02
    assert quality["readability"]["fragmented_fanout_sources"] == {}
    assert quality["readability"]["root_consumer_interleavings"]["wide_root"] == 0


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


def test_quality_gate_rejects_unused_inter_rank_whitespace() -> None:
    config = build_dual_from_reuse(4)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges)
    widened = copy.deepcopy(document)
    boundary = min(
        vertex.x for vertex in widened.vertices if ranks[vertex.name] == 2
    )
    for vertex in widened.vertices:
        if ranks[vertex.name] >= 2:
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
