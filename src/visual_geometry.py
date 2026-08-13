from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any


_TAG_RE = re.compile(r"<[^>]+>")
_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([0-9.]+)px", re.IGNORECASE)


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
    text_width = len(visible_name) * font_size * 0.62 + font_size
    return max(float(cell_width), text_width)


def visual_box(
    *,
    name: str,
    label: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> VisualBox:
    visible_width = estimated_label_width(name, label, width)
    overflow = max(0.0, visible_width - width) / 2.0
    return VisualBox(
        left=x - overflow,
        top=y,
        right=x + width + overflow,
        bottom=y + height,
    )


def vertex_visual_box(vertex: Any) -> VisualBox:
    return visual_box(
        name=str(vertex.name),
        label=str(vertex.object_attrs.get("label", "")),
        x=float(vertex.x),
        y=float(vertex.y),
        width=float(vertex.width),
        height=float(vertex.height),
    )
