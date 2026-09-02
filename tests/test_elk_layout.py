from __future__ import annotations

import copy
import time
import sys
from pathlib import Path

import pytest

import elk_layout
from auto_layout import load_clock_tree
from elk_layout import elk_layout_available, generate_elk_layout
from layout_quality import _points_for_edge, inspect_layout_quality
from scripts.build_stress_examples import build_asymmetric_merge_route_bulge


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock"
EXAMPLES = ROOT / "example" / "auto-layout"


def _generate(name: str):
    config = load_clock_tree(EXAMPLES / f"{name}.json")
    document, report = generate_elk_layout(
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
    return config, document, report, quality


def test_elk_runtime_discovers_bundled_node_and_module(
    tmp_path: Path, monkeypatch,
) -> None:
    runtime = tmp_path / "runtime"
    node = runtime / ("node/node.exe" if sys.platform == "win32" else "node/bin/node")
    script = runtime / "elk" / "elk_layout.mjs"
    bundled = runtime / "elk" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js"
    for path in (node, script, bundled):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    binary = tmp_path / ("drawclock.exe" if sys.platform == "win32" else "drawclock")
    binary.touch()
    monkeypatch.setattr(elk_layout.sys, "frozen", True, raising=False)
    monkeypatch.setattr(elk_layout.sys, "executable", str(binary))
    monkeypatch.setattr(elk_layout.shutil, "which", lambda _name: None)

    assert elk_layout._elk_runtime() == (str(node), script, runtime / "elk")


def test_elk_runtime_uses_original_staticx_program_path(
    tmp_path: Path, monkeypatch,
) -> None:
    installed = tmp_path / "installed"
    runtime = installed / "runtime"
    node = runtime / "node" / (
        "node.exe" if sys.platform == "win32" else "bin/node"
    )
    script = runtime / "elk" / "elk_layout.mjs"
    bundled = runtime / "elk" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js"
    for path in (node, script, bundled):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    monkeypatch.setenv("STATICX_PROG_PATH", str(installed / "drawclock"))
    monkeypatch.setattr(elk_layout.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        elk_layout.sys, "executable", str(tmp_path / "staticx-bundle" / "drawclock")
    )
    monkeypatch.setattr(elk_layout.shutil, "which", lambda _name: None)

    assert elk_layout._elk_runtime() == (str(node), script, runtime / "elk")


def test_elk_runtime_discovers_release_runtime_from_source(
    tmp_path: Path, monkeypatch,
) -> None:
    runtime = tmp_path / "runtime"
    node = runtime / ("node/node.exe" if sys.platform == "win32" else "node/bin/node")
    script = runtime / "elk" / "elk_layout.mjs"
    bundled = runtime / "elk" / "node_modules" / "elkjs" / "lib" / "elk.bundled.js"
    for path in (node, script, bundled):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    monkeypatch.setattr(elk_layout, "__file__", str(tmp_path / "src" / "elk_layout.py"))
    monkeypatch.setattr(elk_layout.sys, "frozen", False, raising=False)
    monkeypatch.setattr(elk_layout.shutil, "which", lambda _name: None)

    assert elk_layout._elk_runtime() == (str(node), script, runtime / "elk")


@pytest.mark.skipif(not elk_layout_available(), reason="ELK Node.js dependency is unavailable")
def test_elk_exact_ports_and_lines_are_deterministic() -> None:
    _, first, _, quality = _generate("06-simple-16-clocks")
    _, second, _, _ = _generate("06-simple-16-clocks")
    line = quality["line_integrity"]

    assert first == second
    assert quality["alignment"]["port_alignment_error_max_px"] == 0
    assert line["missing_edges"] == []
    assert line["extra_edges"] == []
    assert line["non_orthogonal_segments"] == []
    assert line["micro_segments"] == []
    assert line["source_lead_non_horizontal"] == []
    assert line["target_lead_non_horizontal"] == []
    assert line["edge_node_intersections"] == []
    assert line["ambiguous_overlaps"] == []


@pytest.mark.skipif(not elk_layout_available(), reason="ELK Node.js dependency is unavailable")
def test_same_source_port_uses_one_vertical_distribution_trunk() -> None:
    config, document, _, quality = _generate("02-branch-tree")

    assert quality["readability"]["fragmented_fanout_sources"] == {}
    assert quality["line_integrity"]["ambiguous_overlaps"] == []
    assert quality["passed"] is True


@pytest.mark.skipif(not elk_layout_available(), reason="ELK Node.js dependency is unavailable")
def test_grouped_sweep_matches_exact_pair_oracle() -> None:
    config = load_clock_tree(EXAMPLES / "06-simple-16-clocks.json")
    document, _ = generate_elk_layout(
        config,
        library_path=LIBRARY,
    )
    common = {
        "library_path": LIBRARY,
        "grid": 0.0001,
        "tolerance": 0.01,
    }
    grouped = inspect_layout_quality(config, document, **common)
    exact = inspect_layout_quality(
        config, document, exact_pair_oracle=True, **common
    )
    assert grouped["passed"] == exact["passed"]
    for key in (
        "distinct_crossing_points",
        "ambiguous_overlaps",
        "untreated_crossings",
    ):
        assert grouped["line_integrity"][key] == exact["line_integrity"][key]


@pytest.mark.skipif(not elk_layout_available(), reason="ELK Node.js dependency is unavailable")
def test_elk_512_clock_stress_budget_and_integrity() -> None:
    started = time.perf_counter()
    config, document, report, quality = _generate("08-stress-512-clocks")
    elapsed = time.perf_counter() - started
    line = quality["line_integrity"]

    assert sum(item.get("kind") == "clock" for item in config.values()) == 512
    logical_vertex_names = {vertex.logical_name or vertex.name for vertex in document.vertices}
    replica_count = report["selection"]["source_rendering_replicas"]
    assert len(logical_vertex_names) == 1046
    assert len(document.vertices) == 1046 + replica_count
    assert len(document.edges) == 1300
    assert report["engine"] == "constraint-layered"
    assert report["selection"]["basis"] == "graph-structure"
    assert report["selection"]["backbone_nodes"] > 0
    assert line["missing_edges"] == []
    assert line["extra_edges"] == []
    assert line["non_orthogonal_segments"] == []
    assert line["micro_segments"] == []
    assert line["source_lead_non_horizontal"] == []
    assert line["target_lead_non_horizontal"] == []
    assert line["edge_node_intersections"] == []
    assert line["ambiguous_overlaps"] == []
    assert elapsed < 30


def test_quality_rejects_avoidable_global_bottom_detour() -> None:
    config = {
        "src": {"kind": "from"},
        "gate": {"kind": "gate", "source": "src"},
        "div": {"kind": "div", "source": "gate"},
        "sel": {
            "kind": "mux2",
            "source": {"0": "div", "1": "src"},
        },
        "cell": {"kind": "cell", "source": "sel"},
        "clk": {"kind": "clock", "source": "cell"},
    }
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    vertices = {vertex.cell_id: vertex for vertex in document.vertices}
    bad_edge = next(
        edge for edge in document.edges
        if vertices[edge.source_id].name == "src"
        and vertices[edge.target_id].name == "sel"
    )
    points = _points_for_edge(
        bad_edge, vertices[bad_edge.source_id], vertices[bad_edge.target_id]
    )
    bottom = max(vertex.y + vertex.height for vertex in document.vertices) + 1000
    bad_edge.waypoints = (
        (points[0][0] + 20, points[0][1]),
        (points[0][0] + 20, bottom),
        (points[-1][0] - 20, bottom),
        (points[-1][0] - 20, points[-1][1]),
    )

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=10, tolerance=0.01
    )

    assert quality["passed"] is False
    assert quality["line_integrity"]["avoidable_outer_detours"] == [bad_edge.cell_id]


def _two_parallel_chains(*, long_name: bool = False):
    gate_a = (
        "gate_with_an_intentionally_very_long_instance_name_for_label_clearance"
        if long_name
        else "gate_a"
    )
    config = {
        "src_a": {"kind": "from"},
        gate_a: {"kind": "gate", "source": "src_a"},
        "clk_a": {"kind": "clock", "source": gate_a},
        "src_b": {"kind": "from"},
        "gate_b": {"kind": "gate", "source": "src_b"},
        "clk_b": {"kind": "clock", "source": "gate_b"},
    }
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    return config, document, gate_a


def test_quality_fault_injection_rejects_avoidable_bends_and_crossing() -> None:
    config, document, _ = _two_parallel_chains()
    vertices = {vertex.cell_id: vertex for vertex in document.vertices}
    by_name = {vertex.name: vertex for vertex in document.vertices}
    edge = next(
        edge
        for edge in document.edges
        if vertices[edge.source_id].name == "src_a"
        and vertices[edge.target_id].name == "gate_a"
    )
    points = _points_for_edge(
        edge, vertices[edge.source_id], vertices[edge.target_id]
    )
    start, end = points[0], points[-1]
    lower_y = _points_for_edge(
        next(
            item
            for item in document.edges
            if vertices[item.source_id].name == "src_b"
            and vertices[item.target_id].name == "gate_b"
        ),
        by_name["src_b"],
        by_name["gate_b"],
    )[0][1]
    detour_y = lower_y + 30
    edge.waypoints = (
        (start[0] + 20, start[1]),
        (start[0] + 20, detour_y),
        (end[0] - 20, detour_y),
        (end[0] - 20, end[1]),
    )

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=10, tolerance=0.01
    )
    line = quality["line_integrity"]

    assert quality["passed"] is False
    assert line["avoidable_bend_edges"] == [edge.cell_id]
    assert line["avoidable_crossing_edges"] == [edge.cell_id]
    assert line["zigzag_edges"] == [edge.cell_id]


def test_quality_fault_injection_rejects_clear_corridor_bend_without_crossing() -> None:
    """A needless dogleg must fail even when it crosses no other wire."""
    config, document, _ = _two_parallel_chains()
    vertices = {vertex.cell_id: vertex for vertex in document.vertices}
    edge = next(
        item
        for item in document.edges
        if vertices[item.source_id].name == "src_a"
        and vertices[item.target_id].name == "gate_a"
    )
    points = _points_for_edge(
        edge, vertices[edge.source_id], vertices[edge.target_id]
    )
    start, end = points[0], points[-1]
    detour_y = start[1] - 30.0
    edge.waypoints = (
        (start[0] + 20.0, start[1]),
        (start[0] + 20.0, detour_y),
        (end[0] - 20.0, detour_y),
        (end[0] - 20.0, end[1]),
    )

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=10, tolerance=0.01
    )
    line = quality["line_integrity"]

    assert quality["passed"] is False
    assert line["avoidable_bend_edges"] == [edge.cell_id]
    assert line["avoidable_crossing_edges"] == []
    assert line["zigzag_edges"] == [edge.cell_id]


def test_quality_fault_injection_rejects_two_bend_local_merge_crossing() -> None:
    config = build_asymmetric_merge_route_bulge()
    clean, _ = generate_elk_layout(config, library_path=LIBRARY)
    document = copy.deepcopy(clean)
    by_name = {vertex.name: vertex for vertex in document.vertices}
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    gate_a = by_name["gate_a"]
    div_b = by_name["div_b"]
    merge_edges = [
        edge for edge in document.edges if by_id[edge.target_id].name == "sel"
    ]
    merge_edges.sort(key=lambda edge: by_id[edge.source_id].name)
    clean_points = {
        by_id[edge.source_id].name: _points_for_edge(
            edge, by_id[edge.source_id], by_id[edge.target_id]
        )
        for edge in merge_edges
    }
    gate_axis = clean_points["gate_a"][0][1]
    div_axis = clean_points["div_b"][0][1]
    gate_a.y += clean_points["div_b"][-1][1] + 24 - gate_axis
    div_b.y += clean_points["gate_a"][-1][1] - 30 - div_axis
    starts_ends = [
        (
            edge,
            _points_for_edge(edge, by_id[edge.source_id], by_id[edge.target_id])[0],
            _points_for_edge(edge, by_id[edge.source_id], by_id[edge.target_id])[-1],
        )
        for edge in merge_edges
    ]
    first_channel = max(start[0] for _, start, _ in starts_ends) + 24
    for index, (edge, start, end) in enumerate(starts_ends):
        channel = first_channel + index * 10
        edge.waypoints = ((channel, start[1]), (channel, end[1]))

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=10, tolerance=0.01
    )
    expected_pair = [tuple(sorted(edge.cell_id for edge in merge_edges))]

    assert quality["passed"] is False
    assert quality["line_integrity"][
        "avoidable_local_merge_input_crossings"
    ] == expected_pair


def test_quality_fault_injection_rejects_vertical_departure_inside_source() -> None:
    config, document, _ = _two_parallel_chains()
    vertices = {vertex.cell_id: vertex for vertex in document.vertices}
    edge = next(
        edge
        for edge in document.edges
        if vertices[edge.source_id].name == "src_a"
        and vertices[edge.target_id].name == "gate_a"
    )
    points = _points_for_edge(
        edge, vertices[edge.source_id], vertices[edge.target_id]
    )
    edge.waypoints = (
        (points[0][0], points[0][1] + 20),
        (points[-1][0] - 20, points[0][1] + 20),
        (points[-1][0] - 20, points[-1][1]),
    )

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=10, tolerance=0.01
    )

    assert quality["passed"] is False
    assert quality["line_integrity"]["source_lead_inside_visual"] == [
        edge.cell_id
    ]


def test_quality_fault_injection_rejects_wire_through_label_overflow() -> None:
    config, document, long_gate = _two_parallel_chains(long_name=True)
    vertices = {vertex.cell_id: vertex for vertex in document.vertices}
    by_name = {vertex.name: vertex for vertex in document.vertices}
    edge = next(
        edge
        for edge in document.edges
        if vertices[edge.source_id].name == "src_b"
        and vertices[edge.target_id].name == "gate_b"
    )
    points = _points_for_edge(
        edge, vertices[edge.source_id], vertices[edge.target_id]
    )
    obstacle = by_name[long_gate]
    label_y = obstacle.y + obstacle.height - 2
    label_left_x = obstacle.x - 30
    edge.waypoints = (
        (label_left_x, points[0][1]),
        (label_left_x, label_y),
        (obstacle.x - 1, label_y),
        (obstacle.x - 1, points[-1][1]),
    )

    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=10, tolerance=0.01
    )

    assert quality["passed"] is False
    assert f"{edge.cell_id}->{long_gate}" in quality["line_integrity"][
        "edge_label_intersections"
    ]
