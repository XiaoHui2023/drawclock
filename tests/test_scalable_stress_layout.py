from __future__ import annotations

import time
from pathlib import Path

import pytest

from auto_layout import _ranks, build_logical_edges, load_clock_tree, resolve_nodes
from drawio_library import load_library_shapes
from elk_layout import generate_elk_layout, select_layout_plan
from auto_layout import LogicalEdge
from layout_quality import inspect_layout_quality
from scripts.build_stress_examples import build_dual_from_reuse


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
