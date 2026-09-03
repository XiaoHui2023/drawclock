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
    assert report["detected_issues"] == []
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


def test_default_arc_combined_example_has_no_feedback_witness(tmp_path: Path) -> None:
    input_path = ROOT / "example/auto-layout/26-feedback-reproduction-combined.json"
    output = tmp_path / "combined-default-arc.svg"
    result = subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path),
         "-l", str(ROOT / "drawio-lib"), "-o", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = oracle.analyze(input_path, output)
    assert report["totals"]["logical_nodes"] == 121
    assert report["totals"]["logical_edges"] == 122
    assert report["totals"]["different_net_overlaps"] == 0
    assert report["witnesses"]["split_rejoin_roots"] == []
    assert report["detected_issues"] == []


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
