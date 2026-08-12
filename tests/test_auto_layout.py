from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

import pytest

from auto_layout import generate_layout, load_clock_tree, write_generated_drawio
from drawio_build import build_drawio_xml, junction_points
from drawio_decode import compress_diagram_payload, decompress_diagram_payload
from drawio_layout import apply_crossing_style
from layout_quality import inspect_drawio_quality
from pipeline import drawio_to_clock_tree


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock.xml"
SRC_DIR = ROOT / "src"
DRAW_EXAMPLE = ROOT / "example" / "draw.json"


def _linear_config() -> dict[str, dict[str, str]]:
    return {
        "xtal": {"kind": "source", "source_kind": "source"},
        "gate0": {"kind": "gate", "source": "xtal"},
        "clk0": {"kind": "clock", "source": "gate0"},
    }


def test_draw_example_covers_one_shape_per_component_kind() -> None:
    config = load_clock_tree(DRAW_EXAMPLE)
    assert all(set(item) <= {"kind", "source"} for item in config.values())
    assert all("kind" in item for item in config.values())
    document, report = generate_layout(config, library_path=LIBRARY)

    assert report["hard_pass"] is True
    assert report["component_types"] == {
        "clock_cell": "cell",
        "clock_gate": "gate",
        "clock_select": "mux2",
        "core_clock": "clock",
        "divider": "div",
        "external_clk": "from",
        "inverter": "inv",
        "osc": "source",
        "pll_main": "pll",
        "tuner": "dto",
    }
    assert len(document.vertices) == 10
    assert len(document.edges) == 9


def test_draw_requires_kind_even_with_explicit_component() -> None:
    config = {"osc": {"component": "source"}}

    with pytest.raises(ValueError, match="器件 osc 缺少 kind"):
        generate_layout(config, library_path=LIBRARY)


def test_linear_layout_is_deterministic_and_roundtrips(tmp_path: Path) -> None:
    config = _linear_config()
    first, report = generate_layout(config, library_path=LIBRARY)
    second, _ = generate_layout(config, library_path=LIBRARY)

    assert report["hard_pass"] is True
    assert report["crossings"] == 0
    assert report["node_overlaps"] == 0
    assert build_drawio_xml(first) == build_drawio_xml(second)

    output = write_generated_drawio(first, tmp_path / "linear.drawio")
    assert drawio_to_clock_tree([output], library_path=LIBRARY) == config


def test_mux_uses_inferred_variant_and_exact_input_ports() -> None:
    config = {
        "a": {"kind": "source", "source_kind": "source"},
        "b": {"kind": "source", "source_kind": "source"},
        "m": {"kind": "mux", "source": {"0": "a", "1": "b"}},
        "clk": {"kind": "clock", "source": "m"},
    }
    document, report = generate_layout(config, library_path=LIBRARY)

    types = {vertex.name: vertex.drawclock_type for vertex in document.vertices}
    assert types["m"] == "mux2"
    mux_edges = [edge for edge in document.edges if edge.target_id == "n4"]
    assert {"entryY=0.24", "entryY=0.688"} <= {
        part
        for edge in mux_edges
        for part in edge.style.split(";")
    }
    assert report["hard_pass"] is True


def test_same_port_fanout_gets_decorative_junctions_without_changing_topology(
    tmp_path: Path,
) -> None:
    config = {
        "src": {"kind": "source", "source_kind": "source"},
        "gate": {"kind": "gate", "source": "src"},
        "clk_a": {"kind": "clock", "source": "gate"},
        "clk_b": {"kind": "clock", "source": "gate"},
    }
    document, _ = generate_layout(config, library_path=LIBRARY)
    assert junction_points(document)
    output = write_generated_drawio(document, tmp_path / "fanout.drawio")
    xml = output.read_text(encoding="utf-8")
    assert 'id="junction-1"' in xml
    assert drawio_to_clock_tree([output], library_path=LIBRARY) == config


def test_pll_uses_smallest_compatible_library_shape() -> None:
    config = {
        "xtal": {"kind": "source", "source_kind": "source"},
        "pll0": {"kind": "pll", "pll_kind": "SC", "source": "xtal"},
        "clk0": {"kind": "clock", "source": "pll0"},
    }
    document, report = generate_layout(config, library_path=LIBRARY)
    assert {vertex.name: vertex.drawclock_type for vertex in document.vertices}["pll0"] == "pll"
    assert report["hard_pass"] is True


def test_dense_example_meets_hard_gates_and_runtime_budget() -> None:
    config = json.loads(
        (ROOT / "example" / "auto-layout" / "05-dense-cross-root.json").read_text(
            encoding="utf-8"
        )
    )
    _, report = generate_layout(config, library_path=LIBRARY)

    assert report["hard_pass"] is True
    assert report["edge_node_intersections"] == 0
    assert report["ambiguous_overlaps"] == 0
    assert report["runtime_ms"] < 5000


def test_95_node_tree_stays_within_bounded_runtime() -> None:
    config: dict[str, dict[str, str]] = {
        "root": {"kind": "source", "source_kind": "source"}
    }
    level = ["root"]
    for _ in range(5):
        next_level: list[str] = []
        for parent in level:
            for side in ("a", "b"):
                name = f"{parent}_{side}"
                config[name] = {"kind": "gate", "source": parent}
                next_level.append(name)
        level = next_level
    for index, parent in enumerate(level):
        config[f"clk_{index:02d}"] = {"kind": "clock", "source": parent}

    _, report = generate_layout(
        config,
        library_path=LIBRARY,
        candidate_limit=4,
    )
    assert report["nodes"] == 95
    assert report["hard_pass"] is True
    assert report["crossings"] == 0
    assert report["runtime_ms"] < 15000


def test_draw_cli_writes_single_svg_output(tmp_path: Path) -> None:
    output = tmp_path / "linear.svg"
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "draw",
            "-i",
            str(ROOT / "example" / "auto-layout" / "01-linear.json"),
            "-l",
            str(LIBRARY),
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert output.is_file()
    assert output.read_text(encoding="utf-8").startswith("<?xml")


@pytest.mark.parametrize("style", ["arc", "gap", "sharp", "none"])
def test_crossing_style_replaces_the_existing_jump_policy(style: str) -> None:
    document, _ = generate_layout(_linear_config(), library_path=LIBRARY)
    apply_crossing_style(document, style)
    for edge in document.edges:
        if style == "none":
            assert "jumpStyle=" not in edge.style
            assert "jumpSize=" not in edge.style
        else:
            assert f"jumpStyle={style};" in edge.style
            assert "jumpSize=6;" in edge.style


@pytest.mark.skipif(
    not Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe").is_file(),
    reason="PNG integration requires Microsoft Edge",
)
def test_json_to_drawio_cli_writes_real_component_png(tmp_path: Path) -> None:
    output = tmp_path / "linear.png"
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "draw",
            "-i",
            str(ROOT / "example" / "auto-layout" / "01-linear.json"),
            "-l",
            str(LIBRARY),
            "-o",
            str(output),
            "--crossing-style",
            "gap",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.skipif(
    not Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe").is_file(),
    reason="PNG integration requires Microsoft Edge",
)
def test_draw_cli_writes_png_to_relative_output_path(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "draw",
            "-i",
            str(DRAW_EXAMPLE),
            "-l",
            str(LIBRARY),
            "-o",
            "relative.png",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "relative.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_agent_quality_facilities_are_not_public_cli_features() -> None:
    root_help = subprocess.run(
        [sys.executable, str(SRC_DIR), "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    generate_help = subprocess.run(
        [sys.executable, str(SRC_DIR), "draw", "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert "quality-check" not in root_help
    assert "--report" not in generate_help
    for removed in (
        "--profile",
        "--engine",
        "--candidates",
        "--hints",
        "--preview",
        "--preview-format",
        "--preview-max-size",
    ):
        assert removed not in generate_help


@pytest.mark.parametrize(
    ("suffix", "content"),
    [
        (".json", '{"晶振":{"kind":"source","source_kind":"source"}}'),
        (".jsonc", '{// clock source\n"晶振":{"kind":"source","source_kind":"source"}}'),
        (".json5", "{'晶振':{kind:'source',source_kind:'source'}}"),
        (".toml", '["晶振"]\nkind="source"\nsource_kind="source"\n'),
        (".yaml", "晶振:\n  kind: source\n  source_kind: source\n"),
        (".ini", "[晶振]\nkind=source\nsource_kind=source\n"),
    ],
)
def test_clock_tree_input_formats(suffix: str, content: str, tmp_path: Path) -> None:
    source = tmp_path / f"clock-tree{suffix}"
    source.write_text(content, encoding="utf-8")
    assert load_clock_tree(source) == {
        "晶振": {"kind": "source", "source_kind": "source"}
    }


def test_draw_rejects_output_suffix_before_reading_inputs(tmp_path: Path) -> None:
    output = tmp_path / "clock-tree.bmp"
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "draw",
            "-i",
            str(tmp_path / "missing.json"),
            "-l",
            str(tmp_path / "missing.xml"),
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "支持：.drawio, .svg, .png" in proc.stderr
    assert not output.exists()


def test_layout_uses_kind_metadata_and_geometry_from_supplied_library(
    tmp_path: Path,
) -> None:
    text = LIBRARY.read_text(encoding="utf-8").strip()
    entries = json.loads(text[len("<mxlibrary>") : -len("</mxlibrary>")])
    for entry in entries:
        if entry.get("title") == "gate":
            entry["title"] = "custom_gate_symbol"
            entry["w"] = 83
            entry["h"] = 91
            graph_xml = decompress_diagram_payload(entry["xml"])
            graph_xml = graph_xml.replace(
                "drawclockType=gate;", "drawclockType=custom_gate_symbol;"
            )
            entry["xml"] = compress_diagram_payload(graph_xml)
            break
    custom_library = tmp_path / "custom.xml"
    custom_library.write_text(
        "<mxlibrary>" + json.dumps(entries) + "</mxlibrary>", encoding="utf-8"
    )

    document, report = generate_layout(_linear_config(), library_path=custom_library)
    gate = next(vertex for vertex in document.vertices if vertex.name == "gate0")
    assert gate.drawclock_type == "custom_gate_symbol"
    assert (gate.width, gate.height) == (83, 91)
    assert report["hard_pass"] is True


def _generated_linear_artifact(tmp_path: Path) -> tuple[Path, Path]:
    config_path = tmp_path / "linear.json"
    config_path.write_text(json.dumps(_linear_config()), encoding="utf-8")
    document, _ = generate_layout(_linear_config(), library_path=LIBRARY)
    drawio_path = write_generated_drawio(document, tmp_path / "linear.drawio")
    return config_path, drawio_path


def _mutate_drawio(path: Path, mutation) -> None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    mutation(root)
    path.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")


def test_artifact_quality_accepts_exact_generated_file(tmp_path: Path) -> None:
    config_path, drawio_path = _generated_linear_artifact(tmp_path)
    report = inspect_drawio_quality(config_path, drawio_path, library_path=LIBRARY)

    assert report["passed"] is True
    assert report["alignment"]["port_alignment_error_max_px"] == 0
    assert report["line_integrity"]["expected_edges"] == 2
    assert report["layout_order"]["direction_violations"] == []


def test_artifact_quality_rejects_wrong_port_attachment(tmp_path: Path) -> None:
    config_path, drawio_path = _generated_linear_artifact(tmp_path)

    def wrong_port(root: ET.Element) -> None:
        edge = next(cell for cell in root.iter("mxCell") if cell.get("edge") == "1")
        before = edge.get("style", "")
        after = before.replace("exitY=0.5455", "exitY=0.1")
        assert after != before
        edge.set("style", after)

    _mutate_drawio(drawio_path, wrong_port)
    report = inspect_drawio_quality(config_path, drawio_path, library_path=LIBRARY)

    assert report["passed"] is False
    assert report["line_integrity"]["unresolved_port_edges"]


def test_artifact_quality_rejects_diagonal_segment(tmp_path: Path) -> None:
    config_path, drawio_path = _generated_linear_artifact(tmp_path)

    def diagonal(root: ET.Element) -> None:
        edge = next(cell for cell in root.iter("mxCell") if cell.get("edge") == "1")
        geometry = edge.find("mxGeometry")
        assert geometry is not None
        array = ET.SubElement(geometry, "Array", {"as": "points"})
        ET.SubElement(array, "mxPoint", {"x": "150", "y": "67"})
        ET.SubElement(array, "mxPoint", {"x": "200", "y": "60"})

    _mutate_drawio(drawio_path, diagonal)
    report = inspect_drawio_quality(config_path, drawio_path, library_path=LIBRARY)

    assert report["passed"] is False
    assert report["line_integrity"]["non_orthogonal_segments"]


def test_artifact_quality_rejects_missing_and_duplicate_edges(tmp_path: Path) -> None:
    config_path, drawio_path = _generated_linear_artifact(tmp_path)

    def missing_and_duplicate(root: ET.Element) -> None:
        graph_root = root.find("./diagram/mxGraphModel/root")
        assert graph_root is not None
        edges = [cell for cell in graph_root.findall("mxCell") if cell.get("edge") == "1"]
        graph_root.remove(edges[0])
        duplicate = deepcopy(edges[1])
        duplicate.set("id", "duplicate-edge")
        graph_root.append(duplicate)

    _mutate_drawio(drawio_path, missing_and_duplicate)
    report = inspect_drawio_quality(config_path, drawio_path, library_path=LIBRARY)

    assert report["passed"] is False
    assert report["line_integrity"]["missing_edges"]
    assert report["line_integrity"]["duplicate_edges"]


def test_artifact_quality_rejects_skewed_rank(tmp_path: Path) -> None:
    config = {
        "src": {"kind": "source", "source_kind": "source"},
        "a": {"kind": "gate", "source": "src"},
        "b": {"kind": "gate", "source": "src"},
    }
    config_path = tmp_path / "branch.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    document, _ = generate_layout(config, library_path=LIBRARY)
    drawio_path = write_generated_drawio(document, tmp_path / "branch.drawio")

    def skew(root: ET.Element) -> None:
        obj = next(obj for obj in root.iter("object") if obj.get("name") == "a")
        geometry = obj.find("./mxCell/mxGeometry")
        assert geometry is not None
        geometry.set("x", str(float(geometry.get("x", "0")) + 10))

    _mutate_drawio(drawio_path, skew)
    report = inspect_drawio_quality(config_path, drawio_path, library_path=LIBRARY)

    assert report["passed"] is False
    assert report["alignment"]["rank_x_spread_max_px"] == 10


def test_invalid_output_selector_is_rejected() -> None:
    config = {
        "xtal": {"kind": "source", "source_kind": "source"},
        "clk": {"kind": "clock", "source": "xtal[9]"},
    }
    with pytest.raises(ValueError, match="无效输出口"):
        generate_layout(config, library_path=LIBRARY)
