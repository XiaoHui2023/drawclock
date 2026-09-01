from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from auto_layout import generate_layout, load_clock_tree
from drawio_library import load_library_shapes
from elk_layout import generate_elk_layout
from library_payload import compress_diagram_payload, decompress_diagram_payload
from drawio_layout import apply_crossing_style, layout_to_dict
from layout_preview import junction_points
from layout_quality import inspect_layout_quality


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "drawio-lib" / "drawclock"
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


@pytest.mark.parametrize("value", ["", "select", True, 1.5, [20]])
def test_layout_column_rejects_invalid_values(value: object) -> None:
    config = {"osc": {"kind": "source", "layout_column": value}}

    with pytest.raises(
        ValueError,
        match="layout_column 必须是整数",
    ):
        generate_elk_layout(config, library_path=LIBRARY)


@pytest.mark.parametrize("field", ["func_freq", "scan_freq", "bist_freq"])
@pytest.mark.parametrize("value", [None, True, [], {}])
def test_frequency_fields_reject_non_display_scalars(
    field: str, value: object,
) -> None:
    config = {"clk": {"kind": "clock", field: value}}

    with pytest.raises(ValueError, match=rf"{field} 必须是字符串或数字"):
        generate_elk_layout(config, library_path=LIBRARY)


def test_frequency_fields_accept_strings_numbers_and_omission() -> None:
    config = {
        "source": {"kind": "source"},
        "clk_a": {
            "kind": "clock", "source": "source",
            "func_freq": "800 MHz", "scan_freq": 50, "bist_freq": 125.5,
        },
        "clk_b": {"kind": "clock", "source": "source"},
    }

    document, _ = generate_elk_layout(config, library_path=LIBRARY)

    attrs = {vertex.name: vertex.object_attrs for vertex in document.vertices}
    assert attrs["clk_a"]["func_freq"] == "800 MHz"
    assert attrs["clk_a"]["scan_freq"] == "50"
    assert attrs["clk_a"]["bist_freq"] == "125.5"
    assert "func_freq" not in attrs["clk_b"]
    terminals = [vertex for vertex in document.vertices if vertex.name.startswith("clk_")]
    assert len({vertex.x for vertex in terminals}) == 1
    assert len({vertex.y for vertex in terminals}) == len(terminals)


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


def test_clock_tree_accepts_strict_json_with_utf8_bom(tmp_path: Path) -> None:
    source = tmp_path / "clock-tree.json"
    source.write_text(
        '{"晶振":{"kind":"source","source_kind":"source"}}',
        encoding="utf-8-sig",
    )
    assert load_clock_tree(source) == {
        "晶振": {"kind": "source", "source_kind": "source"}
    }


@pytest.mark.parametrize("suffix", [".jsonc", ".json5", ".toml", ".yaml", ".ini"])
def test_clock_tree_rejects_non_json_suffixes(suffix: str, tmp_path: Path) -> None:
    source = tmp_path / f"clock-tree{suffix}"
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match=r"只支持：\.json"):
        load_clock_tree(source)


def test_clock_tree_rejects_json_comments_and_non_object_root(tmp_path: Path) -> None:
    commented = tmp_path / "commented.json"
    commented.write_text('{// comment\n"osc": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="无法读取拓扑配置"):
        load_clock_tree(commented)
    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON 顶层必须是对象"):
        load_clock_tree(array)


def _write_split_library(path: Path, titles: set[str]) -> None:
    assert len(titles) == 1
    title = next(iter(titles))
    source = LIBRARY / f"{title}.xml"
    assert source.is_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, path)


def test_multiple_library_files_and_directories_merge_for_layout(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    source_file = first_dir / "source.xml"
    gate_file = second_dir / "nested" / "gate.xml"
    clock_file = tmp_path / "clock.xml"
    _write_split_library(source_file, {"source"})
    _write_split_library(gate_file, {"gate"})
    _write_split_library(clock_file, {"clock"})

    libraries = [first_dir, clock_file, second_dir, clock_file]
    shapes = load_library_shapes(libraries)
    assert set(shapes) == {"source", "gate", "clock"}
    document, _ = generate_elk_layout(_linear_config(), library_path=libraries)
    assert len(document.vertices) == 3


def test_component_identity_comes_from_title_not_filename(tmp_path: Path) -> None:
    renamed = tmp_path / "arbitrary-name.xml"
    _write_split_library(renamed, {"source"})
    assert set(load_library_shapes(renamed)) == {"source"}


def test_multiple_library_inputs_reject_invalid_paths_and_duplicate_titles(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="没有 XML"):
        load_library_shapes(empty)
    with pytest.raises(FileNotFoundError, match="路径不存在"):
        load_library_shapes(tmp_path / "missing")
    wrong = tmp_path / "library.txt"
    wrong.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="必须是 XML"):
        load_library_shapes(wrong)

    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"
    _write_split_library(first, {"source"})
    _write_split_library(second, {"source"})
    with pytest.raises(ValueError, match="重复 title source"):
        load_library_shapes([first, second])

    combined = tmp_path / "combined.xml"
    source_entry = json.loads(
        (LIBRARY / "source.xml").read_text(encoding="utf-8").strip()[
            len("<mxlibrary>") : -len("</mxlibrary>")
        ]
    )[0]
    clock_entry = json.loads(
        (LIBRARY / "clock.xml").read_text(encoding="utf-8").strip()[
            len("<mxlibrary>") : -len("</mxlibrary>")
        ]
    )[0]
    combined.write_text(
        "<mxlibrary>"
        + json.dumps([source_entry, clock_entry], ensure_ascii=False)
        + "</mxlibrary>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="只包含一个器件"):
        load_library_shapes(combined)

    unwrapped = tmp_path / "unwrapped.xml"
    unwrapped.write_text(json.dumps([source_entry]), encoding="utf-8")
    with pytest.raises(ValueError, match="标准 mxlibrary 包装"):
        load_library_shapes(unwrapped)


def test_cli_accepts_repeated_mixed_library_files_and_directories(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    clock_file = tmp_path / "clock.xml"
    _write_split_library(first_dir / "source.xml", {"source"})
    _write_split_library(second_dir / "nested" / "gate.xml", {"gate"})
    _write_split_library(clock_file, {"clock"})
    input_path = tmp_path / "linear.json"
    input_path.write_text(json.dumps(_linear_config()), encoding="utf-8")
    output = tmp_path / "mixed-libraries.svg"
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR),
            "-i",
            str(input_path),
            "-l",
            str(first_dir),
            str(clock_file),
            "-l",
            str(second_dir),
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "<svg " in output.read_text(encoding="utf-8")


def test_layout_uses_kind_metadata_and_geometry_from_supplied_library(
    tmp_path: Path,
) -> None:
    custom_library = tmp_path / "custom"
    shutil.copytree(LIBRARY, custom_library)
    gate_library = custom_library / "gate.xml"
    text = gate_library.read_text(encoding="utf-8").strip()
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
    (custom_library / "custom-gate.xml").write_text(
        "<mxlibrary>" + json.dumps(entries) + "</mxlibrary>", encoding="utf-8"
    )
    gate_library.unlink()

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

    asymmetric = {
        "input_a": {"kind": "from"},
        "input_b": {"kind": "from"},
        "logic_a": {
            "kind": "custom_gate_symbol",
            "source": "input_a",
        },
        "logic_b": {
            "kind": "custom_gate_symbol",
            "source": "input_b",
        },
        "divide_b": {"kind": "div", "source": "logic_b"},
        "select": {
            "kind": "mux2",
            "source": {"0": "logic_a", "1": "divide_b"},
        },
        "output": {"kind": "clock", "source": "select"},
        "tap": {"kind": "clock", "source": "logic_a"},
    }
    asymmetric_document, _ = generate_elk_layout(
        asymmetric,
        library_path=custom_library,
    )
    asymmetric_quality = inspect_layout_quality(
        asymmetric,
        asymmetric_document,
        library_path=custom_library,
        grid=0.0001,
        tolerance=0.01,
    )
    assert asymmetric_quality["line_integrity"][
        "avoidable_exclusive_chain_bend_edges"
    ] == []
    assert asymmetric_quality["passed"] is True


def test_invalid_output_selector_is_rejected() -> None:
    config = {
        "xtal": {"kind": "source", "source_kind": "source"},
        "clk": {"kind": "clock", "source": "xtal[9]"},
    }
    with pytest.raises(ValueError, match="无效输出口"):
        generate_layout(config, library_path=LIBRARY)
