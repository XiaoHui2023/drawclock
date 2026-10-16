from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


_TAG_RE = re.compile(r"<[^>]+>")
_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([0-9.]+)px", re.IGNORECASE)
_OVERFLOW_RE = re.compile(r'data-drawclock-overflow-(left|right)="([0-9.]+)"')


@dataclass(frozen=True)
class VisualBox:
    """Conservative visible footprint used by layout and independent QA."""

    left: float
    top: float
    right: float
    bottom: float

    def inflated(self, distance: float) -> tuple[float, float, float, float]:
        return (
            self.left - distance,
            self.top - distance,
            self.right + distance,
            self.bottom + distance,
        )


def _plain_text(label: str) -> str:
    return html.unescape(_TAG_RE.sub("", label)).strip()


@lru_cache(maxsize=None)
def estimated_label_width(
    name: str,
    label: str,
    cell_width: float,
) -> float:
    """Estimate horizontal HTML-label overflow without assuming a component kind.

    The component library owns its fixed cell size, while an instance name may
    be wider because draw.io HTML labels use ``overflow=visible``.  The estimate
    intentionally uses only artifact text and CSS, so arbitrary compatible
    libraries receive the same treatment.
    """
    font_sizes = [float(value) for value in _FONT_SIZE_RE.findall(label)]
    font_size = max(font_sizes, default=10.0)
    visible_name = name or _plain_text(label)
    # Helvetica/Arial average advance is below 0.62 em for ordinary clock names.
    # Add one em of side bearing so a vertical channel never grazes the glyphs.
    text_width = max(
        sum(font_size * (1.1 if ord(char) > 0x7F else 0.62) for char in line)
        for line in visible_name.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ) + font_size
    reserved = max((float(v) for _, v in _OVERFLOW_RE.findall(label)), default=0.0)
    return max(float(cell_width) + 2 * reserved, text_width)


def visual_box(
    *,
    name: str,
    label: str,
    x: float,
    y: float,
    width: float,
    height: float,
    include_presentation: bool = True,
) -> VisualBox:
    visible_width = estimated_label_width(name, _OVERFLOW_RE.sub("", label), width)
    overflow = max(0.0, visible_width - width) / 2.0
    reserved = dict((side, float(value)) for side, value in _OVERFLOW_RE.findall(label)) if include_presentation else {}
    line_count = len(name.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    font_size = max((float(value) for value in _FONT_SIZE_RE.findall(label)), default=10.0)
    extra_height = (0.0 if include_presentation and 'data-drawclock-body-height=' in label
                    else max(0, line_count - 1) * font_size * 1.3)
    return VisualBox(
        left=x - max(overflow, reserved.get("left", 0.0)),
        top=y,
        right=x + width + max(overflow, reserved.get("right", 0.0)),
        bottom=y + height + extra_height,
    )


def vertex_visual_box(vertex: Any) -> VisualBox:
    return visual_box(
        name=str(vertex.logical_name or vertex.name),
        label=str(vertex.object_attrs.get("label", "")),
        x=float(vertex.x),
        y=float(vertex.y),
        width=float(vertex.width),
        height=float(vertex.height),
    )
