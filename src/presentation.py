"""Validated drawing defaults shared by Python, CLI and SVG rendering."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
import json
import math
import re
from typing import Any, Mapping


ALIGNMENTS = ("left", "center", "right")
ANCHORS = ("top-left", "top", "top-right", "right", "bottom-right", "bottom", "bottom-left", "left")
TEXT_ANCHORS = {"left": "start", "center": "middle", "right": "end"}
LEGACY_FREQUENCIES = (("func_freq", "工作频率"), ("scan_freq", "SCAN"), ("bist_freq", "BIST"))


def finite_number(value: Any, name: str, *, minimum: float | None = None) -> float:
    """Reject booleans, non-numbers and non-finite geometry before layout."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise ValueError(f"{name} must be finite and >= {minimum}" if minimum is not None else f"{name} must be finite")
    return number


@dataclass(frozen=True)
class DrawingOptions:
    """Global presentation defaults; individual node descriptions may override them."""

    description_align: str = "left"
    """Alignment of lines inside each description block."""
    description_anchor: str = "top-left"
    """One of the eight positions outside the node's visible body."""
    description_offset_x: float = 0.0
    """Horizontal translation from the selected description anchor, in pixels."""
    description_offset_y: float = 0.0
    """Vertical translation from the selected description anchor, in pixels."""
    horizontal_spacing: float | None = None
    """Minimum horizontal layer gap; None retains the selected layout profile."""
    name_align: str = "center"
    """Alignment of explicit lines within a node name."""
    frequency_headers: tuple[str, ...] = ()
    """Column headings for frequency arrays; each string may contain newlines."""
    frequency_align: str = "center"
    """Alignment of frequency headings and cell contents within each column."""

    def __post_init__(self) -> None:
        for key in ("description_align", "name_align", "frequency_align"):
            if getattr(self, key) not in ALIGNMENTS:
                raise ValueError(f"{key} must be one of {ALIGNMENTS}")
        if self.description_anchor not in ANCHORS:
            raise ValueError(f"description_anchor must be one of {ANCHORS}")
        for key in ("description_offset_x", "description_offset_y"):
            finite_number(getattr(self, key), key)
        if self.horizontal_spacing is not None:
            finite_number(self.horizontal_spacing, "horizontal_spacing", minimum=0.0)
        if not isinstance(self.frequency_headers, (tuple, list)) or not all(isinstance(s, str) for s in self.frequency_headers):
            raise ValueError("frequency_headers must be an array of strings")
        object.__setattr__(self, "frequency_headers", tuple(self.frequency_headers))

    def description(self, attrs: Mapping[str, Any]) -> tuple[str, str, float, float]:
        """Resolve each explicit node property independently over global defaults."""
        selected = {field.name: getattr(self, field.name) for field in fields(self)}
        for key in ("description_align", "description_anchor", "description_offset_x", "description_offset_y"):
            if key in attrs:
                value = attrs[key]
                selected[key] = float(value) if key.startswith("description_offset_") else value
        effective = DrawingOptions(**selected)
        return (effective.description_align, effective.description_anchor,
                float(effective.description_offset_x), float(effective.description_offset_y))


def text_lines(value: str) -> tuple[str, ...]:
    """Preserve explicit blank lines while normalizing common newline encodings."""
    return tuple(value.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def text_width(value: str, font_size: float) -> float:
    """Conservative width of the widest explicit line without runtime font dependencies."""
    return max((sum(font_size * (1.1 if ord(c) > 127 else 0.68) for c in line)
                for line in text_lines(value)), default=0.0)


def frequency_values(attrs: Mapping[str, Any]) -> tuple[str, ...]:
    """Read canonical arrays; JSON strings are the internal layout representation."""
    value = attrs.get("frequencies", ())
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, (list, tuple)):
        raise ValueError("frequencies must be an array")
    result = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (str, int, float)):
            raise ValueError("frequencies entries must be strings or finite numbers")
        if isinstance(item, (int, float)):
            finite_number(item, "frequencies entry")
        result.append(str(item))
    return tuple(result)


def wrap_text(value: str, max_width: float = 230.0, font_size: float = 11.0) -> tuple[str, ...]:
    """Use the same deterministic wrapping for space reservation and rendering."""
    result = []
    for paragraph in text_lines(value):
        line, width = "", 0.0
        for char in paragraph:
            advance = font_size * (1.1 if ord(char) > 127 else 0.68)
            if line and width + advance > max_width:
                result.append(line)
                line, width = "", 0.0
            line += char
            width += advance
        result.append(line)
    return tuple(result)


def prepare_nodes(nodes: dict[str, Any], logical_edges: Any, options: DrawingOptions,
                  ranks: Mapping[str, int] | None = None) -> None:
    """Reserve text before packing while keeping artwork and physical ports unchanged."""
    from drawio_ports import port_anchors
    from visual_geometry import estimated_label_width

    outgoing = {edge.source for edge in logical_edges}
    incoming: dict[str, list[str]] = {}
    for edge in logical_edges:
        incoming.setdefault(edge.target, []).append(edge.target_port)
    column_widths: dict[Any, float] = {}
    column_edges: dict[Any, tuple[float, float]] = {}
    for name, node in nodes.items():
        if not node.item.get("description"):
            continue
        column = ranks[name] if ranks is not None else name
        width = max(text_width(line, 11.0) for line in wrap_text(node.item["description"]))
        column_widths[column] = max(column_widths.get(column, 0.0), width)
        overflow = max(0.0, (estimated_label_width(name, node.shape.label, node.shape.w) - node.shape.w) / 2)
        previous = column_edges.get(column, (-overflow, node.shape.w + overflow))
        column_edges[column] = (min(-overflow, previous[0]), max(node.shape.w + overflow, previous[1]))
    for name, node in nodes.items():
        shape = node.shape
        description = node.item.get("description", "")
        name_lines = len(text_lines(name))
        values = (frequency_values(node.item) if "frequencies" in node.item else
                  tuple(str(node.item.get(key, "")) for key, _ in LEGACY_FREQUENCIES))
        cell_lines = max((len(text_lines(value)) for value in values), default=1) if name not in outgoing else 1
        if not description and name_lines <= 1 and cell_lines <= 1:
            continue
        w, h = float(shape.w), float(shape.h)
        font = max((float(v) for v in re.findall(r"font-size\s*:\s*([0-9.]+)px", shape.label)), default=11.0)
        extra_name = max(0, name_lines - 1) * font * 1.3
        name_overflow = max(0.0, (estimated_label_width(name, shape.label, w) - w) / 2)
        owner_left, owner_right = -name_overflow, w + name_overflow
        owner_bottom = h + extra_name + 9.0
        top_pad, bottom_pad = 0.0, extra_name + 9.0
        left_overflow = right_overflow = name_overflow
        if description:
            _, anchor, dx, dy = options.description(node.item)
            lines = wrap_text(description)
            column = ranks[name] if ranks is not None else name
            width = max(5.5, column_widths[column])
            height = len(lines) * 15.0
            owner_left, owner_right = column_edges[column]
            center_x, center_y = (owner_left + owner_right) / 2, owner_bottom / 2
            positions = {
                "top-left": (owner_left, -height - 8),
                "top": (center_x - width / 2, -height - 8),
                "top-right": (owner_right - width, -height - 8),
                "right": (owner_right + 8, center_y - height / 2),
                "bottom-right": (owner_right - width, owner_bottom + 8),
                "bottom": (center_x - width / 2, owner_bottom + 8),
                "bottom-left": (owner_left, owner_bottom + 8),
                "left": (owner_left - width - 8, center_y - height / 2),
            }
            x, y = positions[anchor]
            x, y = x + dx, y + dy
            left_overflow = max(left_overflow, -x + 4)
            right_overflow = max(right_overflow, x + width - w + 4)
            top_pad = max(top_pad, -y + 4)
            bottom_pad = max(bottom_pad, y + height - h + 4)
        if cell_lines > 1:
            anchors = port_anchors(shape.style, shape.title)
            axes = [anchors[port][1] * h for port in incoming.get(name, []) if port in anchors]
            axis = sum(axes) / len(axes) if axes else h / 2
            half = (cell_lines - 1) * 12.0 * 1.35 / 2 + 16
            top_pad = max(top_pad, half - axis + 4)
            bottom_pad = max(bottom_pad, half - (h - axis) + 4)
        new_height = h + top_pad + bottom_pad

        def resize_ports(match):
            points = json.loads(match.group(2))
            for point in points:
                point[1] = (top_pad + float(point[1]) * h) / new_height
            return match.group(1) + json.dumps(points, separators=(",", ":"))

        style = re.sub(r'((?:^|;)points=)(\[\[.*?\]\])', resize_ports, shape.style)
        label = (f'<div data-drawclock-body-y="{top_pad}" data-drawclock-body-height="{h}" '
                 f'data-drawclock-overflow-left="{left_overflow}" data-drawclock-overflow-right="{right_overflow}" '
                 f'style="position:absolute;left:0px;top:{top_pad}px;width:{w}px;height:{h}px;">'
                 f'{shape.label}</div>')
        defaults = {**shape.object_defaults, "label": label,
                    "_drawclock_body_box": json.dumps([0, top_pad, w, h]),
                    "_drawclock_name_extra_height": str(extra_name)}
        nodes[name] = replace(node, shape=replace(shape, style=style, label=label, h=new_height, object_defaults=defaults))
