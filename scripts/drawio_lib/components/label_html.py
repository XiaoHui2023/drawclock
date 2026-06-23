from __future__ import annotations

from typing import Literal

from drawio_lib.components.label_attrs import ATTR_NAME, LABEL_FONT_PX
from drawio_lib.components.label_overflow import graphic_layer_pin_css

OverlayAnchor = Literal["center", "left", "right"]

MUX_SEL_BLOCK_START = "<!--mux-sel-->"
MUX_SEL_BLOCK_END = "<!--/mux-sel-->"
MUX_SEL_LINE_HEIGHT_PX = 12
_MUX_SEL_HIDE_STYLE = (
    "<style>"
    ".dc-mux-sel:not(:has(.dc-mux-sel-t:not(:empty))){display:none!important}"
    "</style>"
)

LabelOverlay = (
    tuple[float, float, str]
    | tuple[float, float, str, int]
    | tuple[float, float, str, int, OverlayAnchor]
)


def shell_open(design_cell_w: int, design_cell_h: int) -> str:
    return (
        f'<div style="position:relative;box-sizing:border-box;margin:0;padding:0;'
        f"display:block;width:{design_cell_w}px;height:{design_cell_h}px;"
        f'overflow:visible;white-space:nowrap;font-family:Helvetica,Arial,sans-serif;">'
    )


def shell_close() -> str:
    return "</div>"


def stretch_body_layer(
    body: str,
    *,
    view_w: int,
    view_h: int,
    overlays: tuple[LabelOverlay, ...] = (),
) -> str:
    """Fixed SVG canvas anchored at the small mxGeometry origin."""
    overlay_html = "".join(
        _overlay_on_cell(item, view_w=view_w, view_h=view_h) for item in overlays
    )
    pin = graphic_layer_pin_css(view_w=view_w, view_h=view_h)
    return (
        f'<div style="{pin}">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{view_w}" height="{view_h}" '
        f'viewBox="0 0 {view_w} {view_h}" preserveAspectRatio="none" '
        f'style="display:block;overflow:visible;">'
        f"{body}</svg>"
        f"{overlay_html}"
        f"</div>"
    )


def _overlay_transform(anchor: OverlayAnchor) -> str:
    if anchor == "left":
        return "translate(0,-50%)"
    if anchor == "right":
        return "translate(-100%,-50%)"
    return "translate(-50%,-50%)"


def overlay_anchor(item: LabelOverlay) -> OverlayAnchor:
    if len(item) >= 5:
        return item[4]
    return "center"


def overlay_font_px(item: LabelOverlay) -> int:
    if len(item) >= 4:
        return item[3]
    return LABEL_FONT_PX


def _overlay_on_cell(item: LabelOverlay, *, view_w: int, view_h: int) -> str:
    if len(item) == 3:
        cell_x, cell_y, text = item
        font_px = LABEL_FONT_PX
        anchor: OverlayAnchor = "center"
    elif len(item) == 4:
        cell_x, cell_y, text, font_px = item
        anchor = "center"
    else:
        cell_x, cell_y, text, font_px, anchor = item
    left_pct = cell_x / view_w * 100
    top_pct = cell_y / view_h * 100
    transform = _overlay_transform(anchor)
    return (
        f'<span style="position:absolute;left:{left_pct}%;top:{top_pct}%;'
        f"font-size:{font_px}px;line-height:1;white-space:nowrap;"
        f'transform:{transform};">{text}</span>'
    )


def text_overlay(
    cell_x: float,
    cell_y: float,
    *,
    cell_w: int,
    cell_h: int,
    text: str,
    font_px: int = LABEL_FONT_PX,
) -> str:
    """Cell-relative overlay (clock freq row, etc.)."""
    left_pct = cell_x / cell_w * 100
    top_pct = cell_y / cell_h * 100
    return (
        f'<span style="position:absolute;left:{left_pct}%;top:{top_pct}%;'
        f"font-size:{font_px}px;line-height:1;white-space:nowrap;"
        f'transform:translate(-50%,-50%);">{text}</span>'
    )


def strip_mux_sel_block(html: str) -> str:
    start = html.find(MUX_SEL_BLOCK_START)
    if start < 0:
        return html
    end = html.find(MUX_SEL_BLOCK_END, start)
    if end < 0:
        return html
    return html[:start] + html[end + len(MUX_SEL_BLOCK_END) :]


def mux_sel_signal_block(
    *,
    anchor_x: float,
    anchor_y: int,
    design_cell_w: int,
    design_cell_h: int,
    attr: str = "sel",
    line_height: int = MUX_SEL_LINE_HEIGHT_PX,
    stroke: str = "#000000",
) -> str:
    """Vertical sel stub above the mux top center; hidden when ``attr`` is empty."""
    left_pct = anchor_x / design_cell_w * 100
    top_pct = anchor_y / design_cell_h * 100
    return (
        f"{MUX_SEL_BLOCK_START}"
        f"{_MUX_SEL_HIDE_STYLE}"
        f'<div class="dc-mux-sel" style="position:absolute;left:{left_pct}%;'
        f"top:{top_pct}%;transform:translate(-50%,-100%);"
        f'pointer-events:none;text-align:center;">'
        f'<div style="display:flex;flex-direction:column;align-items:center;">'
        f'<span class="dc-mux-sel-t" style="font-size:{LABEL_FONT_PX}px;'
        f'line-height:1;white-space:nowrap;">%{attr}%</span>'
        f'<div style="width:1px;height:{line_height}px;background:{stroke};'
        f'flex-shrink:0;"></div>'
        f"</div></div>"
        f"{MUX_SEL_BLOCK_END}"
    )


def mux_sel_preview_svg(
    *,
    anchor_x: float,
    anchor_y: int,
    text: str = "sel",
    line_height: int = MUX_SEL_LINE_HEIGHT_PX,
    font_px: int = LABEL_FONT_PX,
    stroke: str = "#000000",
    text_gap_px: int = 2,
) -> str:
    """Documentation-only sel stub for ``preview_svg`` (not used in library shapes)."""
    line_y1 = anchor_y - line_height
    text_y = line_y1 - text_gap_px
    return (
        f'  <line x1="{anchor_x}" y1="{line_y1}" x2="{anchor_x}" y2="{anchor_y}" '
        f'stroke="{stroke}" stroke-width="1"/>\n'
        f'  <text x="{anchor_x}" y="{text_y}" font-size="{font_px}" fill="{stroke}" '
        f'text-anchor="middle" dominant-baseline="auto">{text}</text>\n'
    )


def name_block(
    name_top_y: int,
    *,
    design_cell_h: int,
    gap_px: int,
    center_x: int | None = None,
    design_cell_w: int | None = None,
) -> str:
    top_pct = name_top_y / design_cell_h * 100
    if center_x is None:
        left_css = "left:50%"
    else:
        if design_cell_w is None:
            raise ValueError("name_block center_x requires design_cell_w")
        left_pct = center_x / design_cell_w * 100
        left_css = f"left:{left_pct}%"
    return (
        f'<div style="position:absolute;{left_css};top:{top_pct}%;'
        f"transform:translateX(-50%);text-align:center;"
        f"font-size:{LABEL_FONT_PX}px;line-height:1;white-space:nowrap;"
        f'padding-top:{gap_px}px;">'
        f"%{ATTR_NAME}%</div>"
    )
