from __future__ import annotations

import importlib.util
import json
import ast
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ORACLE_PATH = ROOT / "tools" / "feedback_layout_reproduction_oracle.py"
QUALITY_ORACLE_PATH = ROOT / "tools" / "svg_layout_quality_oracle.py"
SPEC = importlib.util.spec_from_file_location("feedback_layout_oracle", ORACLE_PATH)
assert SPEC is not None and SPEC.loader is not None
oracle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = oracle
SPEC.loader.exec_module(oracle)


def test_oracle_source_has_no_production_import() -> None:
    for path in (ORACLE_PATH, QUALITY_ORACLE_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name == "src" or name.startswith("src.") for name in imports)


def test_geometry_predicates_separate_cross_touch_and_overlap() -> None:
    assert oracle.proper_cross((0, 5), (10, 5), (4, 0), (4, 10)) == (4, 5)
    assert oracle.proper_cross((0, 5), (10, 5), (0, 0), (0, 10)) is None
    assert oracle.collinear_overlap((0, 5), (10, 5), (4, 5), (12, 5)) == 6
    assert oracle.collinear_overlap((0, 5), (10, 5), (4, 6), (12, 6)) == 0


def test_crossing_predicate_is_translation_and_argument_order_invariant() -> None:
    horizontal = ((0, 5), (10, 5))
    vertical = ((4, 0), (4, 10))
    assert oracle.proper_cross(*horizontal, *vertical) == (4, 5)
    assert oracle.proper_cross(*vertical, *horizontal) == (4, 5)
    shift = (17, -9)
    moved = [tuple(point[index] + shift[index] for index in range(2)) for point in (*horizontal, *vertical)]
    assert oracle.proper_cross(*moved) == (21, -4)


def test_simplify_removes_duplicate_and_collinear_waypoints() -> None:
    assert oracle.simplify([(0, 0), (0, 0), (3, 0), (8, 0), (8, 4)]) == [
        (0, 0), (8, 0), (8, 4)
    ]


def test_duplicate_source_target_edges_bind_by_endpoint_order_not_svg_order() -> None:
    boxes = [oracle.Box("root", 0, 0, 10, 30), oracle.Box("mux", 40, 0, 10, 30)]
    routes = [
        oracle.Route(0, [(10, 20), (40, 20)]),
        oracle.Route(1, [(10, 10), (40, 10)]),
    ]
    logical = [
        oracle.LogicalEdge("root", "mux", "0"),
        oracle.LogicalEdge("root", "mux", "1"),
    ]
    oracle.bind_routes(routes, boxes, logical)
    assert routes[0].target_port == "1"
    assert routes[1].target_port == "0"


def test_same_net_topology_distinguishes_tree_from_split_rejoin_cycle() -> None:
    tree = [
        oracle.Route(0, [(0, 0), (5, 0), (5, -2), (10, -2)], source="r"),
        oracle.Route(1, [(0, 0), (5, 0), (5, 2), (10, 2)], source="r"),
    ]
    cycle = [
        oracle.Route(0, [(0, 0), (3, 0), (3, -2), (7, -2), (7, 0), (10, 0)], source="r"),
        oracle.Route(1, [(0, 0), (3, 0), (3, 2), (7, 2), (7, 0), (10, 0)], source="r"),
    ]
    assert oracle._same_net_cycle(tree) is False
    assert oracle._same_net_cycle(cycle) is True


def test_vertical_root_facility_oracle_requires_full_geometric_dominance() -> None:
    route = oracle.Route(
        0,
        [(10, 5), (30, 5), (30, 25), (50, 25)],
        source="root",
        target="sink",
    )
    boxes = [
        oracle.Box("root", 0, 0, 10, 10),
        oracle.Box("sink", 50, 20, 10, 10),
    ]
    witnesses = oracle._vertical_root_facility_bend_witnesses(
        {"root"}, [route], boxes
    )
    assert len(witnesses) == 1
    assert witnesses[0]["bends_before"] == 2
    assert witnesses[0]["bends_after"] == 0

    blocked = [*boxes, oracle.Box("obstacle", 20, 20, 10, 10)]
    assert oracle._vertical_root_facility_bend_witnesses(
        {"root"}, [route], blocked
    ) == []


def test_vertical_root_facility_oracle_counts_visible_label_footprint() -> None:
    route = oracle.Route(
        0,
        [(10, 5), (30, 5), (30, 25), (50, 25)],
        source="root",
        target="sink",
    )
    boxes = [
        oracle.Box("root", 0, 0, 10, 10),
        oracle.Box("sink", 50, 20, 10, 10),
        oracle.Box("label_owner", 20, 0, 2, 2, 18, 20, 14, 10),
    ]
    assert oracle._vertical_root_facility_bend_witnesses(
        {"root"}, [route], boxes
    ) == []


def test_crossing_free_intervals_cover_whole_prefix_interior_and_suffix() -> None:
    route = oracle.Route(0, [(0, 10), (30, 10), (30, 20), (70, 20), (70, 30), (100, 30)], source="a", target="b")
    crossings = [
        oracle.Route(1, [(10, 0), (10, 40)], source="x1", target="y1"),
        oracle.Route(2, [(50, 0), (50, 40)], source="x2", target="y2"),
        oracle.Route(3, [(90, 0), (90, 40)], source="x3", target="y3"),
    ]
    intervals = oracle._ordered_crossing_free_intervals(route, [route, *crossings])
    assert [row["kind"] for row in intervals] == ["prefix", "interior", "interior", "suffix"]
    assert [row["internal_bends"] for row in intervals] == [0, 2, 2, 0]
    straight = oracle.Route(4, [(0, 0), (20, 0)], source="p", target="q")
    assert oracle._ordered_crossing_free_intervals(straight, [straight])[0]["kind"] == "whole"


def test_frozen_public_svg_exposes_crossing_partitioned_tail_bend() -> None:
    input_path = ROOT / "example/auto-layout/26-feedback-reproduction-combined.json"
    receipt = json.loads(
        (ROOT / ".reproduction/receipts/FB-BEND-013.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = receipt["attempts"][0]["evidence_files"]
    output = next(ROOT / path for path in evidence if path.endswith("/output.svg"))
    report = oracle.analyze(input_path, output)
    assert "FB-BEND-013" in report["detected_issues"]
    witness = report["witnesses"]["downstream_corridor_tail_bend_witnesses"][0]
    assert witness["crossing_pairs_before"] == witness["crossing_pairs_after"] == 1
    assert any(
        row["tail_kind"] == "suffix"
        and row["crossings_before"] == 1
        and row["tail_bends_before"] == 2
        and row["tail_bends_after"] == 0
        for row in witness["affected_edges"]
    )


def test_downstream_corridor_oracle_finds_crossing_free_tail_bends() -> None:
    routes = [
        oracle.Route(0, [(10, 5), (30, 5), (30, 0), (50, 0)], source="a", target="mux", target_port="0"),
        oracle.Route(1, [(10, 25), (35, 25), (35, 20), (50, 20)], source="b", target="mux", target_port="1"),
        oracle.Route(2, [(60, 10), (80, 10)], source="mux", target="sink"),
        oracle.Route(3, [(20, 15), (20, 30)], source="x", target="y"),
    ]
    logical = [oracle.LogicalEdge("a", "mux", "0"), oracle.LogicalEdge("b", "mux", "1"), oracle.LogicalEdge("mux", "sink", "left"), oracle.LogicalEdge("x", "y", "left")]
    boxes = [
        oracle.Box("a", 0, 0, 10, 10), oracle.Box("b", 0, 20, 10, 10),
        oracle.Box("mux", 50, -5, 10, 30), oracle.Box("sink", 80, 5, 10, 10),
        oracle.Box("x", 15, 10, 10, 5), oracle.Box("y", 15, 30, 10, 5),
    ]
    witness = oracle._downstream_corridor_tail_bend_witnesses(logical, routes, boxes)
    assert len(witness) == 1
    assert witness[0]["target"] == "mux"
    assert witness[0]["crossing_pairs_before"] == witness[0]["crossing_pairs_after"] == 1
    assert witness[0]["bends_after"] < witness[0]["bends_before"]
    assert any(row["crossings_before"] == 1 for row in witness[0]["affected_edges"])


def test_downstream_corridor_oracle_rejects_nonuniform_or_blocked_moves() -> None:
    logical = [oracle.LogicalEdge("a", "mux", "0"), oracle.LogicalEdge("b", "mux", "1")]
    boxes = [oracle.Box("a", 0, 0, 10, 10), oracle.Box("b", 0, 20, 10, 10), oracle.Box("mux", 50, -5, 10, 30)]
    nonuniform = [
        oracle.Route(0, [(10, 5), (30, 5), (30, 0), (50, 0)], source="a", target="mux", target_port="0"),
        oracle.Route(1, [(10, 25), (35, 25), (35, 18), (50, 18)], source="b", target="mux", target_port="1"),
    ]
    assert oracle._downstream_corridor_tail_bend_witnesses(logical, nonuniform, boxes) == []
    uniform = [
        oracle.Route(0, [(10, 5), (30, 5), (30, 0), (50, 0)], source="a", target="mux", target_port="0"),
        oracle.Route(1, [(10, 25), (35, 25), (35, 20), (50, 20)], source="b", target="mux", target_port="1"),
    ]
    assert oracle._downstream_corridor_tail_bend_witnesses(logical, uniform, [*boxes, oracle.Box("obstacle", 50, 25, 10, 10)]) == []


def test_downstream_corridor_oracle_expands_a_conflicting_target_row() -> None:
    routes = [
        oracle.Route(0, [(10, 5), (30, 5), (30, 0), (50, 0)], source="a", target="mux", target_port="0"),
        oracle.Route(1, [(10, 25), (35, 25), (35, 20), (50, 20)], source="b", target="mux", target_port="1"),
        oracle.Route(2, [(10, 5), (25, 5), (25, 28), (80, 28)], source="a", target="tap"),
    ]
    logical = [oracle.LogicalEdge("a", "mux", "0"), oracle.LogicalEdge("b", "mux", "1"), oracle.LogicalEdge("a", "tap", "left")]
    boxes = [
        oracle.Box("a", 0, 0, 10, 10), oracle.Box("b", 0, 20, 10, 10),
        oracle.Box("mux", 50, -5, 10, 30), oracle.Box("tap", 80, 23, 10, 10),
    ]
    witness = oracle._downstream_corridor_tail_bend_witnesses(logical, routes, boxes)
    assert len(witness) == 1
    assert witness[0]["moved_nodes"] == 2
    assert witness[0]["bends_after"] < witness[0]["bends_before"]


def test_root_column_lag_oracle_aligns_only_through_a_safe_used_column() -> None:
    lagging = oracle.Route(
        0,
        [(10, 5), (30, 5), (30, 25), (100, 25)],
        source="lagging",
        target="sink_a",
    )
    aligned = oracle.Route(
        1, [(70, 65), (100, 65)], source="aligned", target="sink_b"
    )
    boxes = [
        oracle.Box("lagging", 0, 0, 10, 10),
        oracle.Box("aligned", 60, 60, 10, 10),
        oracle.Box("sink_a", 100, 20, 10, 10),
        oracle.Box("sink_b", 100, 60, 10, 10),
    ]
    witnesses = oracle._root_facility_column_lag_witnesses(
        {"lagging", "aligned"}, [lagging, aligned], boxes
    )
    assert [row["root"] for row in witnesses] == ["lagging"]
    assert witnesses[0]["crossing_events_before"] == 0
    assert witnesses[0]["crossing_events_after"] == 0

    blocked = [*boxes, oracle.Box("obstacle", 60, 20, 10, 10)]
    assert oracle._root_facility_column_lag_witnesses(
        {"lagging", "aligned"}, [lagging, aligned], blocked
    ) == []


def test_frozen_combined_artifact_exposes_bend_and_root_column_escapes() -> None:
    input_path = ROOT / "example/auto-layout/26-feedback-reproduction-combined.json"
    receipt = json.loads(
        (ROOT / ".reproduction/receipts/FB-BEND-011.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = receipt["attempts"][0]["evidence_files"]
    output = next(ROOT / path for path in evidence if path.endswith("/output.svg"))
    report = oracle.analyze(input_path, output)
    assert {"FB-BEND-011", "FB-ROOT-012"}.issubset(report["detected_issues"])
    assert any(
        row["source"] == "weave__public_from"
        and row["target"] == "weave__merge_07"
        and row["crossings_before"] == row["crossings_after"] == 0
        and row["bends_before"] == 2
        and row["bends_after"] == 0
        for row in report["witnesses"]["vertical_root_facility_bend_witnesses"]
    )
    assert any(
        row["root"] == "weave__public_from"
        and row["target"] == "weave__merge_07"
        and row["output_x_after"] > row["output_x_before"]
        and row["crossing_events_before"] == row["crossing_events_after"] == 0
        for row in report["witnesses"]["root_facility_column_lag_witnesses"]
    )


def test_oracle_reads_public_svg_without_importing_production(tmp_path: Path) -> None:
    input_path = ROOT / "tests" / "reproduction-corpus" / "pad-r08-s00.json"
    output = tmp_path / "output.svg"
    result = subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path), "-l", str(ROOT / "drawio-lib"),
         "-o", str(output), "--crossing-style", "none"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = oracle.analyze(input_path, output)
    assert report["totals"]["logical_edges"] == report["totals"]["rendered_edges"] == 48
    assert report["totals"]["proper_crossing_events"] >= report["totals"]["distinct_crossing_points"]
    assert set(report["witnesses"]["mixed_root_kinds"]) == {"from", "gate", "source"}
    assert report["witnesses"]["mixed_root_quality_failures"] == []
    # This fixture is a public-entry smoke test for the older mixed-root
    # contract.  New independent detectors may legitimately discover another
    # registered defect in the same artifact; do not make issues exclusive.
    assert "FB-ROOT-001" not in report["detected_issues"]
    assert report["witnesses"]["split_rejoin_roots"] == []


def test_oracle_recovers_rectilinear_route_through_default_jump_arc() -> None:
    points = oracle._parse_path_as_polyline(
        "M 0 10 L 20 10 A 4 4 0 0 0 28 10 L 40 10 L 40 30"
    )
    assert points == [(0.0, 10.0), (40.0, 10.0), (40.0, 30.0)]


def test_oracle_rejects_nonorthogonal_or_unrelated_curves() -> None:
    with pytest.raises(ValueError, match="non-orthogonal"):
        oracle._parse_path_as_polyline("M 0 0 A 4 4 0 0 0 8 8")
    with pytest.raises(ValueError, match="unsupported"):
        oracle._parse_path_as_polyline("M 0 0 Q 4 4 8 0")


def test_frozen_combined_example_reproduces_root_facility_detour() -> None:
    input_path = ROOT / "example/auto-layout/26-feedback-reproduction-combined.json"
    receipt = json.loads(
        (ROOT / ".reproduction/receipts/FB-ROUTE-009.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = receipt["attempts"][0]["evidence_files"]
    output = next(ROOT / path for path in evidence if path.endswith("/output.svg"))
    report = oracle.analyze(input_path, output)
    assert report["totals"]["logical_nodes"] == 121
    assert report["totals"]["logical_edges"] == 122
    assert report["totals"]["different_net_overlaps"] == 0
    assert report["witnesses"]["split_rejoin_roots"] == []
    assert "FB-ROUTE-009" in report["detected_issues"]
    witness = report["witnesses"]["root_facility_split_witnesses"]
    assert any(
        row["root"] == "weave__public_gate"
        and row["bends_before"] == 4
        and row["bends_after"] == 0
        and row["length_after"] < row["length_before"]
        for row in witness
    )


def test_frozen_medium_example_reproduces_physical_anchor_column_escape() -> None:
    input_path = ROOT / "example/auto-layout/07-medium-64-clocks.json"
    receipt = json.loads(
        (ROOT / ".reproduction/receipts/FB-ROOT-010.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = receipt["attempts"][0]["evidence_files"]
    output = next(ROOT / path for path in evidence if path.endswith("/output.svg"))
    report = oracle.analyze(input_path, output)
    assert "FB-ROOT-010" in report["detected_issues"]
    witnesses = report["witnesses"]["physical_anchor_relocation_witnesses"]
    assert any(
        row["root"] == "xtal_1"
        and row["physical_anchor_edges"] == 1
        and row["crossing_events_after"] < row["crossing_events_before"]
        and row["length_after"] < row["length_before"]
        for row in witnesses
    )


@pytest.mark.parametrize(
    ("filename", "forbidden", "max_events", "max_points", "max_bends"),
    [
        ("26-feedback-reproduction-combined.json", {"FB-ROUTE-009", "FB-ROOT-010", "FB-BEND-013"}, 1, 1, 2),
        ("07-medium-64-clocks.json", {"FB-ROOT-010"}, 130, 19, 204),
    ],
)
def test_current_public_cli_closes_new_root_feedback(
    tmp_path: Path,
    filename: str,
    forbidden: set[str],
    max_events: int,
    max_points: int,
    max_bends: int,
) -> None:
    input_path = ROOT / "example/auto-layout" / filename
    output = tmp_path / f"{Path(filename).stem}.svg"
    result = subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path),
         "-l", str(ROOT / "drawio-lib"), "-o", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = oracle.analyze(input_path, output)
    assert forbidden.isdisjoint(report["detected_issues"])
    assert report["totals"]["different_net_overlaps"] == 0
    assert report["totals"]["proper_crossing_events"] <= max_events
    assert report["totals"]["distinct_crossing_points"] <= max_points
    assert report["totals"]["bends"] <= max_bends


def test_single_route_root_without_crossed_trunk_is_clean_counterexample(
    tmp_path: Path,
) -> None:
    input_path = ROOT / "example/auto-layout/01-linear.json"
    output = tmp_path / "linear.svg"
    subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path),
         "-l", str(ROOT / "drawio-lib"), "-o", str(output),
         "--crossing-style", "none"],
        cwd=ROOT, check=True,
    )
    report = oracle.analyze(input_path, output)
    assert report["witnesses"]["root_facility_split_witnesses"] == []
    assert report["witnesses"]["physical_anchor_relocation_witnesses"] == []
    assert "FB-ROUTE-009" not in report["detected_issues"]
    assert "FB-ROOT-010" not in report["detected_issues"]


def test_oracle_rejects_frozen_mixed_root_failure() -> None:
    receipt = json.loads(
        (ROOT / ".reproduction/receipts/FB-ROOT-001.json").read_text(encoding="utf-8")
    )
    evidence = receipt["attempts"][0]["evidence_files"]
    svg_path = next(ROOT / path for path in evidence if path.endswith("/output.svg"))
    input_path = ROOT / "tests/reproduction-corpus/pad-r08-s00.json"
    report = oracle.analyze(input_path, svg_path)
    assert report["witnesses"]["mixed_root_quality_failures"]
    assert "FB-ROOT-001" in report["detected_issues"]


def test_mixed_root_kinds_alone_are_not_a_defect(tmp_path: Path) -> None:
    config = {
        "root_a": {"kind": "source"},
        "gate_a": {"kind": "gate", "source": "root_a"},
        "clock_a": {"kind": "clock", "source": "gate_a"},
        "root_b": {"kind": "from"},
        "gate_b": {"kind": "gate", "source": "root_b"},
        "clock_b": {"kind": "clock", "source": "gate_b"},
        "root_c": {"kind": "gate"},
        "cell_c": {"kind": "cell", "source": "root_c"},
        "clock_c": {"kind": "clock", "source": "cell_c"},
    }
    input_path = tmp_path / "mixed-good.json"
    output = tmp_path / "mixed-good.svg"
    input_path.write_text(json.dumps(config), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path), "-l", str(ROOT / "drawio-lib"),
         "-o", str(output), "--crossing-style", "none"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = oracle.analyze(input_path, output)
    assert set(report["witnesses"]["mixed_root_kinds"]) == {"from", "gate", "source"}
    assert report["witnesses"]["mixed_root_quality_failures"] == []
    assert "FB-ROOT-001" not in report["detected_issues"]


def test_cli_fails_closed_for_unobserved_issue(tmp_path: Path) -> None:
    input_path = ROOT / "example" / "auto-layout" / "01-linear.json"
    output = tmp_path / "linear.svg"
    subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path), "-l", str(ROOT / "drawio-lib"),
         "-o", str(output), "--crossing-style", "none"], cwd=ROOT, check=True,
    )
    result = subprocess.run(
        [sys.executable, str(ORACLE_PATH), "--input", str(input_path), "--svg", str(output),
         "--issue", "FB-ROUTE-002"], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "symptom not observed" in result.stderr


def test_analyze_fails_closed_when_a_logical_node_is_not_rendered(tmp_path: Path) -> None:
    original = ROOT / "example/auto-layout/01-linear.json"
    config = json.loads(original.read_text(encoding="utf-8"))
    config["unrendered_root"] = {"kind": "source"}
    input_path = tmp_path / "with-isolated-node.json"
    input_path.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "linear.svg"
    subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(original), "-l", str(ROOT / "drawio-lib"),
         "-o", str(output), "--crossing-style", "none"], cwd=ROOT, check=True,
    )
    try:
        oracle.analyze(input_path, output)
    except ValueError as exc:
        assert "missing=['unrendered_root']" in str(exc)
    else:
        raise AssertionError("missing rendered node escaped the oracle")


def test_generic_quality_cli_reports_every_node_edge_and_network(tmp_path: Path) -> None:
    input_path = ROOT / "example/auto-layout/01-linear.json"
    output = tmp_path / "linear.svg"
    report_path = tmp_path / "quality.json"
    subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path), "-l", str(ROOT / "drawio-lib"),
         "-o", str(output), "--crossing-style", "none"], cwd=ROOT, check=True,
    )
    result = subprocess.run(
        [sys.executable, str(QUALITY_ORACLE_PATH), "--input", str(input_path), "--svg", str(output),
         "--report", str(report_path)], cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(report["nodes"]) == report["totals"]["logical_nodes"]
    assert len(report["edges"]) == report["totals"]["logical_edges"]
    assert report["networks"]
    assert all("crossed_edge_count" in edge for edge in report["edges"])


def test_quality_oracle_keeps_output_ports_as_distinct_networks(tmp_path: Path) -> None:
    config = {
        "root": {"kind": "source"},
        "dual": {"kind": "pll2", "source": "root"},
        "clock_0": {"kind": "clock", "source": "dual[0]"},
        "clock_1": {"kind": "clock", "source": "dual[1]"},
    }
    input_path = tmp_path / "two-output-ports.json"
    output = tmp_path / "two-output-ports.svg"
    input_path.write_text(json.dumps(config), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path),
         "-l", str(ROOT / "drawio-lib"), "-o", str(output),
         "--crossing-style", "none"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = oracle.analyze(input_path, output)
    assert {key for key in report["networks"] if key.startswith("dual:")} == {
        "dual:0", "dual:1"
    }
