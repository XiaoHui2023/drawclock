from __future__ import annotations

import re

from library_ports import port_anchors as _port_anchors
from library_ports import resolve_port


EDGE_DRAW_STYLE = (
    "edgeStyle=none;rounded=0;html=1;"
    "endArrow=none;startArrow=none;strokeColor=#000000;"
    "exitDx=0;exitDy=0;entryDx=0;entryDy=0;"
    "exitPerimeter=0;entryPerimeter=0;"
)

_STYLE_XY_RE = re.compile(r"(exit|entry)(X|Y)=(-?[0-9.]+)")


def port_anchors(style: str, drawclock_type: str) -> dict[str, tuple[float, float]]:
    _ = drawclock_type
    return _port_anchors(style)


def abs_port_xy(
    x: float,
    y: float,
    width: float,
    height: float,
    style: str,
    drawclock_type: str,
    port: str,
) -> tuple[float, float]:
    anchors = port_anchors(style, drawclock_type)
    if port not in anchors:
        raise KeyError(f"port {port} not on {drawclock_type}")
    anchor_x, anchor_y = anchors[port]
    return x + width * anchor_x, y + height * anchor_y


def edge_attachment(style: str, *, end: str) -> tuple[float, float] | None:
    prefix = "exit" if end == "exit" else "entry"
    x = y = None
    for kind, axis, value in _STYLE_XY_RE.findall(style):
        if kind != prefix:
            continue
        if axis == "X":
            x = float(value)
        else:
            y = float(value)
    if x is None or y is None:
        return None
    return x, y


def infer_port_from_attachment(
    shape_style: str,
    stored_edge_style: str,
    *,
    end: str,
) -> str | None:
    return resolve_port(
        tuple(_port_anchors(shape_style).values()),
        edge_attachment(stored_edge_style, end=end),
    )
