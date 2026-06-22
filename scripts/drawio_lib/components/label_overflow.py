from __future__ import annotations

import re

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
    """Keep labels visible outside the small fixed mxGeometry."""
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


def verify_name_outside_selection_box(
    name_top_y: int,
    cell_h: int,
    *,
    title: str,
) -> None:
    if name_top_y < cell_h:
        raise ValueError(
            f"{title}: instance name must start at or below the selection box "
            f"(name_top_y={name_top_y}, cell_h={cell_h})"
        )


def verify_selection_box_wraps_graphic(
    graphic_bottom_y: int,
    cell_h: int,
    *,
    title: str,
    tolerance_px: int = 2,
) -> None:
    if abs(cell_h - graphic_bottom_y) > tolerance_px:
        raise ValueError(
            f"{title}: selection box height should match graphic bottom "
            f"(cell_h={cell_h}, graphic_bottom={graphic_bottom_y})"
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
) -> None:
    shell_size = f"width:{design_cell_w}px;height:{design_cell_h}px"
    shell_part = html.split('><div style="position:absolute', 1)[0]
    if shell_size not in shell_part:
        raise ValueError(
            f"{title}: label shell must use fixed {design_cell_w}x{design_cell_h}px"
        )
    layer_size = graphic_layer_pin_css(view_w=design_cell_w, view_h=design_cell_h)
    if layer_size not in html:
        raise ValueError(
            f"{title}: graphic layer must pin to the fixed cell canvas"
        )
    if 'viewBox="0 0 ' not in html:
        raise ValueError(f"{title}: label must include a stretch SVG viewBox")
    if f'width="{design_cell_w}"' not in html or f'height="{design_cell_h}"' not in html:
        raise ValueError(
            f"{title}: pattern SVG must use fixed width/height matching the cell canvas"
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
    )
    verify_mxcell_label_style(style, title=title)
