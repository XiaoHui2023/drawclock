from __future__ import annotations

import copy
import time
from pathlib import Path

from auto_layout import build_logical_edges, load_clock_tree, resolve_nodes
from drawio_library import load_library_shapes
from elk_layout import (
    _logical_fanout_cycle_count,
    _regular_fanout_array_roots,
    _shared_fanout_bus_roots,
    generate_elk_layout,
)
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


def test_same_source_port_uses_one_vertical_distribution_trunk() -> None:
    config, document, _, quality = _generate("02-branch-tree")

    assert quality["readability"]["fragmented_fanout_sources"] == {}
    assert quality["line_integrity"]["ambiguous_overlaps"] == []
    assert quality["passed"] is True


def _two_public_root_mux_array(rows: int = 4):
    """Return repeated two-input mux rows with two reusable root networks."""
    config = {
        "public_from": {"kind": "from"},
        "public_source": {"kind": "source"},
    }
    for index in range(rows):
        suffix = f"{index:02d}"
        from_gate = f"from_gate_{suffix}"
        source_gate = f"source_gate_{suffix}"
        mux = f"mux_{suffix}"
        config[from_gate] = {"kind": "gate", "source": "public_from"}
        config[source_gate] = {"kind": "gate", "source": "public_source"}
        config[mux] = {
            "kind": "mux2",
            "source": {"0": from_gate, "1": source_gate},
        }
        config[f"clock_{suffix}"] = {"kind": "clock", "source": mux}
    return config


def test_two_public_root_mux_array_keeps_a_bus_for_each_root() -> None:
    """Two shared mux inputs are two buses, not one bus plus row aliases."""
    config = _two_public_root_mux_array()
    nodes = resolve_nodes(
        config, load_library_shapes(LIBRARY), {}, library_path=LIBRARY
    )
    logical_edges = build_logical_edges(config, nodes, LIBRARY)

    assert _regular_fanout_array_roots(nodes, logical_edges) == {
        "public_from", "public_source"
    }
    assert _shared_fanout_bus_roots(nodes, logical_edges) >= {
        "public_from", "public_source"
    }

    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    for root in ("public_from", "public_source"):
        facilities = [
            vertex for vertex in document.vertices
            if (vertex.logical_name or vertex.name) == root
        ]
        root_edges = [
            edge for edge in document.edges
            if edge.source_id == facilities[0].cell_id
        ]
        assert len(facilities) == 1
        assert len(root_edges) == 4


def test_fanout_cycle_count_decomposes_by_source_port_network() -> None:
    config = _two_public_root_mux_array()
    nodes = resolve_nodes(
        config, load_library_shapes(LIBRARY), {}, library_path=LIBRARY
    )
    logical_edges = build_logical_edges(config, nodes, LIBRARY)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    source_nets = {
        (edge.source, edge.source_port) for edge in logical_edges
    }

    global_count = _logical_fanout_cycle_count(document, logical_edges)
    decomposed_count = sum(
        _logical_fanout_cycle_count(
            document, logical_edges, source_nets={source_net},
        )
        for source_net in source_nets
    )

    assert decomposed_count == global_count


def test_similar_muxes_share_a_natural_column_with_asymmetric_inputs() -> None:
    """Repeated mux landmarks align despite unequal input-chain depths."""
    config = {
        "public_from": {"kind": "from"},
        "public_source": {"kind": "source"},
    }
    for index in range(5):
        suffix = f"{index:02d}"
        from_gate = f"from_gate_{suffix}"
        source_gate = f"source_gate_{suffix}"
        source_div = f"source_div_{suffix}"
        mux = f"mux_{suffix}"
        config[from_gate] = {"kind": "gate", "source": "public_from"}
        config[source_gate] = {
            "kind": "gate", "source": "public_source",
        }
        config[source_div] = {"kind": "div", "source": source_gate}
        config[mux] = {
            "kind": "mux2",
            "source": {"0": from_gate, "1": source_div},
        }
        config[f"clock_{suffix}"] = {"kind": "clock", "source": mux}

    # Natural alignment must not depend on declaration order or a user hint.
    config = dict(reversed(config.items()))
    assert all("layout_column" not in item for item in config.values())
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    muxes = [
        vertex for vertex in document.vertices if vertex.name.startswith("mux_")
    ]
    quality = inspect_layout_quality(
        config,
        document,
        library_path=LIBRARY,
        grid=0.0001,
        tolerance=0.01,
    )

    assert len(muxes) == 5
    assert len({round(vertex.x, 6) for vertex in muxes}) == 1
    assert quality["passed"] is True


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
        if (vertices[edge.source_id].logical_name or vertices[edge.source_id].name) == "src"
        and (vertices[edge.target_id].logical_name or vertices[edge.target_id].name) == "sel"
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
