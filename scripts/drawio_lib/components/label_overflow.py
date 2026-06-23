from __future__ import annotations

import re

from drawio_lib.components.label_attrs import LABEL_FONT_PX

MXCELL_OVERFLOW_VISIBLE = "overflow=visible"
MXCELL_RESIZABLE_OFF = "resizable=0"

# draw.io html=1 wraps label HTML in a 12px inline-block; export shows graphic
# ~7px below and ~2px right of mxGeometry origin while points stay on the box.
DRAWIO_HTML_LABEL_OFFSET_X = 2
DRAWIO_HTML_LABEL_OFFSET_Y = 7

_PERCENT_HEIGHT_ONLY = re.compile(
    r"height:\s*(?!100(?:\.0+)?%)\d+(?:\.\d+)?%\s*;",
    re.IGNORECASE,
)
_ALLOWED_FIXED_PX = re.compile(
    r"flex:0\s0\sauto;width:\d+px;?",
    re.IGNORECASE,
)


def graphic_layer_pin_css(*, view_w: int, view_h: int) -> str:
    return (
        f"position:absolute;left:{-DRAWIO_HTML_LABEL_OFFSET_X}px;"
        f"top:{-DRAWIO_HTML_LABEL_OFFSET_Y}px;"
        f"width:{view_w}px;height:{view_h}px"
    )


def mxcell_overflow_style() -> str:
    return f"{MXCELL_OVERFLOW_VISIBLE};"


def mxcell_html_label_style_parts() -> str:
    """Fixed-size html=1 label cell; overflow=visible for draw.io HTML wrapper quirks."""
    return (
        "rounded=0;whiteSpace=nowrap;html=1;metaEdit=1;placeholders=1;"
        f"{mxcell_overflow_style()}"
        f"{MXCELL_RESIZABLE_OFF};"
        "autosize=0;"
        "fillColor=none;strokeColor=none;"
        "spacingTop=0;spacingBottom=0;spacingLeft=0;spacingRight=0;"
        "align=left;verticalAlign=top;"
    )


def verify_no_degenerate_label_tricks(html: str, *, title: str) -> None:
    if "transform:scale(" in html or "transform: scale(" in html:
        raise ValueError(
            f"{title}: must not use transform:scale on labels "
            "(text/graphic warps when the shape stretches)"
        )
    if 'preserveAspectRatio="meet"' in html or 'preserveAspectRatio="xMidYMid meet"' in html:
        raise ValueError(
            f"{title}: body SVG must use preserveAspectRatio=none inside the fixed cell"
        )


def verify_selection_box_matches_render_bounds(
    cell_h: int,
    *,
    name_top_y: int,
    instance_name_gap_px: int,
    name_h: int = LABEL_FONT_PX,
    title: str,
    tolerance_px: int = 2,
) -> None:
    expected = name_top_y + instance_name_gap_px + name_h
    if abs(cell_h - expected) > tolerance_px:
        raise ValueError(
            f"{title}: selection box height should match HTML render bounds "
            f"(cell_h={cell_h}, expected={expected})"
        )


def verify_mxcell_label_style(style: str, *, title: str) -> None:
    if "verticalAlign=top" not in style:
        raise ValueError(
            f"{title}: mxCell must use verticalAlign=top "
            "(middle centers HTML when stretched; points stay on outer box)"
        )
    for bad in ("verticalAlign=middle", "verticalAlign=center", "verticalAlign=bottom"):
        if bad in style:
            raise ValueError(f"{title}: mxCell must not use {bad}")
    if "align=left" not in style:
        raise ValueError(
            f"{title}: mxCell must use align=left so label origin matches geometry"
        )


def verify_label_stretch_policy(
    html: str,
    *,
    title: str,
    design_cell_w: int,
    design_cell_h: int,
    graphic_cell_h: int | None = None,
) -> None:
    graphic_h = graphic_cell_h if graphic_cell_h is not None else design_cell_h
    shell_size = f"width:{design_cell_w}px;height:{design_cell_h}px"
    shell_part = html.split('><div style="position:absolute', 1)[0]
    if shell_size not in shell_part:
        raise ValueError(
            f"{title}: label shell must use fixed {design_cell_w}x{design_cell_h}px"
        )
    layer_size = graphic_layer_pin_css(view_w=design_cell_w, view_h=graphic_h)
    if layer_size not in html:
        raise ValueError(
            f"{title}: graphic layer must pin to the fixed graphic canvas"
        )
    if 'viewBox="0 0 ' not in html:
        raise ValueError(f"{title}: label must include a stretch SVG viewBox")
    if f'width="{design_cell_w}"' not in html or f'height="{graphic_h}"' not in html:
        raise ValueError(
            f"{title}: pattern SVG must use fixed width/height matching the graphic canvas"
        )
    if _PERCENT_HEIGHT_ONLY.search(html):
        raise ValueError(
            f"{title}: percent-height bands collapse without a sized parent; "
            "use flex stretch layer instead"
        )
    verify_no_degenerate_label_tricks(html, title=title)


def verify_label_overflow_policy(
    html: str,
    style: str,
    *,
    title: str,
    design_cell_w: int,
    design_cell_h: int,
    graphic_cell_h: int | None = None,
) -> None:
    if "overflow=fill" in style:
        raise ValueError(
            f"{title}: mxCell must not use overflow=fill "
            "(draw.io clips labels outside the selection box)"
        )
    if MXCELL_OVERFLOW_VISIBLE not in style:
        raise ValueError(
            f"{title}: mxCell style must include {MXCELL_OVERFLOW_VISIBLE} "
            "so text outside the selection box remains visible"
        )
    if MXCELL_RESIZABLE_OFF not in style:
        raise ValueError(
            f"{title}: mxCell style must include {MXCELL_RESIZABLE_OFF} "
            "so fixed graphics, text, and ports cannot drift after stretching"
        )
    if "overflow:visible" not in html:
        raise ValueError(f"{title}: label shell must use overflow:visible")
    verify_label_stretch_policy(
        html,
        title=title,
        design_cell_w=design_cell_w,
        design_cell_h=design_cell_h,
        graphic_cell_h=graphic_cell_h,
    )
    verify_mxcell_label_style(style, title=title)
