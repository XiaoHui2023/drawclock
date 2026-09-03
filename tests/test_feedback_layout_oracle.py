from __future__ import annotations

import importlib.util
import json
import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORACLE_PATH = ROOT / "tools" / "feedback_layout_reproduction_oracle.py"
SPEC = importlib.util.spec_from_file_location("feedback_layout_oracle", ORACLE_PATH)
assert SPEC is not None and SPEC.loader is not None
oracle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = oracle
SPEC.loader.exec_module(oracle)


def test_oracle_source_has_no_production_import() -> None:
    tree = ast.parse(ORACLE_PATH.read_text(encoding="utf-8"))
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
    input_path = ROOT / "example" / "auto-layout" / "25-mixed-root-port-order-torture.json"
    output = tmp_path / "output.svg"
    result = subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path), "-l", str(ROOT / "drawio-lib"),
         "-o", str(output), "--crossing-style", "none"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = oracle.analyze(input_path, output)
    assert report["totals"]["logical_edges"] == report["totals"]["rendered_edges"] == 66
    assert report["totals"]["proper_crossing_events"] >= report["totals"]["distinct_crossing_points"]
    assert set(report["witnesses"]["mixed_root_kinds"]) == {"from", "gate", "source"}


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
