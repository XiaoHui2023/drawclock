from __future__ import annotations

from drawio_lib.components.label_attrs import ATTR_NAME, LABEL_FONT_PX

LabelOverlay = tuple[float, float, str] | tuple[float, float, str, int]


def shell_open(design_cell_w: int, design_cell_h: int) -> str:
    _ = (design_cell_w, design_cell_h)
    return (
        f'<div style="position:relative;box-sizing:border-box;margin:0;padding:0;'
        f"display:block;width:100%;height:100%;"
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
    """SVG fills the shape; stretches with mxGeometry so ports stay aligned."""
    overlay_html = "".join(
        _overlay_on_cell(item, view_w=view_w, view_h=view_h) for item in overlays
    )
    return (
        f'<div style="position:absolute;left:0;top:0;width:100%;height:100%;">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        f'viewBox="0 0 {view_w} {view_h}" preserveAspectRatio="none" '
        f'style="display:block;overflow:visible;">'
        f"{body}</svg>"
        f"{overlay_html}"
        f"</div>"
    )


def _overlay_on_cell(item: LabelOverlay, *, view_w: int, view_h: int) -> str:
    if len(item) == 3:
        cell_x, cell_y, text = item
        font_px = LABEL_FONT_PX
    else:
        cell_x, cell_y, text, font_px = item
    left_pct = cell_x / view_w * 100
    top_pct = cell_y / view_h * 100
    return (
        f'<span style="position:absolute;left:{left_pct}%;top:{top_pct}%;'
        f"font-size:{font_px}px;line-height:1;white-space:nowrap;"
        f'transform:translate(-50%,-50%);">{text}</span>'
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
