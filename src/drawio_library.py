from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LABEL_PLACEHOLDER_RE = re.compile(
    r"%(?:name|pll_kind|in\d+_label)%"
)

from drawio_decode import decompress_diagram_payload


def package_root() -> Path:
    """Repository root in dev; PyInstaller extract dir when frozen."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


DEFAULT_LIBRARY_PATH = package_root() / "drawio-lib" / "drawclock.xml"


@dataclass(frozen=True)
class LibraryShape:
    """One shape from drawclock.xml (style + HTML label + default size)."""

    title: str
    style: str
    label: str
    w: int
    h: int


def load_library_titles(path: str | Path) -> set[str]:
    text = Path(path).read_text(encoding="utf-8").strip()
    if text.startswith("<mxlibrary>"):
        text = text[len("<mxlibrary>") : -len("</mxlibrary>")].strip()
    entries = json.loads(text)
    if not isinstance(entries, list):
        raise ValueError("器件库不是 mxlibrary 数组")
    titles: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title")
        if title:
            titles.add(str(title))
    if not titles:
        raise ValueError("器件库未包含任何形状")
    return titles


def validate_layout_types(layout_types: set[str], library_titles: set[str]) -> None:
    missing = sorted(layout_types - library_titles)
    if missing:
        raise ValueError(f"布局中的 drawclock 类型不在器件库中: {', '.join(missing)}")


def load_library_shapes(path: str | Path | None = None) -> dict[str, LibraryShape]:
    """Parse drawclock.xml: mxCell style, object label HTML, and default w/h per title."""
    lib_path = Path(path) if path is not None else DEFAULT_LIBRARY_PATH
    text = lib_path.read_text(encoding="utf-8").strip()
    if text.startswith("<mxlibrary>"):
        text = text[len("<mxlibrary>") : -len("</mxlibrary>")].strip()
    entries = json.loads(text)
    if not isinstance(entries, list):
        raise ValueError("器件库不是 mxlibrary 数组")
    shapes: dict[str, LibraryShape] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title")
        payload = entry.get("xml")
        w = entry.get("w")
        h = entry.get("h")
        if not title or not payload or w is None or h is None:
            continue
        parsed = _parse_library_payload(str(payload))
        if parsed is None:
            continue
        style, label = parsed
        shapes[str(title)] = LibraryShape(
            title=str(title),
            style=style,
            label=label,
            w=int(w),
            h=int(h),
        )
    if not shapes:
        raise ValueError("器件库未解析到任何形状")
    return shapes


def load_library_cell_styles(path: str | Path | None = None) -> dict[str, str]:
    return {title: shape.style for title, shape in load_library_shapes(path).items()}


def _parse_library_payload(payload: str) -> tuple[str, str] | None:
    xml_text = payload.strip()
    if not xml_text.startswith("<"):
        xml_text = decompress_diagram_payload(payload)
    root = ET.fromstring(xml_text)
    style: str | None = None
    label = ""
    for obj in root.iter("object"):
        if obj.find("mxCell") is not None:
            label = obj.get("label") or ""
            break
    for mxcell in root.iter("mxCell"):
        if mxcell.get("vertex") == "1":
            style = mxcell.get("style")
            break
    if not style:
        return None
    return style, label


@lru_cache(maxsize=4)
def _cached_library_shapes(library_path: str) -> dict[str, LibraryShape]:
    return load_library_shapes(library_path)


@lru_cache(maxsize=4)
def _cached_library_styles(library_path: str) -> dict[str, str]:
    return load_library_cell_styles(library_path)


def canonical_vertex_style(
    drawclock_type: str,
    stored_style: str,
    *,
    library_path: str | Path | None = None,
) -> str:
    """Use embedded library HTML style when the diagram only has drawclockType metadata."""
    shape = _cached_library_shapes(str(library_path or DEFAULT_LIBRARY_PATH)).get(
        drawclock_type
    )
    if shape is None:
        return stored_style
    if "html=1" in stored_style and f"drawclockType={drawclock_type}" in stored_style:
        return stored_style
    return shape.style


DEFAULT_PLL_KIND = "SC"


def bake_label_placeholders(label: str, attrs: dict[str, str]) -> str:
    """Replace editable placeholders with object attribute values for draw.io display."""
    baked = label
    name = attrs.get("name", "")
    if name:
        baked = baked.replace("%name%", name)
    if "%pll_kind%" in baked:
        baked = baked.replace("%pll_kind%", attrs.get("pll_kind", DEFAULT_PLL_KIND))
    for index in range(6):
        key = f"in{index}_label"
        token = f"%{key}%"
        if token in baked:
            baked = baked.replace(token, str(index))
    return baked


def canonical_object_attrs(
    drawclock_type: str,
    stored_attrs: dict[str, str],
    *,
    library_path: str | Path | None = None,
) -> dict[str, str]:
    """Ensure object carries baked label HTML (no %placeholders%) for draw.io display."""
    out = dict(stored_attrs)
    shape = _cached_library_shapes(str(library_path or DEFAULT_LIBRARY_PATH)).get(
        drawclock_type
    )
    label = out.get("label", "").strip()
    if not label and shape is not None:
        label = shape.label
    if label:
        out["label"] = bake_label_placeholders(label, out)
        if not LABEL_PLACEHOLDER_RE.search(out["label"]):
            out["placeholders"] = "0"
    return out


def reload_object_attrs(
    drawclock_type: str,
    stored_attrs: dict[str, str],
    *,
    library_path: str | Path | None = None,
) -> dict[str, str]:
    """Apply library label template with placeholders=1; keep diagram attrs as-is."""
    lib = str(library_path or DEFAULT_LIBRARY_PATH)
    shape = _cached_library_shapes(lib).get(drawclock_type)
    if shape is None:
        return canonical_object_attrs(drawclock_type, stored_attrs, library_path=lib)
    out = {
        key: value
        for key, value in stored_attrs.items()
        if key not in ("label", "placeholders") and value is not None
    }
    if not out.get("name"):
        out["name"] = drawclock_type
    out["label"] = shape.label
    out["placeholders"] = "1"
    return out
