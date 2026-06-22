from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from drawio_lib.components.label_overflow import (
    verify_label_overflow_policy,
    verify_label_stretch_policy,
    verify_mxcell_label_style,
    verify_name_outside_selection_box,
    verify_no_degenerate_label_tricks,
    verify_selection_box_wraps_graphic,
)
from drawio_lib.components import registry
from drawio_lib.components import simple_geometry as sgeom


@pytest.mark.parametrize(
    "module_name",
    [
        "gate",
        "div",
        "div2",
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
    verify_label_overflow_policy(
        html,
        style,
        title=module_name,
        design_cell_w=mod.W,
        design_cell_h=mod.H,
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
        )


def _graphic_bottom_y(mod) -> int | None:
    g = getattr(mod, "G", None)
    if g is None:
        return None
    if hasattr(g, "mux_h"):
        return g.mux_h
    if hasattr(g, "graphic_h"):
        from drawio_lib.components.module_geometry import MODULE_BOX_Y

        return MODULE_BOX_Y + g.graphic_h + sgeom.MUX_BODY_PAD_BOTTOM
    if hasattr(g, "trap"):
        return g.trap.y + g.trap.h + sgeom.MUX_BODY_PAD_BOTTOM
    if hasattr(g, "cell_h") and not hasattr(g, "body"):
        return sgeom.BODY_Y + sgeom.BODY_H + sgeom.MUX_BODY_PAD_BOTTOM
    if hasattr(g, "body"):
        if mod.TITLE == "clock":
            from drawio_lib.components.simple_shapes import CLOCK_WAVE_AMP

            return g.body_mid_y + CLOCK_WAVE_AMP
        if mod.TITLE == "from":
            return mod.H
        return g.body.y + g.body.h + sgeom.MUX_BODY_PAD_BOTTOM
    return None


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


@pytest.mark.parametrize("spec", registry.ALL, ids=lambda s: s.module.TITLE)
def test_selection_box_wraps_graphic_not_name(spec) -> None:
    mod = spec.module
    if mod.TITLE == "async":
        pytest.skip("async has no instance name")
    graphic_bottom = _graphic_bottom_y(mod)
    if graphic_bottom is None:
        pytest.skip(f"{mod.TITLE}: no graphic bounds helper")
    verify_selection_box_wraps_graphic(
        graphic_bottom,
        mod.H,
        title=mod.TITLE,
    )
    name_top = _name_top_y(mod)
    if name_top is not None:
        verify_name_outside_selection_box(name_top, mod.H, title=mod.TITLE)
