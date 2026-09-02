from __future__ import annotations

import importlib.util
import copy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "clock-layout-algorithms" / "scripts" / "layout_statistics.py"


def _module():
    spec = importlib.util.spec_from_file_location("layout_statistics_tool", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_statistics_tool_covers_every_node_and_edge() -> None:
    module = _module()
    report = module.build_report(
        ROOT / "example" / "auto-layout" / "23-middle-column-low-use-sources.json",
        [ROOT / "drawio-lib" / "drawclock"],
    )
    statistics = report["statistics"]

    assert report["schema"] == 1
    assert statistics["totals"]["edges"] == len(statistics["edges"])
    assert len(statistics["nodes"]) == 44
    assert statistics["nodes"]["common_source"]["direct_downstream_nodes"] == 1
    assert statistics["nodes"]["common_stage_3"]["direct_downstream_nodes"] == 8
    assert statistics["nodes"]["local_source_00"]["direct_downstream_nodes"] == 1
    assert statistics["nodes"]["clock_00"]["is_terminal"] is True


def test_agent_statistics_tool_rejects_missing_node_and_edge_drift() -> None:
    module = _module()
    config_path = ROOT / "example" / "auto-layout" / "23-middle-column-low-use-sources.json"
    report = module.build_report(
        config_path, [ROOT / "drawio-lib" / "drawclock"]
    )
    config = __import__("json").loads(config_path.read_text(encoding="utf-8"))
    broken = copy.deepcopy(report["statistics"])
    del broken["nodes"]["clock_00"]
    broken["totals"]["edges"] -= 1

    errors = module.validate_statistics(broken, config, 43)

    assert "node statistics do not cover the input node set" in errors
    assert "edge statistics do not cover the generated edge set" in errors
