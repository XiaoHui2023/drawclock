from __future__ import annotations

import re

from drawio_graph import _parse_points

MUX_KIND_RE = re.compile(r"^mux([2-6])$")

# edgeStyle=none: draw.io paints port-to-port lines correctly on first open.
# orthogonalEdgeStyle without waypoints triggers auto-routing (false bends until relayout).
EDGE_STRAIGHT_STYLE = (
    "edgeStyle=none;rounded=0;html=1;"
    "endArrow=none;startArrow=none;strokeColor=#000000;"
    "exitDx=0;exitDy=0;entryDx=0;entryDy=0;"
    "exitPerimeter=0;entryPerimeter=0;"
)

EDGE_DRAW_STYLE = EDGE_STRAIGHT_STYLE

_PORT_ATTACH_KEYS = (
    "exitDx=0",
    "exitDy=0",
    "entryDx=0",
    "entryDy=0",
    "exitPerimeter=0",
    "entryPerimeter=0",
)


def finalize_edge_style(style: str) -> str:
    """Keep connectors on custom points inside the shape, not the bbox perimeter."""
    out = style
    if not out.endswith(";"):
        out += ";"
    for key in _PORT_ATTACH_KEYS:
        if key not in out:
            out += f"{key};"
    return out


def port_anchors(style: str, drawclock_type: str) -> dict[str, tuple[float, float]]:
    """Map port keys to relative (x, y) anchors from mxCell style points."""
    pts = _parse_points(style)
    if not pts:
        if drawclock_type in ("pll", "source"):
            return {"right": (1.0, 0.5)}
        if drawclock_type == "clock":
            return {"left": (0.0, 0.5)}
        return {"left": (0.0, 0.5), "right": (1.0, 0.5)}

    mux_match = MUX_KIND_RE.match(drawclock_type)
    if mux_match:
        anchors: dict[str, tuple[float, float]] = {}
        for index, point in enumerate(pts[:-1]):
            anchors[f"in{index}"] = (point[0], point[1])
        anchors["out"] = (pts[-1][0], pts[-1][1])
        return anchors

    if drawclock_type in ("pll", "source"):
        return {"right": (pts[0][0], pts[0][1])}
    if drawclock_type == "clock":
        return {"left": (pts[0][0], pts[0][1])}
    if drawclock_type == "wire":
        return {
            "left": (pts[0][0], pts[0][1]),
            "right": (pts[-1][0], pts[-1][1]),
        }
    return {
        "left": (pts[0][0], pts[0][1]),
        "right": (pts[-1][0], pts[-1][1]),
    }


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
    ax, ay = anchors[port]
    return x + width * ax, y + height * ay


def y_for_port(shape_h: float, style: str, drawclock_type: str, port: str, bus_y: float) -> float:
    """Top-left y so the given port sits on horizontal bus_y."""
    _, ay = port_anchors(style, drawclock_type)[port]
    return bus_y - shape_h * ay


def edge_port_style(
    source_style: str,
    source_type: str,
    target_style: str,
    target_type: str,
    *,
    target_mux_input: int | None = None,
    fallback: str = "",
) -> str:
    """Build exitX/exitY/entryX/entryY so connectors meet shape ports."""
    try:
        src_ports = port_anchors(source_style, source_type)
        tgt_ports = port_anchors(target_style, target_type)
        if "out" in src_ports:
            exit_xy = src_ports["out"]
        elif "right" in src_ports:
            exit_xy = src_ports["right"]
        else:
            raise ValueError(f"no exit port for {source_type}")

        if target_mux_input is not None:
            key = f"in{target_mux_input}"
            if key not in tgt_ports:
                raise ValueError(f"mux input {key} missing")
            entry_xy = tgt_ports[key]
        elif "left" in tgt_ports:
            entry_xy = tgt_ports["left"]
        else:
            raise ValueError(f"no entry port for {target_type}")
    except ValueError:
        return finalize_edge_style(
            fallback or "exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
        )

    return finalize_edge_style(
        f"{EDGE_DRAW_STYLE}"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};"
    )


def chain_edge_style(
    src_x: float,
    src_y: float,
    src_w: float,
    src_h: float,
    src_style: str,
    src_type: str,
    tgt_x: float,
    tgt_y: float,
    tgt_w: float,
    tgt_h: float,
    tgt_style: str,
    tgt_type: str,
    *,
    src_port: str = "right",
    tgt_port: str = "left",
) -> str:
    """Straight connector along a shared horizontal bus between two ports."""
    sx, sy = abs_port_xy(src_x, src_y, src_w, src_h, src_style, src_type, src_port)
    tx, ty = abs_port_xy(tgt_x, tgt_y, tgt_w, tgt_h, tgt_style, tgt_type, tgt_port)
    src_anchors = port_anchors(src_style, src_type)
    tgt_anchors = port_anchors(tgt_style, tgt_type)
    exit_xy = src_anchors[src_port]
    entry_xy = tgt_anchors[tgt_port]
    _ = (sx, sy, tx, ty)
    return (
        f"{EDGE_DRAW_STYLE}"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};"
    )


def chain_edge_orthogonal(
    src_x: float,
    src_y: float,
    src_w: float,
    src_h: float,
    src_style: str,
    src_type: str,
    tgt_x: float,
    tgt_y: float,
    tgt_w: float,
    tgt_h: float,
    tgt_style: str,
    tgt_type: str,
    *,
    src_port: str = "right",
    tgt_port: str = "left",
) -> tuple[str, tuple[tuple[float, float], ...]]:
    """Route between two ports; straight when aligned, else orthogonal."""
    return chain_edge_route(
        src_x,
        src_y,
        src_w,
        src_h,
        src_style,
        src_type,
        tgt_x,
        tgt_y,
        tgt_w,
        tgt_h,
        tgt_style,
        tgt_type,
        src_port=src_port,
        tgt_port=tgt_port,
    )


def chain_edge_route(
    src_x: float,
    src_y: float,
    src_w: float,
    src_h: float,
    src_style: str,
    src_type: str,
    tgt_x: float,
    tgt_y: float,
    tgt_w: float,
    tgt_h: float,
    tgt_style: str,
    tgt_type: str,
    *,
    src_port: str = "right",
    tgt_port: str = "left",
) -> tuple[str, tuple[tuple[float, float], ...]]:
    """Straight when ports share Y; else polyline via explicit waypoints (edgeStyle=none)."""
    exit_xy = port_anchors(src_style, src_type)[src_port]
    entry_xy = port_anchors(tgt_style, tgt_type)[tgt_port]
    ex, ey = abs_port_xy(src_x, src_y, src_w, src_h, src_style, src_type, src_port)
    ix, iy = abs_port_xy(tgt_x, tgt_y, tgt_w, tgt_h, tgt_style, tgt_type, tgt_port)
    style = (
        f"{EDGE_DRAW_STYLE}"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};"
    )
    if abs(ey - iy) < 0.5:
        return style, ()
    mid_x = (ex + ix) / 2
    return style, ((mid_x, ey), (mid_x, iy))


def mux_fanin_edge_style(
    src_x: float,
    src_y: float,
    src_w: float,
    src_h: float,
    src_style: str,
    src_type: str,
    tgt_x: float,
    tgt_y: float,
    tgt_w: float,
    tgt_h: float,
    tgt_style: str,
    tgt_type: str,
    mux_input: int,
    *,
    stub_x: float | None = None,
) -> tuple[str, tuple[tuple[float, float], ...]]:
    """Horizontal stub from PLL, vertical into mux input (orthogonal)."""
    exit_xy = port_anchors(src_style, src_type)["right"]
    entry_xy = port_anchors(tgt_style, tgt_type)[f"in{mux_input}"]
    ex, ey = abs_port_xy(src_x, src_y, src_w, src_h, src_style, src_type, "right")
    ix, iy = abs_port_xy(
        tgt_x, tgt_y, tgt_w, tgt_h, tgt_style, tgt_type, f"in{mux_input}"
    )
    merge = stub_x if stub_x is not None else tgt_x - 20.0
    style = (
        f"{EDGE_DRAW_STYLE}"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};"
    )
    if abs(ey - iy) < 0.5:
        return style, ((merge, ey),)
    return style, ((merge, ey), (merge, iy))


def infer_mux_input_index(
    target_style: str,
    target_type: str,
    entry_xy: tuple[float, float] | None,
) -> int | None:
    if entry_xy is None or MUX_KIND_RE.match(target_type) is None:
        return None
    ports = port_anchors(target_style, target_type)
    best_idx: int | None = None
    best_dist = float("inf")
    for key, xy in ports.items():
        if not key.startswith("in"):
            continue
        dist = (xy[0] - entry_xy[0]) ** 2 + (xy[1] - entry_xy[1]) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = int(key[2:])
    if best_dist > 0.04:
        return None
    return best_idx


def resolve_edge_style(
    source_style: str,
    source_type: str,
    target_style: str,
    target_type: str,
    stored_style: str,
) -> str:
    from drawio_graph import edge_attachment

    mux_in = infer_mux_input_index(
        target_style, target_type, edge_attachment(stored_style, end="entry")
    )
    return finalize_edge_style(
        edge_port_style(
            source_style,
            source_type,
            target_style,
            target_type,
            target_mux_input=mux_in,
            fallback=stored_style,
        )
    )
