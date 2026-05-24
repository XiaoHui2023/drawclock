from __future__ import annotations

import re

MXCELL_OVERFLOW_FILL = "overflow=fill"

_PERCENT_HEIGHT_ONLY = re.compile(
    r"height:\s*(?!100(?:\.0+)?%)\d+(?:\.\d+)?%\s*;",
    re.IGNORECASE,
)
_FIXED_SHELL_SIZE = re.compile(
    r"width:\s*\d+px\s*;|height:\s*\d+px\s*;",
    re.IGNORECASE,
)
_ALLOWED_FIXED_PX = re.compile(
    r"flex:0\s0\sauto;width:\d+px;?",
    re.IGNORECASE,
)


def mxcell_overflow_style() -> str:
    return f"{MXCELL_OVERFLOW_FILL};"


def mxcell_html_label_style_parts() -> str:
    """Label fills mxGeometry so the graphic layer can use width/height 100%."""
    return (
        "rounded=0;whiteSpace=nowrap;html=1;metaEdit=1;placeholders=1;"
        f"{mxcell_overflow_style()}"
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
            f"{title}: body SVG must use preserveAspectRatio=none so ports track the graphic"
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
    if "width:100%" not in html or "height:100%" not in html:
        raise ValueError(f"{title}: label shell must use width/height 100%")
    if f"min-width:{design_cell_w}px" in html or f"min-height:{design_cell_h}px" in html:
        raise ValueError(
            f"{title}: label shell must not set min-width/min-height to design px "
            "(draw.io shrink-wraps to min size; ports drift from the graphic)"
        )
    if 'position:absolute;left:0;top:0;width:100%;height:100%' not in html:
        raise ValueError(
            f"{title}: graphic layer must pin to the full cell (absolute 100%×100%)"
        )
    shell_part = html.split('viewBox="0 0 ', 1)[0]
    shell_part = _ALLOWED_FIXED_PX.sub("", shell_part)
    if _FIXED_SHELL_SIZE.search(shell_part):
        raise ValueError(
            f"{title}: label shell must not use fixed px width/height "
            "(pattern will not fill a stretched mxGeometry)"
        )
    if 'viewBox="0 0 ' not in html:
        raise ValueError(f"{title}: label must include a stretch SVG viewBox")
    if 'width="100%"' not in html or 'height="100%"' not in html:
        raise ValueError(
            f"{title}: pattern SVG must use width/height 100% or the graphic collapses"
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
    if "overflow=visible" in style:
        raise ValueError(
            f"{title}: mxCell must not use overflow=visible "
            "(draw.io shrink-wraps HTML labels to ~1px; the graphic disappears)"
        )
    if MXCELL_OVERFLOW_FILL not in style:
        raise ValueError(
            f"{title}: mxCell style must include {MXCELL_OVERFLOW_FILL} "
            "so the label fills mxGeometry"
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
