from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from auto_layout import generate_layout, load_clock_tree
from elk_layout import generate_elk_layout
from library_payload import compress_diagram_payload, decompress_diagram_payload
from drawio_layout import apply_crossing_style, layout_to_dict
from layout_preview import junction_points
from layout_quality import inspect_layout_quality


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


def test_linear_layout_is_deterministic() -> None:
    config = _linear_config()
    first, report = generate_layout(config, library_path=LIBRARY)
    second, _ = generate_layout(config, library_path=LIBRARY)

    assert report["hard_pass"] is True
    assert report["crossings"] == 0
    assert report["node_overlaps"] == 0
    assert layout_to_dict(first) == layout_to_dict(second)


@pytest.mark.parametrize(
    ("sources", "expected_entry_y"),
    [
        ({"0": "a"}, {"entryY=0.24"}),
        ({"1": "b"}, {"entryY=0.688"}),
        ({"0": "a", "1": "b"}, {"entryY=0.24", "entryY=0.688"}),
    ],
)
def test_mux_kind_is_exact_and_unconnected_inputs_are_allowed(
    sources: dict[str, str], expected_entry_y: set[str]
) -> None:
    config = {
        "a": {"kind": "source", "source_kind": "source"},
        "b": {"kind": "source", "source_kind": "source"},
        "m": {"kind": "mux2", "source": sources},
        "clk": {"kind": "clock", "source": "m"},
    }
    document, report = generate_layout(config, library_path=LIBRARY)

    types = {vertex.name: vertex.drawclock_type for vertex in document.vertices}
    assert types["m"] == "mux2"
    mux_edges = [edge for edge in document.edges if edge.target_id == "n4"]
    assert expected_entry_y == {
        part
        for edge in mux_edges
        for part in edge.style.split(";")
        if part.startswith("entryY=")
    }
    assert report["hard_pass"] is True


def test_generic_mux_kind_is_not_guessed_from_connected_ports() -> None:
    config = {
        "a": {"kind": "source"},
        "m": {"kind": "mux", "source": {"0": "a"}},
    }

    with pytest.raises(ValueError, match="kind=mux 不在当前器件库中"):
        generate_layout(config, library_path=LIBRARY)


def test_same_port_fanout_gets_decorative_junctions() -> None:
    config = {
        "src": {"kind": "source", "source_kind": "source"},
        "gate": {"kind": "gate", "source": "src"},
        "clk_a": {"kind": "clock", "source": "gate"},
        "clk_b": {"kind": "clock", "source": "gate"},
    }
    document, _ = generate_layout(config, library_path=LIBRARY)
    assert junction_points(document)


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


@pytest.mark.parametrize("filename", ["linear.svg", "linear.png", "linear.drawio", "linear"])
def test_draw_always_writes_svg_regardless_of_output_suffix(
    filename: str, tmp_path: Path
) -> None:
    output = tmp_path / filename
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
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
    assert output.read_text(encoding="utf-8").startswith("<?xml")


def test_draw_cli_writes_svg_to_relative_arbitrary_path(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "-i",
            str(DRAW_EXAMPLE),
            "-l",
            str(LIBRARY),
            "-o",
            "relative.output",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "relative.output").read_text(encoding="utf-8").startswith(
        "<?xml"
    )


def test_agent_quality_facilities_are_not_public_cli_features() -> None:
    root_help = subprocess.run(
        [sys.executable, str(SRC_DIR), "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "quality-check" not in root_help
    assert "extract" not in root_help
    assert "reload" not in root_help
    assert "--report" not in root_help
    for removed in (
        "--profile",
        "--engine",
        "--candidates",
        "--hints",
        "--preview",
        "--preview-format",
        "--preview-max-size",
    ):
        assert removed not in root_help


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

    config = _linear_config()
    config["gate0"]["kind"] = "custom_gate_symbol"
    document, report = generate_layout(config, library_path=custom_library)
    gate = next(vertex for vertex in document.vertices if vertex.name == "gate0")
    assert gate.drawclock_type == "custom_gate_symbol"
    assert (gate.width, gate.height) == (83, 91)
    assert "gate0" in gate.object_attrs["label"]
    assert report["hard_pass"] is True
    production_document, _ = generate_elk_layout(
        config,
        library_path=custom_library,
    )
    quality = inspect_layout_quality(
        config,
        production_document,
        library_path=custom_library,
        grid=0.0001,
        tolerance=0.01,
    )
    assert quality["passed"] is True
    assert quality["alignment"]["port_alignment_error_max_px"] == 0


def test_invalid_output_selector_is_rejected() -> None:
    config = {
        "xtal": {"kind": "source", "source_kind": "source"},
        "clk": {"kind": "clock", "source": "xtal[9]"},
    }
    with pytest.raises(ValueError, match="无效输出口"):
        generate_layout(config, library_path=LIBRARY)
