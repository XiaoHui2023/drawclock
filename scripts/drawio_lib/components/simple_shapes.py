from __future__ import annotations

import math
from typing import Literal

from drawio_lib.components import simple_geometry as geom

STROKE = "#000000"
FILL = "none"
SW = 2


def _mid(g: geom.SimpleGeometry) -> int:
    return g.body_mid_y


def _dx(g: geom.SimpleGeometry, x: float) -> float:
    return geom.side_pad_x(g.cell_w) + x


def _inversion_bubble(cx: float, cy: float, r: float) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" stroke="{STROKE}" '
        f'stroke-width="{SW}"/>'
    )


def _hex_points(cx: float, cy: float, r: float) -> str:
    pts = []
    for i in range(6):
        a = math.pi / 6 + i * math.pi / 3
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


GATE_LEFT_X = 11
GATE_ARC_X = 19
GATE_BODY_R = 12
GATE_BUBBLE_GAP = 5
GATE_BUBBLE_R = 3
GATE_BUBBLE_X = GATE_ARC_X + GATE_BODY_R + GATE_BUBBLE_GAP + GATE_BUBBLE_R


def gate_body(g: geom.SimpleGeometry) -> str:
    """Clock gate: left vertical, top/bottom horizontals, right semicircle (stretchable width)."""
    mid = _mid(g)
    top_y = mid - GATE_BODY_R
    bot_y = mid + GATE_BODY_R
    left = _dx(g, GATE_LEFT_X)
    arc = _dx(g, GATE_ARC_X)
    bubble = _dx(g, GATE_BUBBLE_X)
    return (
        f'<path d="M {left} {top_y} L {arc} {top_y} '
        f'A {GATE_BODY_R} {GATE_BODY_R} 0 1 1 {arc} {bot_y} '
        f'L {left} {bot_y} Z" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="miter"/>'
        f'{_inversion_bubble(bubble, mid, GATE_BUBBLE_R)}'
    )


DIV_HEX_R = 12
DIV_SYMBOL_HALF_W = 5.5
DIV_SYMBOL_DOT_R = 1.4
DIV_SYMBOL_DOT_OFFSET = 4.5


def _div_symbol_markup(cx: float, cy: float, *, angle_deg: float = 0) -> str:
    """Division sign drawn as line + dots (not text)."""
    half_w = DIV_SYMBOL_HALF_W
    dot_off = DIV_SYMBOL_DOT_OFFSET
    r = DIV_SYMBOL_DOT_R
    paths = (
        f'<path d="M {cx - half_w:.1f} {cy:.1f} L {cx + half_w:.1f} {cy:.1f}" fill="none" '
        f'stroke="{STROKE}" stroke-width="1.5" stroke-linecap="round"/>'
        f'<circle cx="{cx:.1f}" cy="{cy - dot_off:.1f}" r="{r}" fill="{STROKE}"/>'
        f'<circle cx="{cx:.1f}" cy="{cy + dot_off:.1f}" r="{r}" fill="{STROKE}"/>'
    )
    if angle_deg == 0:
        return paths
    return f'<g transform="rotate({angle_deg:.0f} {cx:.1f} {cy:.1f})">{paths}</g>'


def div_hex_side_port_x(side: Literal["left", "right"]) -> float:
    """Hex flat-side x at body mid_y (design cell coords, before side_pad_x)."""
    cx = geom.DESIGN_W / 2
    edge = DIV_HEX_R * math.cos(math.pi / 6)
    return cx - edge if side == "left" else cx + edge


def div_hex_port_cells(*, mid_y: int, pad: int = 0) -> tuple[tuple[float, int], tuple[float, int]]:
    return (
        (pad + div_hex_side_port_x("left"), mid_y),
        (pad + div_hex_side_port_x("right"), mid_y),
    )


def div_body(g: geom.SimpleGeometry) -> str:
    """Hexagon divider with horizontal division sign."""
    cx = _dx(g, geom.DESIGN_W / 2)
    cy = _mid(g)
    hex_pts = _hex_points(cx, cy, DIV_HEX_R)
    return (
        f'<polygon points="{hex_pts}" fill="{FILL}" stroke="{STROKE}" '
        f'stroke-width="{SW}" stroke-linejoin="round"/>'
        f"{_div_symbol_markup(cx, cy)}"
    )


def div2_body(g: geom.SimpleGeometry) -> str:
    """Hexagon divide-by-2; center ÷2 rendered as HTML overlay."""
    cx = _dx(g, geom.DESIGN_W / 2)
    cy = _mid(g)
    hex_pts = _hex_points(cx, cy, DIV_HEX_R)
    return (
        f'<polygon points="{hex_pts}" fill="{FILL}" stroke="{STROKE}" '
        f'stroke-width="{SW}" stroke-linejoin="round"/>'
    )


def div_n_body(g: geom.SimpleGeometry) -> str:
    """Programmable divider; division sign tilted 45° from div."""
    cx = _dx(g, geom.DESIGN_W / 2)
    cy = _mid(g)
    hex_pts = _hex_points(cx, cy, DIV_HEX_R)
    return (
        f'<polygon points="{hex_pts}" fill="{FILL}" stroke="{STROKE}" '
        f'stroke-width="{SW}" stroke-linejoin="round"/>'
        f'{_div_symbol_markup(cx, cy, angle_deg=45)}'
    )


CELL_TRI_LEFT_X = 8
CELL_TRI_TIP_X = 30
CELL_TRI_HALF_H = 15

OCC_CLK_CELL_FILL = "#b3ffff"
GEN_CELL_FILL = "#ffb3b3"
BIST_CLK_CELL_FILL = "#b3ffb3"
OCC_BIST_CLK_CELL_FILL = "#66cc66"

ASYNC_STROKE = "#cc0000"
ASYNC_CROSS_LEFT = 13
ASYNC_CROSS_RIGHT = 27
ASYNC_CROSS_HALF_H = 9

LOGIC_GATE_LEFT_X = 8
LOGIC_GATE_ARC_X = 18
LOGIC_GATE_BODY_R = 12
LOGIC_GATE_BUBBLE_R = 3
LOGIC_GATE_BUBBLE_GAP = 0
LOGIC_GATE_FILL = "#d9d9d9"
LOGIC_INPUT_TOP_Y = 22
LOGIC_INPUT_BOTTOM_Y = 38
LOGIC_LEAD_EXT = 5
LOGIC_BUFFER_TIP_X = 28
LOGIC_XOR_EXTRA_X = 4
LOGIC_OR_LEFT_ARC_RX = LOGIC_GATE_ARC_X - LOGIC_GATE_LEFT_X
LOGIC_OR_LEFT_ARC_RY = LOGIC_GATE_BODY_R


def logic_input_port_x() -> float:
    return LOGIC_GATE_LEFT_X - LOGIC_LEAD_EXT


def logic_output_port_x(*, with_bubble: bool = False, buffer: bool = False) -> float:
    if buffer:
        return LOGIC_BUFFER_TIP_X + LOGIC_LEAD_EXT
    return _logic_body_right_design(with_bubble=with_bubble) + LOGIC_LEAD_EXT


def _logic_body_right_design(*, with_bubble: bool) -> float:
    body_right = LOGIC_GATE_ARC_X + LOGIC_GATE_BODY_R
    if with_bubble:
        return body_right + 2 * LOGIC_GATE_BUBBLE_R
    return body_right


def colored_cell_body(g: geom.SimpleGeometry, fill: str) -> str:
    """Triangle clock cell with a fixed fill color."""
    cy = _mid(g)
    left = _dx(g, CELL_TRI_LEFT_X)
    tip = _dx(g, CELL_TRI_TIP_X)
    return (
        f'<polygon points="{left},{cy - CELL_TRI_HALF_H} {tip},{cy} '
        f'{left},{cy + CELL_TRI_HALF_H}" fill="{fill}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round"/>'
    )


def cell_body(g: geom.SimpleGeometry) -> str:
    return colored_cell_body(g, FILL)


def occ_clk_cell_body(g: geom.SimpleGeometry) -> str:
    return colored_cell_body(g, OCC_CLK_CELL_FILL)


def gen_cell_body(g: geom.SimpleGeometry) -> str:
    return colored_cell_body(g, GEN_CELL_FILL)


def bist_clk_cell_body(g: geom.SimpleGeometry) -> str:
    return colored_cell_body(g, BIST_CLK_CELL_FILL)


def occ_bist_clk_cell_body(g: geom.SimpleGeometry) -> str:
    return colored_cell_body(g, OCC_BIST_CLK_CELL_FILL)


def async_body(g: geom.SimpleGeometry) -> str:
    """Async marker: red cross only."""
    mid = _mid(g)
    left = _dx(g, ASYNC_CROSS_LEFT)
    right = _dx(g, ASYNC_CROSS_RIGHT)
    top = mid - ASYNC_CROSS_HALF_H
    bottom = mid + ASYNC_CROSS_HALF_H
    return (
        f'<path d="M {left} {top} L {right} {bottom} '
        f'M {right} {top} L {left} {bottom}" '
        f'fill="{FILL}" stroke="{ASYNC_STROKE}" stroke-width="2.5" '
        f'stroke-linecap="round"/>'
    )


def _logic_body_right_cell(g: geom.SimpleGeometry, *, with_bubble: bool) -> float:
    return _dx(g, _logic_body_right_design(with_bubble=with_bubble))


def _logic_input_lead_straight(g: geom.SimpleGeometry, y: float, body_left: float) -> str:
    start_x = body_left - LOGIC_LEAD_EXT
    return (
        f'<line x1="{start_x}" y1="{y}" x2="{body_left}" y2="{y}" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linecap="round"/>'
    )


def _or_left_arc_x_at_y(*, body_left: float, mid: float, y: float) -> float:
    """Right-bulging OR left arc: x on the body edge at cell y."""
    dy = y - mid
    if abs(dy) >= LOGIC_OR_LEFT_ARC_RY:
        return body_left
    bump = LOGIC_OR_LEFT_ARC_RX * math.sqrt(1 - (dy / LOGIC_OR_LEFT_ARC_RY) ** 2)
    return body_left + bump


def _or_left_arc_x_at_y_from_outside(*, body_left: float, mid: float, y: float) -> float:
    """OR left arc: first x on the arc when approaching horizontally from the left."""
    dy = y - mid
    if abs(dy) >= LOGIC_OR_LEFT_ARC_RY:
        return body_left
    bump = LOGIC_OR_LEFT_ARC_RX * math.sqrt(1 - (dy / LOGIC_OR_LEFT_ARC_RY) ** 2)
    return body_left + LOGIC_OR_LEFT_ARC_RX - bump


def _logic_input_lead_or(g: geom.SimpleGeometry, y: float, body_left: float) -> str:
    mid = _mid(g)
    arc_x = _or_left_arc_x_at_y(body_left=body_left, mid=mid, y=y)
    start_x = body_left - LOGIC_LEAD_EXT
    return (
        f'<line x1="{start_x}" y1="{y}" x2="{arc_x:.2f}" y2="{y}" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linecap="round"/>'
    )


def xor_extra_input_arc_x_at_y(*, extra_left: float, mid: float, y: float) -> float:
    """X on the extra XOR arc at input y — same _or_left_arc_x_at_y convention as OR inputs."""
    return _or_left_arc_x_at_y(body_left=extra_left, mid=mid, y=y)


def _logic_input_lead_xor(g: geom.SimpleGeometry, y: float) -> str:
    """XOR/XNOR: input stub ends on the extra left arc, not the main OR body."""
    mid = _mid(g)
    extra = _dx(g, LOGIC_XOR_EXTRA_X)
    arc_x = xor_extra_input_arc_x_at_y(extra_left=extra, mid=mid, y=y)
    start_x = _dx(g, LOGIC_GATE_LEFT_X) - LOGIC_LEAD_EXT
    return (
        f'<line x1="{start_x}" y1="{y}" x2="{arc_x:.2f}" y2="{y}" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linecap="round"/>'
    )


def _logic_output_lead(g: geom.SimpleGeometry, body_right: float, y: float) -> str:
    end_x = body_right + LOGIC_LEAD_EXT
    return (
        f'<line x1="{body_right}" y1="{y}" x2="{end_x}" y2="{y}" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linecap="round"/>'
    )


def _logic_arc_body(g: geom.SimpleGeometry) -> str:
    mid = _mid(g)
    top_y = mid - LOGIC_GATE_BODY_R
    bot_y = mid + LOGIC_GATE_BODY_R
    left = _dx(g, LOGIC_GATE_LEFT_X)
    arc = _dx(g, LOGIC_GATE_ARC_X)
    return (
        f'<path d="M {left} {top_y} L {arc} {top_y} '
        f'A {LOGIC_GATE_BODY_R} {LOGIC_GATE_BODY_R} 0 1 1 {arc} {bot_y} '
        f'L {left} {bot_y} Z" fill="{LOGIC_GATE_FILL}" stroke="{STROKE}" '
        f'stroke-width="{SW}" stroke-linejoin="miter"/>'
    )


def _logic_bubble(g: geom.SimpleGeometry, body_right_design: float) -> str:
    mid = _mid(g)
    bubble = _dx(g, body_right_design + LOGIC_GATE_BUBBLE_R)
    return _inversion_bubble(bubble, mid, LOGIC_GATE_BUBBLE_R)


def _logic_arc_gate(
    g: geom.SimpleGeometry,
    *,
    with_bubble: bool = False,
) -> str:
    mid = _mid(g)
    left = _dx(g, LOGIC_GATE_LEFT_X)
    body_right = _logic_body_right_cell(g, with_bubble=with_bubble)
    parts = [
        _logic_arc_body(g),
        _logic_input_lead_straight(g, LOGIC_INPUT_TOP_Y, left),
        _logic_input_lead_straight(g, LOGIC_INPUT_BOTTOM_Y, left),
        _logic_output_lead(g, body_right, mid),
    ]
    if with_bubble:
        body_edge = _logic_body_right_design(with_bubble=False)
        parts.insert(1, _logic_bubble(g, body_edge))
    return "".join(parts)


def and_body(g: geom.SimpleGeometry) -> str:
    return _logic_arc_gate(g)


def nand_body(g: geom.SimpleGeometry) -> str:
    return _logic_arc_gate(g, with_bubble=True)


def _or_shape(g: geom.SimpleGeometry) -> str:
    """OR/NOR body: same D skeleton as AND; left vertical is a right-bulging elliptic arc."""
    mid = _mid(g)
    top_y = mid - LOGIC_GATE_BODY_R
    bot_y = mid + LOGIC_GATE_BODY_R
    left = _dx(g, LOGIC_GATE_LEFT_X)
    arc = _dx(g, LOGIC_GATE_ARC_X)
    return (
        f'<path d="M {left} {top_y} L {arc} {top_y} '
        f'A {LOGIC_GATE_BODY_R} {LOGIC_GATE_BODY_R} 0 1 1 {arc} {bot_y} '
        f'L {left} {bot_y} '
        f'A {LOGIC_OR_LEFT_ARC_RX} {LOGIC_OR_LEFT_ARC_RY} 0 0 0 {left} {top_y} Z" '
        f'fill="{LOGIC_GATE_FILL}" stroke="{STROKE}" stroke-width="{SW}" '
        f'stroke-linejoin="miter"/>'
    )


def or_body(g: geom.SimpleGeometry) -> str:
    left = _dx(g, LOGIC_GATE_LEFT_X)
    body_right = _logic_body_right_cell(g, with_bubble=False)
    mid = _mid(g)
    return (
        f"{_or_shape(g)}"
        f'{_logic_input_lead_or(g, LOGIC_INPUT_TOP_Y, left)}'
        f'{_logic_input_lead_or(g, LOGIC_INPUT_BOTTOM_Y, left)}'
        f'{_logic_output_lead(g, body_right, mid)}'
    )


def nor_body(g: geom.SimpleGeometry) -> str:
    left = _dx(g, LOGIC_GATE_LEFT_X)
    body_edge = _logic_body_right_design(with_bubble=False)
    body_right = _logic_body_right_cell(g, with_bubble=True)
    mid = _mid(g)
    return (
        f"{_or_shape(g)}"
        f'{_logic_input_lead_or(g, LOGIC_INPUT_TOP_Y, left)}'
        f'{_logic_input_lead_or(g, LOGIC_INPUT_BOTTOM_Y, left)}'
        f"{_logic_bubble(g, body_edge)}"
        f'{_logic_output_lead(g, body_right, mid)}'
    )


def _xor_extra_input_line(g: geom.SimpleGeometry) -> str:
    """Second left arc for XOR/XNOR, parallel to the OR body left arc."""
    mid = _mid(g)
    extra = _dx(g, LOGIC_XOR_EXTRA_X)
    top = mid - LOGIC_GATE_BODY_R
    bottom = mid + LOGIC_GATE_BODY_R
    return (
        f'<path d="M {extra} {bottom} '
        f'A {LOGIC_OR_LEFT_ARC_RX} {LOGIC_OR_LEFT_ARC_RY} 0 0 0 {extra} {top}" '
        f'fill="none" stroke="{STROKE}" stroke-width="{SW}" stroke-linecap="round"/>'
    )


def _xor_gate(g: geom.SimpleGeometry, *, with_bubble: bool = False) -> str:
    body_edge = _logic_body_right_design(with_bubble=False)
    body_right = _logic_body_right_cell(g, with_bubble=with_bubble)
    mid = _mid(g)
    parts = [
        _or_shape(g),
        _xor_extra_input_line(g),
        _logic_input_lead_xor(g, LOGIC_INPUT_TOP_Y),
        _logic_input_lead_xor(g, LOGIC_INPUT_BOTTOM_Y),
        _logic_output_lead(g, body_right, mid),
    ]
    if with_bubble:
        parts.insert(2, _logic_bubble(g, body_edge))
    return "".join(parts)


def xor_body(g: geom.SimpleGeometry) -> str:
    return _xor_gate(g)


def xnor_body(g: geom.SimpleGeometry) -> str:
    return _xor_gate(g, with_bubble=True)


def buffer_body(g: geom.SimpleGeometry) -> str:
    mid = _mid(g)
    left = _dx(g, LOGIC_GATE_LEFT_X)
    tip = _dx(g, LOGIC_BUFFER_TIP_X)
    return (
        f'<polygon points="{left},{mid} {left},{mid - LOGIC_GATE_BODY_R} '
        f'{tip},{mid} {left},{mid + LOGIC_GATE_BODY_R}" fill="{LOGIC_GATE_FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round"/>'
        f'{_logic_input_lead_straight(g, mid, left)}'
        f'{_logic_output_lead(g, tip, mid)}'
    )


def _gate_path_only(g: geom.SimpleGeometry) -> str:
    """Clock gate outline without the right inversion bubble."""
    mid = _mid(g)
    top_y = mid - GATE_BODY_R
    bot_y = mid + GATE_BODY_R
    left = _dx(g, GATE_LEFT_X)
    arc = _dx(g, GATE_ARC_X)
    return (
        f'<path d="M {left} {top_y} L {arc} {top_y} '
        f'A {GATE_BODY_R} {GATE_BODY_R} 0 1 1 {arc} {bot_y} '
        f'L {left} {bot_y} Z" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="miter"/>'
    )


CLK_PHASE_SEL_BOX_LEFT = 4
CLK_PHASE_SEL_BOX_RIGHT = 36
CLK_PHASE_SEL_BOX_HALF_H = 18
CLK_PHASE_SEL_WAVE_PHASES = (0, 5, 10)
CLK_PHASE_SEL_WAVE_INSET = 4
CLK_PHASE_SEL_WAVE_RUN = 16


def _clk_phase_sel_wave_rows(
    mid: float,
    half_h: int = CLK_PHASE_SEL_BOX_HALF_H,
) -> tuple[tuple[int, int, int], ...]:
    """Per-row (phase, hi, lo) in cell y; shared by body SVG and port geometry."""
    top = mid - half_h
    rows: list[tuple[int, int, int]] = []
    for index, phase in enumerate(CLK_PHASE_SEL_WAVE_PHASES):
        y = top + 6 + index * 10
        rows.append((phase, y, y + 5))
    return tuple(rows)


def clk_phase_sel_output_positions(
    mid: float,
    half_h: int = CLK_PHASE_SEL_BOX_HALF_H,
) -> tuple[tuple[float, float], ...]:
    """Output ports on the right box edge, one per wave row."""
    return tuple(
        (CLK_PHASE_SEL_BOX_RIGHT, lo)
        for _phase, _hi, lo in _clk_phase_sel_wave_rows(mid, half_h)
    )


def clk_phase_sel_output_cell_positions(
    pad: int,
    mid: int,
    half_h: int = CLK_PHASE_SEL_BOX_HALF_H,
) -> tuple[tuple[float, float], ...]:
    return tuple(
        (pad + x, y) for x, y in clk_phase_sel_output_positions(mid, half_h)
    )


def clk_phase_sel_body(g: geom.SimpleGeometry) -> str:
    """Three phase-shifted square waves."""
    mid = _mid(g)
    box_left = _dx(g, CLK_PHASE_SEL_BOX_LEFT)
    box_right = _dx(g, CLK_PHASE_SEL_BOX_RIGHT)
    top = mid - CLK_PHASE_SEL_BOX_HALF_H
    bottom = mid + CLK_PHASE_SEL_BOX_HALF_H
    waves = []
    for phase, hi, lo in _clk_phase_sel_wave_rows(mid, CLK_PHASE_SEL_BOX_HALF_H):
        x = box_left + CLK_PHASE_SEL_WAVE_INSET
        waves.append(
            f"M {x + phase} {lo} L {x + phase} {hi} "
            f"L {x + phase + 7} {hi} L {x + phase + 7} {lo} "
            f"L {x + phase + CLK_PHASE_SEL_WAVE_RUN} {lo}"
        )
    wave_paths = " ".join(
        f'<path d="{path}" fill="{FILL}" stroke="{STROKE}" stroke-width="1.2" '
        f'stroke-linecap="square"/>'
        for path in waves
    )
    return (
        f'<rect x="{box_left}" y="{top}" width="{box_right - box_left}" '
        f'height="{bottom - top}" fill="{FILL}" stroke="{STROKE}" stroke-width="{SW}"/>'
        f"{wave_paths}"
    )


DTO_CHIP_LEFT = 6
DTO_CHIP_W = 28
DTO_CHIP_H = 26


def _dto_chip_top(mid: int) -> int:
    return mid - DTO_CHIP_H // 2


def dto_chip_port_cells(*, mid_y: int, pad: int = 0) -> tuple[tuple[int, int], tuple[int, int]]:
    return (
        (pad + DTO_CHIP_LEFT, mid_y),
        (pad + DTO_CHIP_LEFT + DTO_CHIP_W, mid_y),
    )


def dto_body(g: geom.SimpleGeometry) -> str:
    """Rounded chip with duty waveform."""
    mid = _mid(g)
    top = _dto_chip_top(mid)
    left = _dx(g, DTO_CHIP_LEFT)
    wave_left = _dx(g, DTO_CHIP_LEFT + 4)
    wave_mid_a = _dx(g, DTO_CHIP_LEFT + 9)
    wave_mid_b = _dx(g, DTO_CHIP_LEFT + 14)
    wave_right = _dx(g, DTO_CHIP_LEFT + DTO_CHIP_W - 4)
    wave_top = mid - 7
    wave_bot = mid + 1
    return (
        f'<rect x="{left}" y="{top}" width="{DTO_CHIP_W}" height="{DTO_CHIP_H}" rx="5" ry="5" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}"/>'
        f'<path d="M {wave_left} {wave_bot} L {wave_left} {wave_top + 3} L {wave_mid_a} {wave_top + 3} '
        f'L {wave_mid_a} {wave_bot - 2} L {wave_mid_b} {wave_bot - 2} L {wave_mid_b} {wave_top} L {wave_right} {wave_top}" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.5" stroke-linecap="square"/>'
    )


def dto_n_body(g: geom.SimpleGeometry) -> str:
    """DTO_N chip with vertically mirrored duty waveform."""
    mid = _mid(g)
    top = _dto_chip_top(mid)
    left = _dx(g, DTO_CHIP_LEFT)
    wave_left = _dx(g, DTO_CHIP_LEFT + 4)
    wave_mid_a = _dx(g, DTO_CHIP_LEFT + 9)
    wave_mid_b = _dx(g, DTO_CHIP_LEFT + 14)
    wave_right = _dx(g, DTO_CHIP_LEFT + DTO_CHIP_W - 4)
    wave_top = mid - 7
    wave_bot = mid + 1
    return (
        f'<rect x="{left}" y="{top}" width="{DTO_CHIP_W}" height="{DTO_CHIP_H}" rx="5" ry="5" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}"/>'
        f'<path d="M {wave_left} {wave_top} L {wave_left} {wave_bot - 3} L {wave_mid_a} {wave_bot - 3} '
        f'L {wave_mid_a} {wave_top + 2} L {wave_mid_b} {wave_top + 2} L {wave_mid_b} {wave_bot} L {wave_right} {wave_bot}" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.5" stroke-linecap="square"/>'
    )


INV_PORT_LEFT_X = 8
INV_TIP_X = 28
INV_BUBBLE_R = 3
INV_BUBBLE_CX = INV_TIP_X + INV_BUBBLE_R
INV_RIGHT_PORT_X = INV_BUBBLE_CX + INV_BUBBLE_R


INV_MUX_MARKER_HALF = INV_BUBBLE_R


def inv_body(g: geom.SimpleGeometry) -> str:
    mid = _mid(g)
    left = _dx(g, INV_PORT_LEFT_X)
    tip = _dx(g, INV_TIP_X)
    bubble = _dx(g, INV_BUBBLE_CX)
    return (
        f'<polygon points="{left},{mid} {left},13 '
        f'{tip},{mid} {left},47" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round"/>'
        f'{_inversion_bubble(bubble, mid, INV_BUBBLE_R)}'
    )


def inv_mux_body(g: geom.SimpleGeometry) -> str:
    """Triangle inverter with a single inverted output (hollow square marker)."""
    mid = _mid(g)
    left = _dx(g, INV_PORT_LEFT_X)
    tip = _dx(g, INV_TIP_X)
    marker_cx = _dx(g, INV_BUBBLE_CX)
    half = INV_MUX_MARKER_HALF
    return (
        f'<polygon points="{left},{mid} {left},13 '
        f'{tip},{mid} {left},47" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round"/>'
        f'<rect x="{marker_cx - half:.1f}" y="{mid - half:.1f}" width="{half * 2:.1f}" '
        f'height="{half * 2:.1f}" fill="{FILL}" stroke="{STROKE}" stroke-width="{SW}"/>'
    )


PLL_LEFT_X = 2
PLL_SHOULDER_X = 30
PLL_TIP_X = 38
PLL_BODY_HALF_H = 14
PLL_LEFT_NOTCH_HALF = 8
PLL_LABEL_CX = (PLL_LEFT_X + PLL_SHOULDER_X) / 2


def pll_label_cx(g: geom.SimpleGeometry) -> float:
    return _dx(g, PLL_LABEL_CX)


def pll_body(g: geom.SimpleGeometry) -> str:
    """PLL: tag with left input notch, closed sides above/below notch, tip on the right."""
    mid = _mid(g)
    top_y = mid - PLL_BODY_HALF_H
    bot_y = mid + PLL_BODY_HALF_H
    lx = _dx(g, PLL_LEFT_X)
    sx = _dx(g, PLL_SHOULDER_X)
    tx = _dx(g, PLL_TIP_X)
    notch_top = mid - PLL_LEFT_NOTCH_HALF
    notch_bot = mid + PLL_LEFT_NOTCH_HALF
    return (
        f'<path d="M {lx} {top_y} L {sx} {top_y} L {tx} {mid} L {sx} {bot_y} L {lx} {bot_y} '
        f"L {lx} {notch_bot} M {lx} {notch_top} L {lx} {top_y}\" fill=\"{FILL}\" "
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round" '
        f'stroke-linecap="round"/>'
    )


SOURCE_CX = geom.DESIGN_W / 2
SOURCE_R = 14
SOURCE_PORT_X = int(SOURCE_CX + SOURCE_R)
SOURCE_WAVE_PERIODS = 1.5
SOURCE_WAVE_AMP = 5
SOURCE_WAVE_INSET = 6


PAD_LEFT_X = 10
PAD_RIGHT_X = 30
PAD_HALF_H = 12


def pad_body(g: geom.SimpleGeometry) -> str:
    """I/O pad: hollow block; output on the right."""
    mid = _mid(g)
    left = _dx(g, PAD_LEFT_X)
    right = _dx(g, PAD_RIGHT_X)
    top = mid - PAD_HALF_H
    bottom = mid + PAD_HALF_H
    return (
        f'<rect x="{left:.1f}" y="{top}" width="{right - left:.1f}" '
        f'height="{bottom - top}" rx="2" ry="2" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}"/>'
    )


def source_body(g: geom.SimpleGeometry) -> str:
    """Clock source: circle with sine wave; output on the right."""
    mid = _mid(g)
    cx = _dx(g, SOURCE_CX)
    r = SOURCE_R
    left = cx - r + SOURCE_WAVE_INSET
    right = cx + r - SOURCE_WAVE_INSET
    span = right - left
    amp = SOURCE_WAVE_AMP
    steps = 12
    pts = [f"M {left:.1f} {mid:.1f}"]
    for i in range(1, steps + 1):
        t = i / steps
        x = left + t * span
        y = mid + amp * math.sin(t * math.pi * 2 * SOURCE_WAVE_PERIODS)
        pts.append(f"L {x:.1f} {y:.1f}")
    wave = " ".join(pts)
    return (
        f'<circle cx="{cx:.1f}" cy="{mid}" r="{r}" fill="{FILL}" stroke="{STROKE}" '
        f'stroke-width="{SW}"/>'
        f'<path d="{wave}" fill="{FILL}" stroke="{STROKE}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )


CLOCK_WAVE_PERIODS = 4
CLOCK_WAVE_AMP = 6
CLOCK_SW = 1.5
CLOCK_BODY_MARGIN_X = 2
CLOCK_LEAD_EXT = 5
CLOCK_GRAPHIC_W = geom.DESIGN_W - CLOCK_LEAD_EXT
CLOCK_NAME_SIDE_PAD = 0
CLOCK_CELL_W = geom.W
CLOCK_LEFT_PAD = CLOCK_NAME_SIDE_PAD + CLOCK_LEAD_EXT
CLOCK_WAVE_W = CLOCK_GRAPHIC_W - 2 * CLOCK_BODY_MARGIN_X


def _clock_wave_pitch_bar(wave_w: int) -> tuple[int, int]:
    pitch = wave_w // CLOCK_WAVE_PERIODS
    bar = max(pitch // 2, 1)
    return pitch, bar


def clock_body(g: geom.SimpleGeometry) -> str:
    """Clock terminal: square wave with left input lead on the wave bottom rail."""
    mid = g.body_mid_y
    rect = g.body
    wave_w = rect.w
    pitch, bar = _clock_wave_pitch_bar(wave_w)
    amp = CLOCK_WAVE_AMP
    y_hi = mid - amp
    y_lo = mid + amp
    wave_left = rect.x
    wave_right = rect.x + wave_w
    lead_x = CLOCK_NAME_SIDE_PAD
    segments = [f"M {lead_x} {y_lo} L {wave_left} {y_lo}", f"M {wave_right} {y_lo}"]
    x = wave_right
    for _ in range(CLOCK_WAVE_PERIODS):
        segments.append(
            f"L {x} {y_hi} L {x - bar} {y_hi} L {x - bar} {y_lo} L {x - pitch} {y_lo}"
        )
        x -= pitch
    path = " ".join(segments)
    return (
        f'<path d="{path}" fill="{FILL}" stroke="{STROKE}" stroke-width="{CLOCK_SW}" '
        f'stroke-linecap="square" stroke-linejoin="miter"/>'
    )


def wire_body(g: geom.SimpleGeometry) -> str:
    y = geom.WIRE_STROKE_Y
    amp = 5
    x0 = geom.side_pad_x(g.cell_w)
    x1 = x0 + geom.DESIGN_W
    return (
        f'<path d="M {x0} {y} Q {x0 + 5} {y - amp} {x0 + 10} {y} T {x0 + 20} {y} T {x0 + 30} {y} T {x1} {y}" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="{SW}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )
