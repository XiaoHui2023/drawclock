from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_lib.components.label_attrs import INSTANCE_NAME_GAP_PX, LABEL_FONT_PX
from drawio_lib.components.label_overflow import (
    verify_label_overflow_policy,
    verify_label_stretch_policy,
    verify_mxcell_label_style,
    verify_no_degenerate_label_tricks,
    verify_selection_box_matches_render_bounds,
)
from drawio_lib.components import registry
from drawio_lib.components import simple_geometry as sgeom


@pytest.mark.parametrize(
    "module_name",
    [
        "gate",
        "div",
        "div_r",
        "div_n",
        "dto",
        "dto_n",
        "inv",
        "occ_clk_cell",
        "pll",
        "clock",
        "from",
        "mux2",
        "mux6",
    ],
)
def test_mxcell_uses_visible_overflow_and_fixed_size(module_name: str) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    style = mod.cell_style()
    html = mod.label_html()
    graphic_h = getattr(mod, "GRAPHIC_H", mod.H)
    verify_label_overflow_policy(
        html,
        style,
        title=module_name,
        design_cell_w=mod.W,
        design_cell_h=mod.H,
        graphic_cell_h=graphic_h,
    )
    verify_mxcell_label_style(style, title=module_name)
    verify_no_degenerate_label_tricks(html, title=module_name)


def test_middle_vertical_align_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    bad = gate.cell_style().replace("verticalAlign=top", "verticalAlign=middle")
    with pytest.raises(ValueError, match="verticalAlign=top"):
        verify_mxcell_label_style(bad, title="gate")


def test_fill_overflow_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html()
    bad_style = gate.cell_style().replace("overflow=visible", "overflow=fill")
    with pytest.raises(ValueError, match="overflow=fill"):
        verify_label_overflow_policy(
            html,
            bad_style,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
            graphic_cell_h=gate.GRAPHIC_H,
        )


def test_resizable_required() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html()
    bad_style = gate.cell_style().replace("resizable=0;", "")
    with pytest.raises(ValueError, match="resizable=0"):
        verify_label_overflow_policy(
            html,
            bad_style,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
            graphic_cell_h=gate.GRAPHIC_H,
        )


def test_percent_shell_rejected() -> None:
    gate = importlib.import_module("drawio_lib.components.gate")
    html = gate.label_html().replace(
        f"display:block;width:{gate.W}px;height:{gate.H}px;",
        "display:block;width:100%;height:100%;",
    )
    with pytest.raises(ValueError, match="fixed"):
        verify_label_stretch_policy(
            html,
            title="gate",
            design_cell_w=gate.W,
            design_cell_h=gate.H,
            graphic_cell_h=gate.GRAPHIC_H,
        )


def _name_top_y(mod) -> int | None:
    import re

    if not hasattr(mod, "label_html"):
        return None
    html = mod.label_html()
    if "%name%" not in html:
        return None
    fn = getattr(mod, "_instance_name_top_y", None)
    if callable(fn):
        return int(fn())
    before = html.split("%name%")[0]
    tops = re.findall(r"top:(\d+(?:\.\d+)?)%", before)
    if tops:
        return round(float(tops[-1]) / 100 * mod.H)
    return None


def _instance_name_gap_px(mod) -> int:
    return int(getattr(mod, "DEFAULT_INSTANCE_GAP", INSTANCE_NAME_GAP_PX))


@pytest.mark.parametrize(
    ("module_name", "expected_name_top"),
    [
        ("gate", 44),
        ("div", 44),
        ("from", 14),
        ("clock", 36),
        ("and_gate", 54),
        ("mux2", None),
    ],
)
def test_instance_name_top_y_unchanged_pixels(
    module_name: str, expected_name_top: int | None
) -> None:
    mod = importlib.import_module(f"drawio_lib.components.{module_name}")
    if expected_name_top is None:
        assert _name_top_y(mod) == mod.G.mux_h
    else:
        assert _name_top_y(mod) == expected_name_top


@pytest.mark.parametrize("spec", registry.ALL, ids=lambda s: s.module.TITLE)
def test_selection_box_matches_render_bounds(spec) -> None:
    mod = spec.module
    if mod.TITLE == "async":
        verify_selection_box_matches_render_bounds(
            mod.H,
            name_top_y=mod.H,
            instance_name_gap_px=0,
            name_h=0,
            title=mod.TITLE,
        )
        return
    name_top = _name_top_y(mod)
    assert name_top is not None, f"{mod.TITLE}: expected instance name in label"
    verify_selection_box_matches_render_bounds(
        mod.H,
        name_top_y=name_top,
        instance_name_gap_px=_instance_name_gap_px(mod),
        name_h=LABEL_FONT_PX,
        title=mod.TITLE,
    )
