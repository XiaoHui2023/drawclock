from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest

ROOT = Path(__file__).resolve().parents[1]

from drawio_graph import _parse_points
from drawio_library import (
    DEFAULT_LIBRARY_PATH,
    load_library_cell_styles,
    load_library_shapes,
)
from drawio_ports import port_anchors
from pipeline import parse_drawio_paths

from kind_families import (
    ALL_VARIANT_TYPES,
    JSON_VARIANT_KEYS,
    STYLE_VARIANT_KEYS,
    VARIANT_FAMILIES,
)


def test_parse_points_reads_all_mux_ports() -> None:
    style = (
        "drawclockType=mux3;points=[[0.3500,0.2075,0,0,0],"
        "[0.3500,0.3585,0,0,0],[0.3500,0.5094,0,0,0],[0.6500,0.3585,0,0,0]];"
    )
    pts = _parse_points(style)
    assert len(pts) == 4
    assert pts[0] == (0.35, 0.2075)
    assert pts[-1] == (0.65, 0.3585)


def test_mini_tree_drawio() -> None:
    path = ROOT / "tests" / "fixtures" / "mini-tree.drawio"
    config = parse_drawio_paths([path])

    assert config["pll0"]["source"] == "xtal0"
    assert config["pll0"]["gap"] == "4"
    assert config["gate0"]["source"] == "pll0"
    assert config["clk0"]["source"] == "gate0"
    assert config["clk0"]["freq"] == "100"
    assert "target" not in config["gate0"]
    assert "targets" not in config["pll0"]
    assert "freq" in config["clk0"]
    for item in config.values():
        assert "kind" in item
        assert "name" not in item


def test_kind_matches_library_name() -> None:
    path = ROOT / "tests" / "fixtures" / "pll2-tree.drawio"
    config = parse_drawio_paths([path])
    assert config["pll2_0"]["kind"] == "pll2"
    assert config["gate0"]["kind"] == "gate"


def test_from_folded_not_in_json() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-bridge.drawio"
    config = parse_drawio_paths([path])
    assert "clk0" in config
    assert config["clk0"]["source"] == "pll0"
    assert "from" not in {item.get("kind") for item in config.values()}


def test_from_fanout_downstream_sources_only() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-fanout.drawio"
    config = parse_drawio_paths([path])
    assert config["clk_a"]["source"] == "pll0"
    assert config["clk_b"]["source"] == "pll0"


def test_gate_right_port_fanout() -> None:
    path = ROOT / "tests" / "fixtures" / "gate-fanout.drawio"
    config = parse_drawio_paths([path])
    assert config["gate0"]["source"] == "src0"
    assert config["clk_a"]["source"] == "gate0"
    assert config["clk_b"]["source"] == "gate0"
    assert "target" not in config["gate0"]


def _attr(name: str, value: str) -> str:
    return f"{name}={quoteattr(value)}"


def _library_object(
    cell_id: int,
    name: str,
    shape,
    *,
    extra: dict[str, str] | None = None,
) -> str:
    attrs = {"id": str(cell_id), "name": name, "label": "", "placeholders": "0"}
    if extra:
        attrs.update(extra)
    attr_s = " ".join(_attr(key, value) for key, value in attrs.items())
    return (
        f"<object {attr_s}>"
        f"<mxCell style={quoteattr(shape.style)} vertex=\"1\" parent=\"1\">"
        f"<mxGeometry x=\"{cell_id * 120}\" y=\"40\" width=\"{shape.w}\" "
        f"height=\"{shape.h}\" as=\"geometry\"/>"
        f"</mxCell>"
        f"</object>"
    )


def _edge(
    cell_id: int,
    source_id: int,
    target_id: int,
    source_shape,
    source_kind: str,
    source_port: str,
    target_shape,
    target_kind: str,
    target_port: str,
) -> str:
    sx, sy = port_anchors(source_shape.style, source_kind)[source_port]
    tx, ty = port_anchors(target_shape.style, target_kind)[target_port]
    style = (
        "edgeStyle=none;rounded=0;html=1;endArrow=none;startArrow=none;"
        f"exitX={sx};exitY={sy};entryX={tx};entryY={ty};"
        "exitDx=0;exitDy=0;entryDx=0;entryDy=0;exitPerimeter=0;entryPerimeter=0;"
    )
    return (
        f"<mxCell id=\"{cell_id}\" style={quoteattr(style)} edge=\"1\" parent=\"1\" "
        f"source=\"{source_id}\" target=\"{target_id}\">"
        "<mxGeometry relative=\"1\" as=\"geometry\"/>"
        "</mxCell>"
    )


def test_occ_clk_cell_drawio_exports_as_single_input_device(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    occ_cell = shapes["occ_clk_cell"]
    clock = shapes["clock"]
    model = (
        "<mxGraphModel><root>"
        "<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
        f"{_library_object(10, 'src0', source)}"
        f"{_library_object(11, 'cell0', occ_cell)}"
        f"{_library_object(12, 'clk0', clock)}"
        f"{_edge(20, 10, 11, source, 'source', 'right', occ_cell, 'occ_clk_cell', 'left')}"
        f"{_edge(21, 11, 12, occ_cell, 'occ_clk_cell', 'right', clock, 'clock', 'left')}"
        "</root></mxGraphModel>"
    )
    path = tmp_path / "occ-cell-tree.drawio"
    path.write_text(f"<mxfile><diagram>{model}</diagram></mxfile>", encoding="utf-8")

    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    assert config["cell0"] == {
        "kind": "cell",
        "cell_kind": "occ_clk_cell",
        "source": "src0",
    }
    assert config["clk0"]["source"] == "cell0"


def test_inv_mux_exports_major_and_minor_kind(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    inv_mux = shapes["inv_mux"]
    clock = shapes["clock"]
    model = (
        "<mxGraphModel><root>"
        "<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
        f"{_library_object(10, 'src0', source)}"
        f"{_library_object(11, 'inv0', inv_mux)}"
        f"{_library_object(12, 'clk0', clock)}"
        f"{_edge(20, 10, 11, source, 'source', 'right', inv_mux, 'inv_mux', 'left')}"
        f"{_edge(21, 11, 12, inv_mux, 'inv_mux', 'right', clock, 'clock', 'left')}"
        "</root></mxGraphModel>"
    )
    path = tmp_path / "inv-mux-tree.drawio"
    path.write_text(f"<mxfile><diagram>{model}</diagram></mxfile>", encoding="utf-8")

    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    assert config["inv0"] == {
        "kind": "inv",
        "inv_kind": "inv_mux",
        "source": "src0",
    }
    assert config["clk0"]["source"] == "inv0"


def test_source_exports_major_and_minor_kind(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    pll = shapes["pll"]
    clock = shapes["clock"]
    model = (
        "<mxGraphModel><root>"
        "<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
        f"{_library_object(10, 'xtal', source)}"
        f"{_library_object(11, 'pll0', pll)}"
        f"{_library_object(12, 'clk0', clock)}"
        f"{_edge(20, 10, 11, source, 'source', 'right', pll, 'pll', 'left')}"
        f"{_edge(21, 11, 12, pll, 'pll', 'right', clock, 'clock', 'left')}"
        "</root></mxGraphModel>"
    )
    path = tmp_path / "source-tree.drawio"
    path.write_text(f"<mxfile><diagram>{model}</diagram></mxfile>", encoding="utf-8")

    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    assert config["xtal"] == {
        "kind": "source",
        "source_kind": "source",
    }
    assert config["pll0"]["source"] == "xtal"


def test_pll2_dual_output_source_suffix() -> None:
    path = ROOT / "tests" / "fixtures" / "pll2-tree.drawio"
    config = parse_drawio_paths([path])
    assert config["pll2_0"]["kind"] == "pll2"
    assert config["pll2_0"]["pll_kind"] == "SC"
    assert config["pll2_0"]["source"] == "xtal0"
    assert config["pll2_0"]["target"] == {"0": "gate0", "1": "div0"}
    assert config["gate0"]["source"] == "pll2_0[0]"
    assert config["div0"]["source"] == "pll2_0[1]"


def test_cpu_gate_named_output_keys(tmp_path: Path) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    source = shapes["source"]
    cpu_gate = shapes["cpu_gate"]
    clock = shapes["clock"]
    model = (
        "<mxGraphModel><root>"
        "<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
        f"{_library_object(10, 'src0', source)}"
        f"{_library_object(11, 'cg0', cpu_gate)}"
        f"{_library_object(12, 'clk_en', clock)}"
        f"{_library_object(13, 'clk_main', clock)}"
        f"{_library_object(14, 'clk_core', clock)}"
        f"{_edge(20, 10, 11, source, 'source', 'right', cpu_gate, 'cpu_gate', 'left')}"
        f"{_edge(21, 11, 12, cpu_gate, 'cpu_gate', 'out0', clock, 'clock', 'left')}"
        f"{_edge(22, 11, 13, cpu_gate, 'cpu_gate', 'out1', clock, 'clock', 'left')}"
        f"{_edge(23, 11, 14, cpu_gate, 'cpu_gate', 'out2', clock, 'clock', 'left')}"
        "</root></mxGraphModel>"
    )
    path = tmp_path / "cpu-gate-tree.drawio"
    path.write_text(f"<mxfile><diagram>{model}</diagram></mxfile>", encoding="utf-8")

    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    assert config["cg0"]["target"] == {
        "hclk_en": "clk_en",
        "hclk": "clk_main",
        "clk_arm_core": "clk_core",
    }
    assert config["clk_en"]["source"] == "cg0[hclk_en]"
    assert config["clk_main"]["source"] == "cg0[hclk]"
    assert config["clk_core"]["source"] == "cg0[clk_arm_core]"


def test_from_duplicate_input_binding_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-too-many.drawio"
    with pytest.raises(ValueError, match="未连接"):
        parse_drawio_paths([path])


def test_duplicate_device_name_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "duplicate-name.drawio"
    with pytest.raises(ValueError, match="重复"):
        parse_drawio_paths([path])


def test_library_styles_load() -> None:
    styles = load_library_cell_styles(DEFAULT_LIBRARY_PATH)
    assert "pll" in styles and "html=1" in styles["pll"]
    assert "pll2" in styles
    assert "mux2" in styles
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    assert "pll" in shapes and "<svg" in shapes["pll"].label


def test_example_fig1_embeds_library_labels() -> None:
    from drawio_decode import extract_mxfile_xml, iter_diagram_models  # noqa: E402

    fig1 = ROOT / "example" / "fig1.drawio"
    if not fig1.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    text = fig1.read_text(encoding="utf-8")
    assert "<mxGraphModel" not in text
    model_xml = ET.tostring(iter_diagram_models(extract_mxfile_xml(str(fig1)))[0], encoding="unicode")
    assert 'label="' in model_xml and ("&lt;svg" in model_xml or "<svg" in model_xml)
    assert "%name%" not in model_xml
    assert "exitPerimeter=0" in model_xml
    assert "drawclockType=source" in model_xml


def test_example_two_figs_cross_from_no_from_in_json() -> None:
    fig1 = ROOT / "example" / "fig1.drawio"
    fig2 = ROOT / "example" / "fig2.drawio"
    if not fig1.is_file() or not fig2.is_file():
        pytest.skip("先运行 scripts/build_example_demo.py")
    config = parse_drawio_paths([fig1, fig2])
    kinds = {item["kind"] for item in config.values()}
    assert "from" not in kinds
    assert config["pll_main"]["source"] == "xtal"
    assert config["gate0"]["source"] == "pll_main"
    assert config["div0"]["source"] == "pll_main"
    assert "targets" not in config["pll_main"]
    assert "target" not in config["mux2"]
    assert config["mux2"]["kind"] == "mux2"
    assert config["mux2"]["source"] == {"0": "pll_m2a", "1": "pll_m2b"}
    assert config["pll_m2a"]["source"] == "osc_mux"
    assert config["pll_m2b"]["source"] == "osc_mux"


def test_reload_restores_drawable_html_style(tmp_path: Path) -> None:
    from migrate import reload_drawio_file  # noqa: E402

    fixture = ROOT / "tests" / "fixtures" / "mini-tree.drawio"
    out = tmp_path / "drawable.drawio"
    reload_drawio_file(fixture, DEFAULT_LIBRARY_PATH, out)
    text = out.read_text(encoding="utf-8")
    assert "html=1" in text
    assert "drawclockType=pll" in text
    assert 'label="' in text


def test_from_without_clock_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-only.drawio"
    with pytest.raises(ValueError, match="未找到同名 clock"):
        parse_drawio_paths([path])


def test_from_upstream_connect_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-open-left.drawio"
    with pytest.raises(ValueError, match="无输入端口") as exc:
        parse_drawio_paths([path])
    msg = str(exc.value)
    assert "clk0" in msg
    assert "输入端口未连接" not in msg


def test_from_open_output_fails() -> None:
    path = ROOT / "tests" / "fixtures" / "wire-open-right.drawio"
    with pytest.raises(ValueError, match="右端未连接任何器件") as exc:
        parse_drawio_paths([path])
    assert "输出端口未连接" not in str(exc.value)


def test_library_variant_styles_embed_major_and_minor_kind() -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    for major, variants in VARIANT_FAMILIES.items():
        style_key = STYLE_VARIANT_KEYS[major]
        for variant in variants:
            style = shapes[variant].style
            assert f"drawclockType={variant};" in style
            assert f"drawclockKind={major};" in style
            assert f"{style_key}={variant};" in style


def test_library_single_kind_matches_drawclock_type() -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    variant_style_keys = set(STYLE_VARIANT_KEYS.values())
    for title, shape in shapes.items():
        if title == "from":
            continue
        if title in ALL_VARIANT_TYPES:
            continue
        style = shape.style
        assert f"drawclockType={title};" in style, title
        assert f"drawclockKind={title};" in style, title
        for key in variant_style_keys:
            assert f"{key}=" not in style, title


@pytest.mark.parametrize(
    ("major", "variant"),
    [
        (major, variant)
        for major, variants in VARIANT_FAMILIES.items()
        for variant in variants
    ],
)
def test_variant_family_parse_exports_major_and_minor_kind(
    major: str,
    variant: str,
    tmp_path: Path,
) -> None:
    shapes = load_library_shapes(DEFAULT_LIBRARY_PATH)
    device = shapes[variant]
    json_variant_key = JSON_VARIANT_KEYS[major]
    name = "dev0"

    if major == "source":
        clock = shapes["clock"]
        model = (
            "<mxGraphModel><root>"
            "<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
            f"{_library_object(10, name, device)}"
            f"{_library_object(11, 'clk0', clock)}"
            f"{_edge(20, 10, 11, device, variant, 'right', clock, 'clock', 'left')}"
            "</root></mxGraphModel>"
        )
    else:
        source = shapes["source"]
        clock = shapes["clock"]
        model = (
            "<mxGraphModel><root>"
            "<mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/>"
            f"{_library_object(10, 'src0', source)}"
            f"{_library_object(11, name, device)}"
            f"{_library_object(12, 'clk0', clock)}"
            f"{_edge(20, 10, 11, source, 'source', 'right', device, variant, 'left')}"
            f"{_edge(21, 11, 12, device, variant, 'right', clock, 'clock', 'left')}"
            "</root></mxGraphModel>"
        )

    path = tmp_path / f"{variant}-kind.drawio"
    path.write_text(f"<mxfile><diagram>{model}</diagram></mxfile>", encoding="utf-8")
    config = parse_drawio_paths([path], library_path=DEFAULT_LIBRARY_PATH)

    assert config[name]["kind"] == major
    assert config[name][json_variant_key] == variant
