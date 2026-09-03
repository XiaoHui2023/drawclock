from __future__ import annotations

import copy
import itertools
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
    assess_layout,
)
from drawio_library import load_library_shapes
from elk_layout import (
    _optimal_source_anchor_partitions,
    _replicate_dispersed_roots,
    _relocate_root_rendering_anchors,
    _split_root_rendering_anchors_by_local_rows,
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
from scripts.build_stress_examples import build_single_source_rendering_alias
from scripts.build_stress_examples import build_middle_column_low_use_sources
from scripts.build_stress_examples import build_asymmetric_merge_route_bulge
from scripts.build_stress_examples import build_mixed_root_port_order_torture
from drawio_ports import abs_port_xy, edge_attachment, infer_port_from_attachment
from drawio_layout import layout_from_dict, layout_to_dict


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock"
EXAMPLES = ROOT / "example" / "auto-layout"


def _forced_dispersed_root_layout(config, offset=5000.0):
    """Create a true distant-band artifact before testing root facilities."""
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    logical_edges = build_logical_edges(config, nodes, LIBRARY)
    moved_ids = set()
    for vertex in document.vertices:
        if "_bottom_" in vertex.name:
            vertex.y += offset
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
            edge.waypoints = tuple((x, y + offset) for x, y in edge.waypoints)
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


def _forced_multiband_root_layout(
    band_count: int,
    *,
    band_gap: float = 500.0,
    source_has_parent: bool = False,
):
    config: dict[str, dict[str, str]] = {"root": {"kind": "from"}}
    fanout_source = "root"
    if source_has_parent:
        fanout_source = "fanout_source"
        config[fanout_source] = {"kind": "gate", "source": "root"}
    for band in range(band_count):
        gate = f"gate_band_{band}"
        config[gate] = {"kind": "gate", "source": fanout_source}
        config[f"clock_band_{band}"] = {"kind": "clock", "source": gate}
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    logical_edges = build_logical_edges(config, nodes, LIBRARY)
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    for band in range(band_count):
        for name in (f"gate_band_{band}", f"clock_band_{band}"):
            by_id[nodes[name].cell_id].y += band * band_gap
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
        if abs(start[1] - end[1]) <= 1e-6:
            edge.waypoints = ()
        else:
            lane_x = (start[0] + end[0]) / 2.0
            edge.waypoints = ((lane_x, start[1]), (lane_x, end[1]))
    laid_out, report = _replicate_dispersed_roots(
        document, nodes, logical_edges, PROFILES["readable"]
    )
    return config, laid_out, report


def test_source_partition_budget_triggers_just_after_three_visual_rows() -> None:
    row_pitch = 100.0
    assert _optimal_source_anchor_partitions(
        [(0.0, 1), (300.0, 2)],
        3 * row_pitch,
        row_axes=(100.0, 200.0),
    ) == [[1, 2]]
    assert _optimal_source_anchor_partitions(
        [(0.0, 1), (301.0, 2)],
        3 * row_pitch,
        row_axes=(100.0, 200.0, 300.0),
    ) == [[1], [2]]


def test_source_partition_keeps_local_row_and_replicates_four_rows_away() -> None:
    """A local consumer must not force a four-row source trunk."""
    row_pitch = 100.0
    assert _optimal_source_anchor_partitions(
        [(0.0, 1), (400.0, 2)],
        3 * row_pitch,
        row_axes=(0.0, 100.0, 200.0, 300.0, 400.0),
    ) == [[1], [2]]


def test_source_partition_supports_every_geometry_justified_band() -> None:
    """The general facility solver must not stop after two render anchors."""
    row_pitch = 100.0
    assert _optimal_source_anchor_partitions(
        [(0.0, 1), (400.0, 2), (800.0, 3), (1200.0, 4)],
        3 * row_pitch,
        row_axes=tuple(float(axis) for axis in range(0, 1201, 100)),
    ) == [[1], [2], [3], [4]]


def test_source_partition_is_order_and_identity_independent() -> None:
    samples = [(1200.0, 91), (400.0, 17), (0.0, 203), (800.0, 5)]
    assert _optimal_source_anchor_partitions(
        samples,
        300.0,
        row_axes=tuple(float(axis) for axis in range(0, 1201, 100)),
    ) == [[203], [17], [5], [91]]


def test_source_partition_does_not_duplicate_dense_local_fanout() -> None:
    assert _optimal_source_anchor_partitions(
        [(0.0, 1), (100.0, 2), (200.0, 3), (300.0, 4)],
        300.0,
        row_axes=(0.0, 100.0, 200.0, 300.0),
    ) == [[1, 2, 3, 4]]


def test_source_partition_gap_solver_matches_exhaustive_facility_optimum() -> None:
    """Independent small-state oracle for the closed-form partition solver."""
    fixed_cost = 300.0
    for gaps in itertools.product((100.0, 300.0, 301.0, 450.0), repeat=4):
        values = [0.0]
        for gap in gaps:
            values.append(values[-1] + gap)
        samples = [(axis, index) for index, axis in enumerate(values)]
        actual = _optimal_source_anchor_partitions(samples, fixed_cost)
        actual_cuts = tuple(sum(map(len, actual[:index])) for index in range(1, len(actual)))

        candidates = []
        for cut_mask in itertools.product((False, True), repeat=len(gaps)):
            cuts = (0,) + tuple(
                index + 1 for index, cut in enumerate(cut_mask) if cut
            ) + (len(values),)
            score = fixed_cost * (len(cuts) - 1) + sum(
                values[right - 1] - values[left]
                for left, right in zip(cuts, cuts[1:])
            )
            candidates.append((score, len(cuts), cuts[1:-1]))
        expected_cuts = min(candidates)[:2]
        actual_score = fixed_cost * len(actual) + sum(
            values[part[-1]] - values[part[0]] for part in actual
        )
        assert (actual_score, len(actual) + 1) == expected_cuts
        assert actual_cuts == min(candidates)[2]


def test_source_replication_integrates_every_distant_consumer_band() -> None:
    config, document, report = _forced_multiband_root_layout(4)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    root_anchors = [
        vertex
        for vertex in document.vertices
        if (vertex.logical_name or vertex.name) == "root"
    ]

    assert len(root_anchors) == 4
    assert report["source_rendering_replicas"] == 3
    assert report["source_replica_length_saved_px"] > 0
    assert report["source_replica_area_delta_px2"] <= 0
    assert quality["alignment"]["rendering_replicas"] == {"root": 3}
    assert quality["alignment"]["avoidable_source_replicas"] == []
    assert quality["passed"] is True


def test_public_single_source_example_naturally_renders_local_anchors() -> None:
    """The public fixture must prove aliases without a second logical source."""
    config = build_single_source_rendering_alias()
    document, report = generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    logical_edges = build_logical_edges(
        config,
        resolve_nodes(config, load_library_shapes(LIBRARY), {}, library_path=LIBRARY),
        LIBRARY,
    )
    indegree = Counter(edge.target for edge in logical_edges)
    roots = [name for name in config if indegree[name] == 0]
    anchors = [
        vertex for vertex in document.vertices
        if (vertex.logical_name or vertex.name) == "shared_source"
    ]
    used_source_ids = {edge.source_id for edge in document.edges}
    selection = report["selection"]
    statistics = selection["routing_statistics"]

    assert roots == ["shared_source"]
    assert len(anchors) == 2
    assert all(anchor.cell_id in used_source_ids for anchor in anchors)
    assert selection["source_replicated_roots"] == 1
    assert selection["source_rendering_replicas"] == 1
    assert selection["source_replica_length_saved_px"] > 0
    assert statistics["nodes"]["shared_source"]["rendering_anchors"] == 2
    assert len({vertex.logical_name or vertex.name for vertex in document.vertices}) == len(config)


def _assert_complex_multi_source_feature_space(
    config: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Independently prove that the public corpus spans the frozen topology space."""
    roots = {name for name, item in config.items() if not item.get("source")}
    terminals = [name for name, item in config.items() if item.get("kind") == "clock"]
    pads = [name for name, item in config.items() if item.get("kind") == "pad3"]
    memo: dict[str, frozenset[str]] = {}

    def root_ancestors(name: str, active: frozenset[str] = frozenset()) -> frozenset[str]:
        if name in memo:
            return memo[name]
        if name in active:
            raise AssertionError(f"cycle while resolving root ancestry: {name}")
        source = config[name].get("source")
        if not source:
            result = frozenset({name})
        else:
            upstream = source.values() if isinstance(source, dict) else (source,)
            result = frozenset().union(*(
                root_ancestors(str(reference).split("[", 1)[0], active | {name})
                for reference in upstream
            ))
        memo[name] = result
        return result

    signatures = [root_ancestors(name) for name in terminals]
    signature_sizes = Counter(map(len, signatures))
    pad_port_counts = Counter(
        len(config[name]["source"])
        for name in pads
        if isinstance(config[name].get("source"), dict)
    )
    source_pairs = {
        pair
        for signature in signatures
        for pair in itertools.combinations(sorted(signature), 2)
    }
    hybrid_muxes = []
    for name, item in config.items():
        source = item.get("source")
        if item.get("kind") != "mux2" or not isinstance(source, dict):
            continue
        upstream = {str(value).split("[", 1)[0] for value in source.values()}
        if upstream & set(pads) and upstream & roots:
            hybrid_muxes.append(name)

    single_root_signatures = [signature for signature in signatures if len(signature) == 1]
    direct_positions: dict[str, list[int]] = {root: [] for root in roots}
    for position, signature in enumerate(single_root_signatures):
        direct_positions[next(iter(signature))].append(position)
    gaps = {
        right - left
        for positions in direct_positions.values()
        for left, right in zip(positions, positions[1:])
    }
    gap_shapes = {
        tuple(right - left for left, right in zip(positions, positions[1:]))
        for positions in direct_positions.values()
        if len(positions) > 1
    }

    assert len(roots) == 8
    assert all(config[name].get("kind") == "source" for name in roots)
    assert len(terminals) == 48
    assert len(pads) == 8
    assert pad_port_counts == Counter({3: 6, 2: 2})
    assert len(hybrid_muxes) == 8
    assert signature_sizes == Counter({1: 24, 3: 15, 4: 6, 2: 3})
    assert len(set(signatures)) == 24
    assert len(source_pairs) >= 24
    assert sorted(map(len, direct_positions.values())) == [1, 2, 2, 2, 3, 4, 5, 5]
    assert gaps == set(range(3, 12))
    assert len(gap_shapes) >= 6
    assert all(any(root in signature and len(signature) > 1 for signature in signatures)
               for root in roots)
    return {
        "roots": len(roots),
        "terminals": len(terminals),
        "signature_sizes": signature_sizes,
        "unique_signatures": len(set(signatures)),
        "source_pairs": len(source_pairs),
        "gap_values": gaps,
    }


def test_public_multi_source_rows_cover_complex_interleaved_feature_space() -> None:
    config = build_dispersed_root_fanout()
    coverage = _assert_complex_multi_source_feature_space(config)
    document, report = generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert coverage["source_pairs"] >= 24
    assert {vertex.logical_name or vertex.name for vertex in document.vertices} == set(config)
    assert report["selection"]["source_rendering_replicas"] > 0
    assert report["selection"]["routing_statistics"]["totals"]["edges"] > len(config)
    assert quality["passed"] is True


def test_multi_source_feature_oracle_rejects_the_old_shallow_corpus() -> None:
    """Mutation check: the former 12-terminal example must not escape again."""
    config = build_dispersed_root_fanout()
    shallow = {
        name: item
        for name, item in config.items()
        if item.get("kind") != "clock" or int(name.rsplit("_", 1)[-1]) < 12
    }
    with pytest.raises(AssertionError):
        _assert_complex_multi_source_feature_space(shallow)


def test_complex_multi_source_corpus_survives_rename_and_order_transformations() -> None:
    """Names, object order, and multi-input member order are not layout semantics."""
    original = build_dispersed_root_fanout()
    renamed = {name: f"node_{index:03d}" for index, name in enumerate(original)}

    def rename_reference(reference: object) -> object:
        if not isinstance(reference, str):
            return reference
        base, separator, port = reference.partition("[")
        return renamed[base] + (separator + port if separator else "")

    transformed: dict[str, dict[str, object]] = {}
    for name, item in reversed(tuple(original.items())):
        updated = copy.deepcopy(item)
        source = updated.get("source")
        if isinstance(source, dict):
            updated["source"] = {
                port: rename_reference(reference)
                for port, reference in reversed(tuple(source.items()))
            }
        elif source is not None:
            updated["source"] = rename_reference(source)
        transformed[renamed[name]] = updated

    assert _assert_complex_multi_source_feature_space(transformed) == \
        _assert_complex_multi_source_feature_space(original)
    document, report = generate_elk_layout(
        transformed, library_path=LIBRARY, include_statistics=True
    )
    quality = inspect_layout_quality(
        transformed, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert {vertex.logical_name or vertex.name for vertex in document.vertices} == \
        set(transformed)
    assert report["selection"]["routing_statistics"]["totals"]["edges"] == 190
    assert quality["alignment"]["invalid_rendering_replicas"] == []
    assert quality["passed"] is True, quality["hard_failures"]


def test_source_replication_never_aliases_an_intermediate_fanout() -> None:
    config, document, report = _forced_multiband_root_layout(
        4, source_has_parent=True
    )
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert report["source_replica_candidate_roots"] == 0
    assert report["source_rendering_replicas"] == 0
    assert all(vertex.logical_name is None for vertex in document.vertices)
    assert quality["alignment"]["invalid_rendering_replicas"] == []
    assert quality["passed"] is False
    assert quality["hard_failures"]


def test_routing_statistics_are_attributed_to_edges_and_logical_sources() -> None:
    config = _minimal_dispersed_config()
    document, report = generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    statistics = report["selection"]["routing_statistics"]
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert statistics["row_pitch_px"] > 0
    assert statistics["totals"]["edges"] == 6
    assert statistics["totals"]["manhattan_length_px"] == pytest.approx(sum(
        edge["manhattan_length_px"] for edge in statistics["edges"].values()
    ), abs=0.001)
    assert len(statistics["edges"]) == 6
    assert set(statistics["nodes"]) == set(config)
    assert statistics["nodes"]["wide_root"]["direct_downstream_nodes"] == 3
    assert statistics["nodes"]["wide_clock_top_0"]["is_terminal"] is True
    assert statistics["nodes"]["wide_clock_top_0"]["outgoing_edges"] == 0
    assert statistics["sources"]["wide_root"]["outgoing_edges"] == 3
    assert statistics["sources"]["wide_root"]["manhattan_length_px"] == pytest.approx(sum(
        edge["manhattan_length_px"]
        for edge in statistics["edges"].values()
        if edge["source"] == "wide_root"
    ), abs=0.001)
    assert statistics == quality["readability"]["routing_statistics"]


def test_complex_source_weave_statistics_match_exact_pair_oracle() -> None:
    config = load_clock_tree(EXAMPLES / "19-dispersed-root-fanout.json")
    document, report = generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    production = report["selection"]["routing_statistics"]
    independent = inspect_layout_quality(
        config,
        document,
        library_path=LIBRARY,
        grid=0.0001,
        tolerance=0.01,
        exact_pair_oracle=True,
    )["readability"]["routing_statistics"]

    assert production == independent
    assert production["totals"]["crossing_pair_intersections"] >= production["totals"]["distinct_crossed_edge_pairs"]
    assert production["totals"]["distinct_crossed_edge_pairs"] >= production["totals"]["distinct_crossing_points"]


def test_complex_source_weave_anchor_relocation_dominates_inherited_columns(
    monkeypatch,
) -> None:
    import elk_layout as layout_module

    config = load_clock_tree(EXAMPLES / "19-dispersed-root-fanout.json")

    def keep_inherited(document, nodes, logical_edges, profile, **kwargs):
        assessment = kwargs.get("accepted_assessment")
        return document, {
            "source_anchor_relocation_attempts": 0,
            "source_anchor_column_moves": 0,
            "source_anchor_crossings_removed": 0,
            "source_anchor_source_crossings_removed": 0,
            "source_anchor_length_saved_px": 0.0,
            "source_anchor_relocation_blockers": {},
            **({"_accepted_assessment": assessment} if kwargs.get("include_assessment") else {}),
        }

    monkeypatch.setattr(
        layout_module, "_relocate_root_rendering_anchors", keep_inherited
    )
    inherited, inherited_report = layout_module.generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    monkeypatch.setattr(
        layout_module,
        "_relocate_root_rendering_anchors",
        _relocate_root_rendering_anchors,
    )
    optimized, optimized_report = layout_module.generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    inherited_totals = inherited_report["selection"]["routing_statistics"]["totals"]
    optimized_totals = optimized_report["selection"]["routing_statistics"]["totals"]
    optimized_quality = inspect_layout_quality(
        config, optimized, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert optimized_report["selection"]["source_anchor_column_moves"] > 0
    assert (
        optimized_totals["source_induced_crossing_points"],
        optimized_totals["distinct_crossing_points"],
        optimized_totals["bends_total"],
        optimized_totals["manhattan_length_px"],
    ) < (
        inherited_totals["source_induced_crossing_points"],
        inherited_totals["distinct_crossing_points"],
        inherited_totals["bends_total"],
        inherited_totals["manhattan_length_px"],
    )
    assert optimized_quality["passed"] is True, optimized_quality["hard_failures"]


def test_complex_source_weave_local_facilities_dominate_one_anchor_per_root(
    monkeypatch,
) -> None:
    """Long-root replication must improve the complete graph, not one route."""
    import elk_layout as layout_module

    config = load_clock_tree(EXAMPLES / "19-dispersed-root-fanout.json")

    def keep_long_roots(document, nodes, logical_edges, profile, **kwargs):
        assessment = kwargs.get("accepted_assessment")
        return document, {
            "source_local_partition_attempts": 0,
            "source_local_partition_roots": 0,
            "source_local_partition_replicas": 0,
            "source_local_partition_row_pitch_px": 0.0,
            "source_local_partition_gap_budget_px": 0.0,
            "source_local_partition_crossings_removed": 0,
            "source_local_partition_source_crossings_removed": 0,
            "source_local_partition_length_saved_px": 0.0,
            "source_local_partition_blockers": {},
            **({"_accepted_assessment": assessment} if kwargs.get("include_assessment") else {}),
        }

    def keep_root_corridors(document, nodes, logical_edges, profile, **kwargs):
        assessment = kwargs.get("accepted_assessment")
        return document, {
            "source_corridor_attempts": 0,
            "source_corridor_moves": 0,
            "source_corridor_retired_facilities": 0,
            "source_corridor_expanded_px": 0.0,
            "source_corridor_crossings_removed": 0,
            "source_corridor_bends_removed": 0,
            "source_corridor_blockers": {},
            **({"_accepted_assessment": assessment} if kwargs.get("include_assessment") else {}),
        }

    monkeypatch.setattr(
        layout_module, "_split_root_rendering_anchors_by_local_rows", keep_long_roots
    )
    monkeypatch.setattr(
        layout_module, "_open_root_facility_corridors", keep_root_corridors
    )
    _, long_report = layout_module.generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    monkeypatch.setattr(
        layout_module,
        "_split_root_rendering_anchors_by_local_rows",
        _split_root_rendering_anchors_by_local_rows,
    )
    optimized, optimized_report = layout_module.generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    long_totals = long_report["selection"]["routing_statistics"]["totals"]
    optimized_totals = optimized_report["selection"]["routing_statistics"]["totals"]
    optimized_sources = optimized_report["selection"]["routing_statistics"]["sources"]
    quality = inspect_layout_quality(
        config, optimized, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert all(
        optimized_sources[root]["rendering_anchors"] > 1
        for root in ("source_a", "source_c", "source_g")
    )
    assert optimized_totals["distinct_crossing_points"] * 2 <= \
        long_totals["distinct_crossing_points"]
    assert optimized_totals["source_induced_crossing_points"] * 2 <= \
        long_totals["source_induced_crossing_points"]
    assert optimized_totals["bends_total"] <= long_totals["bends_total"]
    assert optimized_totals["manhattan_length_px"] * 4 < \
        long_totals["manhattan_length_px"] * 3
    assert quality["passed"] is True, quality["hard_failures"]


def test_crossing_statistics_identify_each_involved_edge_and_source() -> None:
    config = {
        "root_a": {"kind": "from"},
        "root_b": {"kind": "from"},
        "gate_a": {"kind": "gate", "source": "root_a"},
        "gate_b": {"kind": "gate", "source": "root_b"},
    }
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    logical_edges = build_logical_edges(config, nodes, LIBRARY)
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    edge_by_id = {edge.cell_id: edge for edge in document.edges}
    first = edge_by_id["e1"]
    second = edge_by_id["e2"]
    first_logical, second_logical = logical_edges
    first_source = by_id[first.source_id]
    first_target = by_id[first.target_id]
    second_source = by_id[second.source_id]
    second_target = by_id[second.target_id]
    first_target.y = first_source.y + 300.0
    second_source.y = first_source.y + 150.0
    second_target.y = second_source.y
    first_start = abs_port_xy(
        first_source.x, first_source.y, first_source.width, first_source.height,
        first_source.style, first_source.drawclock_type, first_logical.source_port,
    )
    first_end = abs_port_xy(
        first_target.x, first_target.y, first_target.width, first_target.height,
        first_target.style, first_target.drawclock_type, first_logical.target_port,
    )
    channel_x = (first_start[0] + first_end[0]) / 2.0
    first.waypoints = ((channel_x, first_start[1]), (channel_x, first_end[1]))
    second.waypoints = ()

    production = assess_layout(
        document,
        logical_edges,
        0.0,
        include_routing_statistics=True,
    )["routing_statistics"]
    independent = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )["readability"]["routing_statistics"]

    assert production == independent
    assert production["edges"]["e1"]["crossing_points"] == 1
    assert production["edges"]["e2"]["crossing_points"] == 1
    assert production["edges"]["e1"]["crossed_edge_count"] == 1
    assert production["edges"]["e2"]["crossed_edge_count"] == 1
    assert production["sources"]["root_a"]["crossing_points"] == 1
    assert production["sources"]["root_b"]["crossing_points"] == 1
    assert production["nodes"]["root_a"]["crossed_edge_count"] == 1
    assert production["nodes"]["root_b"]["crossed_edge_count"] == 1


def test_low_use_roots_move_to_their_latest_feasible_middle_column() -> None:
    config = load_clock_tree(
        ROOT / "example" / "auto-layout" / "23-middle-column-low-use-sources.json"
    )
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    x_by_name = {vertex.name: vertex.x for vertex in document.vertices}

    assert ranks["common_source"] == 0
    assert {ranks[f"local_source_{index:02d}"] for index in range(8)} == {4}
    assert {ranks[f"mux_{index:02d}"] for index in range(8)} == {5}
    assert all(
        x_by_name["common_source"] < x_by_name[f"local_source_{index:02d}"]
        < x_by_name[f"mux_{index:02d}"]
        for index in range(8)
    )
    assert quality["line_integrity"]["distinct_crossing_points"] == 0
    assert quality["line_integrity"][
        "avoidable_zero_crossing_root_bend_edges"
    ] == []
    assert quality["alignment"]["root_facility_column_count"] == 2
    assert sorted(
        column["facility_count"]
        for column in quality["alignment"]["root_facility_columns"]
    ) == [1, 8]
    assert quality["passed"] is True


def test_middle_column_oracle_rejects_full_forced_first_column_layout() -> None:
    config = load_clock_tree(
        ROOT / "example" / "auto-layout" / "23-middle-column-low-use-sources.json"
    )
    natural, natural_report = generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    forced_config = copy.deepcopy(config)
    for name, item in forced_config.items():
        if name == "common_source" or name.startswith("local_source_"):
            item["layout_column"] = 0
    forced, forced_report = generate_elk_layout(
        forced_config, library_path=LIBRARY, include_statistics=True
    )
    natural_quality = inspect_layout_quality(
        config, natural, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    forced_quality = inspect_layout_quality(
        config, forced, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    natural_totals = natural_report["selection"]["routing_statistics"]["totals"]
    forced_totals = forced_report["selection"]["routing_statistics"]["totals"]

    assert natural_totals["distinct_crossing_points"] == 0
    assert forced_totals["distinct_crossing_points"] > 0
    assert natural_totals["bends_total"] < forced_totals["bends_total"]
    assert natural_totals["manhattan_length_px"] < forced_totals["manhattan_length_px"]
    assert natural_quality["layout_order"]["avoidable_root_layer_positions"] == []
    assert forced_quality["passed"] is False
    assert {
        item["node"]
        for item in forced_quality["layout_order"]["avoidable_root_layer_positions"]
    } == {f"local_source_{index:02d}" for index in range(8)}


def test_middle_source_fixture_is_name_and_input_order_independent() -> None:
    original = build_middle_column_low_use_sources()
    names = list(original)
    renamed = {name: f"arbitrary_{index:02d}" for index, name in enumerate(names)}
    config: dict[str, dict[str, object]] = {}
    for name in reversed(names):
        item = copy.deepcopy(original[name])
        source = item.get("source")
        if isinstance(source, str):
            item["source"] = renamed[source]
        elif isinstance(source, dict):
            item["source"] = {
                port: renamed[parent] for port, parent in reversed(source.items())
            }
        config[renamed[name]] = item
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    edges = build_logical_edges(config, nodes, LIBRARY)
    ranks = _ranks(nodes, edges)
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert ranks[renamed["common_source"]] == 0
    assert {ranks[renamed[f"local_source_{index:02d}"]] for index in range(8)} == {4}
    assert quality["layout_order"]["avoidable_root_layer_positions"] == []
    assert quality["passed"] is True


def test_four_row_dispersal_is_already_eligible_for_safe_replication() -> None:
    config = _minimal_dispersed_config()
    # Existing consumer rows already occupy part of the offset; 425 px leaves
    # just over the measured three-row budget between adjacent bands.
    document, report = _forced_dispersed_root_layout(config, offset=425.0)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert report["source_replica_row_budget"] == 3
    assert report["source_replicated_roots"] == 1
    assert report["source_rendering_replicas"] == 1
    assert quality["passed"] is True


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
    document, report = generate_elk_layout(
        config, library_path=LIBRARY, include_statistics=True
    )
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    source_tops = [
        vertex.y
        for vertex in document.vertices
        if vertex.name.startswith("from_") and vertex.logical_name is None
    ]

    assert quality["passed"] is True
    assert report["selection"]["source_position_mode"] == "adaptive-span"
    assert quality["readability"]["fanout_trunk_clusters"] == {}
    assert quality["readability"]["fragmented_fanout_sources"] == {}
    assert len(set(source_tops)) == 4
    root_outgoing_edges = sum(
        1
        for item in report["selection"]["routing_statistics"]["edges"].values()
        if item["source"].startswith("from_")
    )
    physical_root_anchors = 4 + report["selection"]["source_rendering_replicas"]
    assert physical_root_anchors <= root_outgoing_edges
    assert report["selection"]["source_replica_crossings_removed"] > 0
    assert report["selection"]["source_replica_length_saved_px"] > 0
    assert quality["alignment"]["unused_rendering_replicas"] == []
    assert quality["alignment"]["avoidable_source_replicas"] == []
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


def test_low_use_root_promotion_is_topology_driven() -> None:
    names = ["common", "local", "merge", "other"]
    edges = [
        LogicalEdge("common", "merge", "right", "in0"),
        LogicalEdge("common", "other", "right", "left"),
        LogicalEdge("local", "merge", "right", "in1"),
    ]
    ranks = _ranks(names, edges)

    assert ranks["common"] == 0
    assert ranks["local"] == 1
    assert ranks["merge"] == 2
    assert all(ranks[edge.source] < ranks[edge.target] for edge in edges)


def test_explicit_column_preference_prevents_implicit_root_promotion() -> None:
    names = ["common", "local", "merge", "other"]
    edges = [
        LogicalEdge("common", "merge", "right", "in0"),
        LogicalEdge("common", "other", "right", "left"),
        LogicalEdge("local", "merge", "right", "in1"),
    ]
    ranks = _ranks(names, edges, {0: ["local"]})

    assert ranks["local"] == 0
    assert all(ranks[edge.source] < ranks[edge.target] for edge in edges)


def test_mixed_graph_roots_are_placed_by_consumers_and_fixed_port_order() -> None:
    config = build_mixed_root_port_order_torture()
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )
    line = quality["line_integrity"]
    vertices = {vertex.name: vertex for vertex in document.vertices}

    assert quality["passed"] is True
    assert line["root_merge_input_order_inversions"] == []
    assert line["avoidable_root_merge_input_crossings"] == []
    for index in range(12):
        pad_x = vertices[f"pad_{index:02d}"].x
        for prefix in ("local_a", "local_b"):
            root = vertices[f"{prefix}_{index:02d}"]
            assert root.x < pad_x
    assert line["avoidable_bend_edges"] == []
    assert quality["readability"]["fragmented_fanout_sources"] == {}


def test_combined_feedback_layout_consolidates_overlapping_root_aliases() -> None:
    config = load_clock_tree(EXAMPLES / "26-feedback-reproduction-combined.json")
    document, report = generate_elk_layout(config, library_path=LIBRARY)
    quality = inspect_layout_quality(
        config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01
    )

    assert report["selection"]["fanout_residual_logical_cycle_rank"] == 0
    assert report["selection"]["source_corridor_moves"] >= 1
    assert report["selection"]["source_corridor_crossings_removed"] >= 1
    assert report["selection"]["source_corridor_bends_removed"] >= 1
    assert quality["line_integrity"]["split_rejoin_fanout_nets"] == []


def test_quality_oracle_rejects_same_root_split_rejoin_cycle() -> None:
    config = {
        "root": {"kind": "from"},
        "gate_a": {"kind": "gate", "source": "root"},
        "gate_b": {"kind": "gate", "source": "root"},
        "clock_a": {"kind": "clock", "source": "gate_a"},
        "clock_b": {"kind": "clock", "source": "gate_b"},
    }
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    shapes = load_library_shapes(LIBRARY)
    nodes = resolve_nodes(config, shapes, {}, library_path=LIBRARY)
    logical_edges = build_logical_edges(config, nodes, LIBRARY)
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    root_edges = [edge for edge in document.edges if edge.source_id == nodes["root"].cell_id]
    starts_ends = []
    for edge in root_edges:
        logical = logical_edges[int(edge.cell_id[1:]) - 1]
        source, target = by_id[edge.source_id], by_id[edge.target_id]
        start = abs_port_xy(source.x, source.y, source.width, source.height, source.style, source.drawclock_type, logical.source_port)
        end = abs_port_xy(target.x, target.y, target.width, target.height, target.style, target.drawclock_type, logical.target_port)
        starts_ends.append((edge, start, end))
    start = starts_ends[0][1]
    x1, x2 = start[0] + 20.0, start[0] + 40.0
    x3 = min(item[2][0] for item in starts_ends) - 20.0
    y_join = max(item[2][1] for item in starts_ends) + 90.0
    for offset, (edge, _, end) in enumerate(starts_ends):
        lane = x1 if offset == 0 else x2
        edge.waypoints = ((lane, start[1]), (lane, y_join), (x3, y_join), (x3, end[1]))
    quality = inspect_layout_quality(config, document, library_path=LIBRARY, grid=0.0001, tolerance=0.01)
    assert quality["line_integrity"]["split_rejoin_fanout_nets"]
    assert quality["passed"] is False


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

    compact_config = {
        "wide_root": {"kind": "from"},
        "compact_mux": {
            "kind": "mux2",
            "source": {"0": "wide_root", "1": "wide_root"},
        },
        "compact_clock": {"kind": "clock", "source": "compact_mux"},
    }
    compact_document, _ = generate_elk_layout(
        compact_config, library_path=LIBRARY
    )
    redundant = copy.deepcopy(compact_document)
    compact_root_anchors = [
        vertex for vertex in redundant.vertices
        if (vertex.logical_name or vertex.name) == "wide_root"
    ]
    compact_primary = compact_root_anchors[0]
    compact_shapes = load_library_shapes(LIBRARY)
    compact_nodes = resolve_nodes(
        compact_config, compact_shapes, {}, library_path=LIBRARY
    )
    compact_edges = build_logical_edges(compact_config, compact_nodes, LIBRARY)
    for index, logical in enumerate(compact_edges, 1):
        if logical.source == "wide_root":
            next(
                edge for edge in redundant.edges if edge.cell_id == f"e{index}"
            ).source_id = compact_primary.cell_id
    redundant.vertices = [
        vertex for vertex in redundant.vertices
        if (vertex.logical_name or vertex.name) != "wide_root"
        or vertex.cell_id == compact_primary.cell_id
    ]
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
        compact_config,
        redundant,
        library_path=LIBRARY,
        grid=0.0001,
        tolerance=0.01,
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


def test_quality_gate_rejects_zero_crossing_bend_on_movable_root_facility() -> None:
    config = {
        "root": {"kind": "from"},
        "gate": {"kind": "gate", "source": "root"},
        "clock": {"kind": "clock", "source": "gate"},
    }
    document, _ = generate_elk_layout(config, library_path=LIBRARY)
    by_id = {vertex.cell_id: vertex for vertex in document.vertices}
    root = next(vertex for vertex in document.vertices if vertex.name == "root")
    edge = next(item for item in document.edges if item.source_id == root.cell_id)
    target = by_id[edge.target_id]
    root.y += 56.0
    logical_edges = build_logical_edges(
        config,
        resolve_nodes(
            config,
            load_library_shapes(LIBRARY),
            {},
            library_path=LIBRARY,
        ),
        LIBRARY,
    )
    logical = logical_edges[int(edge.cell_id[1:]) - 1]
    start = abs_port_xy(
        root.x,
        root.y,
        root.width,
        root.height,
        root.style,
        root.drawclock_type,
        logical.source_port,
    )
    end = abs_port_xy(
        target.x,
        target.y,
        target.width,
        target.height,
        target.style,
        target.drawclock_type,
        logical.target_port,
    )
    lane_x = (start[0] + end[0]) / 2.0
    edge.waypoints = ((lane_x, start[1]), (lane_x, end[1]))

    quality = inspect_layout_quality(
        config,
        document,
        library_path=LIBRARY,
        grid=0.0001,
        tolerance=0.01,
    )

    assert quality["line_integrity"][
        "avoidable_zero_crossing_root_bend_edges"
    ] == [edge.cell_id]
    assert (
        f"avoidable-zero-crossing-root-bends:{edge.cell_id}"
        in quality["hard_failures"]
    )
    assert quality["passed"] is False


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
