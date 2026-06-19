from __future__ import annotations

from library_ports import port_anchors as _port_anchors
from library_ports import port_topology_from_style, resolve_port

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
                raise ValueError(f"input {key} missing")
            entry_xy = tgt_ports[key]
        elif "left" in tgt_ports:
            entry_xy = tgt_ports["left"]
        elif tgt_ports:
            first_input = next(
                (key for key in tgt_ports if key.startswith("in")),
                next(iter(tgt_ports)),
            )
            entry_xy = tgt_ports[first_input]
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
    exit_xy = port_anchors(src_style, src_type)[src_port]
    entry_xy = port_anchors(tgt_style, tgt_type)[tgt_port]
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
    src_ports = port_anchors(src_style, src_type)
    exit_port = "right" if "right" in src_ports else "out"
    exit_xy = src_ports[exit_port]
    entry_xy = port_anchors(tgt_style, tgt_type)[f"in{mux_input}"]
    ex, ey = abs_port_xy(src_x, src_y, src_w, src_h, src_style, src_type, exit_port)
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
    topology = port_topology_from_style(target_style)
    if not topology.inputs:
        return None
    port = resolve_port(_parse_points_from_style(target_style), entry_xy)
    if port is None or not port.startswith("in"):
        return None
    return int(port[2:])


def _parse_points_from_style(style: str) -> tuple[tuple[float, float], ...]:
    from drawio_graph import _parse_points

    return _parse_points(style)


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
