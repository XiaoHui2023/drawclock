from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import svg_graph_inspector as inspector
import svg_quality_system as quality
from search_recurrent_mux_bends import build_case as build_mux_case


BAD_SVG = ROOT / ".reproduction" / "evidence" / "20260908T122300-public-from-dispersed-current" / "attempt-1" / "output.svg"
INPUT = ROOT / "tests" / "reproduction-corpus" / "pad-r08-s02.json"


def test_inspector_reports_complete_public_from_geometry() -> None:
    report = inspector.inspect(INPUT, BAD_SVG)
    node = next(item for item in report["nodes"] if item["id"] == "public_from")
    network = next(item for item in report["networks"] if item["id"] == "public_from:right")
    assert node["physical_rendering_count"] == 5
    assert len(node["outgoing_edge_ids"]) == 5
    assert network["fanout"] == 5
    assert network["physical_source_facilities"] == 5
    assert network["vertical_channel_xs"] == []
    assert all("bend_points" in edge and "segments" in edge and "crossings" in edge for edge in report["edges"])


def test_every_artifact_executes_exact_complete_registry() -> None:
    report = quality.evaluate(INPUT, BAD_SVG)
    assert report["executed_metric_ids"] == report["required_metric_ids"]
    assert len(report["executed_metric_ids"]) == len(set(report["executed_metric_ids"]))
    assert "shared_root_single_bus" in report["failed_metric_ids"]
    by_id = {item["metric_id"]: item for item in report["metric_results"]}
    assert by_id["annotation_geometry"]["status"] == "not_applicable"
    assert by_id["annotation_geometry"]["applicability_proof"] == "annotations=0"
    assert "feasible_direct_root_fanin_column" in report["executed_metric_ids"]


def test_quality_cli_rejects_known_bad_artifact(tmp_path: Path) -> None:
    receipt = tmp_path / "quality.json"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/svg_quality_system.py"),
         "--input", str(INPUT), "--svg", str(BAD_SVG),
         "--registry", str(quality.DEFAULT_REGISTRY),
         "--output", str(receipt)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 1
    report = json.loads(receipt.read_text(encoding="utf-8"))
    assert report["executed_metric_ids"] == report["required_metric_ids"]
    assert len(report["executed_metric_ids"]) == 25
    assert report["failed_metric_ids"]


def test_registry_rejects_duplicate_or_missing_identity(tmp_path: Path) -> None:
    source = json.loads(quality.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    source["metrics"].append(dict(source["metrics"][0]))
    target = tmp_path / "bad-registry.json"
    target.write_text(json.dumps(source), encoding="utf-8")
    try:
        quality.load_registry(target)
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate metric id escaped")


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "duplicate", "reordered", "unreceipted"]
)
def test_exact_metric_receipt_rejects_escape_mutants(mutation: str) -> None:
    required = ["identity", "geometry", "routing"]
    executed = list(required)
    results = [{"metric_id": item} for item in required]
    if mutation == "missing":
        executed.pop()
        results.pop()
    elif mutation == "extra":
        executed.append("invented")
        results.append({"metric_id": "invented"})
    elif mutation == "duplicate":
        executed.append("routing")
        results.append({"metric_id": "routing"})
    elif mutation == "reordered":
        executed[0], executed[1] = executed[1], executed[0]
        results[0], results[1] = results[1], results[0]
    else:
        results.pop()
    with pytest.raises(ValueError):
        quality.validate_metric_receipt(required, executed, results)


def test_shared_bus_root_detection_is_name_independent_and_structural() -> None:
    module_path = ROOT / "src" / "elk_layout.py"
    spec = importlib.util.spec_from_file_location(
        "elk_layout_for_shared_bus_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    class Node:
        def __init__(self, kind: str):
            self.item = {"kind": kind}

    nodes = {
        name: Node(kind)
        for name, kind in {
            "arbitrary": "from", "a": "mux2", "b": "clock"
        }.items()
    }
    edges = [
        SimpleNamespace(source="arbitrary", target="a", target_port="0", source_port="west"),
        SimpleNamespace(source="arbitrary", target="b", target_port="left", source_port="west"),
    ]
    assert module._shared_fanout_bus_roots(nodes, edges) == set()
    nodes["arbitrary"].item["kind"] = "gate"
    assert module._shared_fanout_bus_roots(nodes, edges) == set()

    nodes = {
        name: Node(kind)
        for name, kind in {
            "shared": "from",
            "peer_a": "source",
            "peer_b": "source",
            "merge_a": "mux2",
            "merge_b": "mux2",
        }.items()
    }
    edges = [
        SimpleNamespace(source="shared", target="merge_a", target_port="0", source_port="west"),
        SimpleNamespace(source="peer_a", target="merge_a", target_port="1", source_port="west"),
        SimpleNamespace(source="shared", target="merge_b", target_port="0", source_port="west"),
        SimpleNamespace(source="peer_b", target="merge_b", target_port="1", source_port="west"),
    ]
    assert module._shared_fanout_bus_roots(nodes, edges) == {"shared"}


@pytest.mark.parametrize("seed", [0, 2, 3, 12, 24])
def test_adversarial_from_mux_seeds_preserve_all_quality_metrics(
    seed: int, tmp_path: Path
) -> None:
    config = build_mux_case(seed)
    for item in config.values():
        if item.get("kind") == "source":
            item["kind"] = "from"
            item.pop("source_kind", None)
    input_path = tmp_path / f"seed-{seed}.json"
    svg_path = tmp_path / f"seed-{seed}.svg"
    input_path.write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "src"), "-i", str(input_path),
         "-l", str(ROOT / "drawio-lib"), "-o", str(svg_path),
         "--crossing-style", "arc"],
        cwd=ROOT, check=True, capture_output=True,
    )
    report = quality.evaluate(input_path, svg_path)
    assert report["executed_metric_ids"] == report["required_metric_ids"]
    assert report["failed_metric_ids"] == []


def test_topology_identity_rejects_unknown_rendered_node(tmp_path: Path) -> None:
    text = BAD_SVG.read_text(encoding="utf-8")
    ghost = (
        '<g class="component" data-node-id="untrusted_ghost">'
        '<svg class="component-graphic" x="1" y="1" width="1" height="1"/>'
        '</g>'
    )
    mutant = tmp_path / "unexpected-node.svg"
    head, tail = text.rsplit("</svg>", 1)
    mutant.write_text(head + ghost + "</svg>" + tail, encoding="utf-8")
    witnesses = quality._artifact_metric_witnesses(INPUT, mutant)
    assert witnesses["topology_identity"]["unexpected_nodes"] == [
        "untrusted_ghost"
    ]
    with pytest.raises(ValueError, match="component identity mismatch"):
        quality.evaluate(INPUT, mutant)


def test_orthogonal_segments_rejects_diagonal_polyline(tmp_path: Path) -> None:
    text = BAD_SVG.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(<polyline class="edge" points="[-0-9.]+,)([-0-9.]+)'
        r'( [-0-9.]+,)([-0-9.]+)'
    )
    match = pattern.search(text)
    assert match is not None
    diagonal_y = str(float(match.group(4)) + 1.0)
    text = text[:match.start()] + (
        match.group(1) + match.group(2) + match.group(3) + diagonal_y
    ) + text[match.end():]
    mutant = tmp_path / "diagonal-segment.svg"
    mutant.write_text(text, encoding="utf-8")
    report = quality.evaluate(INPUT, mutant)
    result = next(
        item for item in report["metric_results"]
        if item["metric_id"] == "orthogonal_segments"
    )
    assert result["status"] == "fail"
    assert result["witnesses"]


def _write_crossing_fixture(
    tmp_path: Path, horizontal: str, vertical: str, *, junction: bool = False,
) -> tuple[Path, Path]:
    input_path = tmp_path / "crossing.json"
    svg_path = tmp_path / "crossing.svg"
    input_path.write_text(json.dumps({
        "a": {"kind": "source"},
        "b": {"kind": "clock", "source": "a"},
        "c": {"kind": "source"},
        "d": {"kind": "clock", "source": "c"},
    }), encoding="utf-8")
    dot = '<circle cx="50" cy="50" r="3" fill="#000000"/>' if junction else ""
    svg_path.write_text(
        '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="component" data-node-id="a"><svg class="component-graphic" x="0" y="45" width="10" height="10"/></g>'
        '<g class="component" data-node-id="b"><svg class="component-graphic" x="90" y="45" width="10" height="10"/></g>'
        '<g class="component" data-node-id="c"><svg class="component-graphic" x="45" y="0" width="10" height="10"/></g>'
        '<g class="component" data-node-id="d"><svg class="component-graphic" x="45" y="90" width="10" height="10"/></g>'
        f'{horizontal}{vertical}{dot}</svg>', encoding="utf-8",
       )
    return input_path, svg_path


@pytest.mark.parametrize(
    ("horizontal", "vertical", "junction", "expected_kind"),
    [
        ('<polyline class="edge" points="10,50 90,50"/>',
         '<polyline class="edge" points="50,10 50,90"/>', False, "missing_bridge"),
        ('<path class="edge" d="M 10 50 L 46 50 A 4 4 0 0 0 54 50 L 90 50"/>',
         '<path class="edge" d="M 50 10 L 50 46 A 4 4 0 0 0 50 54 L 50 90"/>', False, "multiple_bridges"),
        ('<polyline class="edge" points="10,50 90,50"/>',
         '<polyline class="edge" points="50,10 50,90"/>', True, "junction_at_different_net_crossing"),
        ('<path class="edge" d="M 10 50 L 26 50 A 4 4 0 0 0 34 50 L 90 50"/>',
         '<polyline class="edge" points="50,10 50,90"/>', False, "orphan_bridge"),
    ],
)
def test_crossing_treatment_rejects_bridge_mutants(
    tmp_path: Path, horizontal: str, vertical: str,
    junction: bool, expected_kind: str,
) -> None:
    input_path, svg_path = _write_crossing_fixture(
        tmp_path, horizontal, vertical, junction=junction,
    )
    report = quality.evaluate(input_path, svg_path)
    metric = next(
        item for item in report["metric_results"]
        if item["metric_id"] == "crossing_treatment"
    )
    assert metric["status"] == "fail"
    assert expected_kind in {row["kind"] for row in metric["witnesses"]}


def test_crossing_treatment_accepts_exactly_one_bridge(tmp_path: Path) -> None:
    input_path, svg_path = _write_crossing_fixture(
        tmp_path,
        '<path class="edge" d="M 10 50 L 46 50 A 4 4 0 0 0 54 50 L 90 50"/>',
        '<polyline class="edge" points="50,10 50,90"/>',
    )
    report = quality.evaluate(input_path, svg_path)
    metric = next(
        item for item in report["metric_results"]
        if item["metric_id"] == "crossing_treatment"
    )
    assert metric["status"] == "pass"
    assert metric["witnesses"] == []
