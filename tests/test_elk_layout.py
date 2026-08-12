from __future__ import annotations

import time
from pathlib import Path

import pytest

from auto_layout import load_clock_tree
from elk_layout import elk_layout_available, generate_elk_layout
from layout_quality import inspect_layout_quality


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
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
    assert len(document.vertices) == 1046
    assert len(document.edges) == 1300
    assert report["engine"] == "scalable-layered"
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
