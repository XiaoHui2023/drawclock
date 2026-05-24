from __future__ import annotations

import math

from drawio_lib.components import simple_geometry as geom
from drawio_lib.components.label_attrs import CLOCK_FREQ_GAP_PX, CLOCK_FREQ_TEXT_RESERVE_PX

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


DIV_SYMBOL_Y_OFFSET = -2
DIV_LABEL_Y_OFFSET = 7
DIV_SYMBOL_FONT_PX = 16
DIV_CENTER_FONT_PX = 6
DIV_LABEL_FONT_PX = DIV_CENTER_FONT_PX


def div_body(g: geom.SimpleGeometry) -> str:
    """Hexagon divider (labels rendered as HTML overlay)."""
    cx = _dx(g, geom.DESIGN_W / 2)
    cy = _mid(g)
    hex_pts = _hex_points(cx, cy, 15)
    return (
        f'<polygon points="{hex_pts}" fill="{FILL}" stroke="{STROKE}" '
        f'stroke-width="{SW}" stroke-linejoin="round"/>'
    )


DTO_LABEL_Y_OFFSET = 16
DTO_CENTER_FONT_PX = 7
DTO_LABEL_FONT_PX = DTO_CENTER_FONT_PX


def dto_body(g: geom.SimpleGeometry) -> str:
    """Rounded chip with duty waveform (DTO label rendered as HTML overlay)."""
    mid = _mid(g)
    wave_top = mid - 10
    wave_bot = mid + 2
    return (
        f'<rect x="{_dx(g, 7)}" y="11" width="26" height="40" rx="5" ry="5" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}"/>'
        f'<path d="M {_dx(g, 11)} {wave_bot} L {_dx(g, 11)} {wave_top + 4} L {_dx(g, 16)} {wave_top + 4} '
        f'L {_dx(g, 16)} {wave_bot - 3} L {_dx(g, 21)} {wave_bot - 3} L {_dx(g, 21)} {wave_top} L {_dx(g, 29)} {wave_top}" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.5" stroke-linecap="square"/>'
    )


INV_PORT_LEFT_X = 8
INV_TIP_X = 28


def inv_body(g: geom.SimpleGeometry) -> str:
    mid = _mid(g)
    left = _dx(g, INV_PORT_LEFT_X)
    tip = _dx(g, INV_TIP_X)
    return (
        f'<polygon points="{left},{mid} {left},13 '
        f'{tip},{mid} {left},47" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round"/>'
    )


PLL_LEFT_X = 2
PLL_SHOULDER_X = 28
PLL_TIP_X = 36
PLL_LABEL_CX = (PLL_LEFT_X + PLL_SHOULDER_X) / 2


def pll_label_cx(g: geom.SimpleGeometry) -> float:
    return _dx(g, PLL_LABEL_CX)


def pll_body(g: geom.SimpleGeometry) -> str:
    """PLL: right-pointing tag; open left, parallel top/bottom, tip on the right."""
    mid = _mid(g)
    top_y = mid - 10
    bot_y = mid + 10
    return (
        f'<path d="M {_dx(g, PLL_LEFT_X)} {top_y} L {_dx(g, PLL_SHOULDER_X)} {top_y} L {_dx(g, PLL_TIP_X)} {mid} '
        f'L {_dx(g, PLL_SHOULDER_X)} {bot_y} L {_dx(g, PLL_LEFT_X)} {bot_y}" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round" '
        f'stroke-linecap="round"/>'
    )


CLOCK_WAVE_PERIODS = 4
CLOCK_WAVE_AMP = 6
CLOCK_SW = 1.5
CLOCK_BODY_MARGIN_X = 2
CLOCK_GRAPHIC_W = geom.DESIGN_W
CLOCK_RIGHT_PAD = CLOCK_FREQ_GAP_PX + CLOCK_FREQ_TEXT_RESERVE_PX
CLOCK_LEFT_PAD = 60
CLOCK_CELL_W = CLOCK_LEFT_PAD + CLOCK_GRAPHIC_W + CLOCK_RIGHT_PAD
CLOCK_WAVE_W = CLOCK_GRAPHIC_W - 2 * CLOCK_BODY_MARGIN_X


def _clock_wave_pitch_bar(wave_w: int) -> tuple[int, int]:
    pitch = wave_w // CLOCK_WAVE_PERIODS
    bar = max(pitch // 2, 1)
    return pitch, bar


def clock_body(g: geom.SimpleGeometry) -> str:
    """Clock terminal: 50% duty square wave only (text rendered outside this SVG)."""
    mid = g.body_mid_y
    rect = g.body
    wave_w = rect.w
    pitch, bar = _clock_wave_pitch_bar(wave_w)
    amp = CLOCK_WAVE_AMP
    y_hi = mid - amp
    y_lo = mid + amp
    x0 = rect.x
    x = x0
    segments = [f"M {x} {y_lo}"]
    for _ in range(CLOCK_WAVE_PERIODS):
        segments.append(
            f"L {x} {y_hi} L {x + bar} {y_hi} L {x + bar} {y_lo} L {x + pitch} {y_lo}"
        )
        x += pitch
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
