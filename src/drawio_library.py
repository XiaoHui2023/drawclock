from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TypeAlias

LABEL_PLACEHOLDER_RE = re.compile(
    r"%(?:name|pll_kind|ratio|in\d+_label)%"
)

from library_payload import decompress_diagram_payload


def package_root() -> Path:
    """Repository root in dev; PyInstaller extract dir when frozen."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


DEFAULT_LIBRARY_PATH = package_root() / "drawio-lib" / "drawclock.xml"
LibraryPath: TypeAlias = str | Path
LibrarySource: TypeAlias = LibraryPath | Sequence[LibraryPath]


@dataclass(frozen=True)
class LibraryShape:
    """One shape from drawclock.xml (style + HTML label + default size)."""

    title: str
    style: str
    label: str
    w: int
    h: int
    object_defaults: dict[str, str]


def library_cache_key(source: LibrarySource | None = None) -> tuple[str, ...]:
    """Expand files/directories into a stable, deduplicated XML path tuple."""
    if source is None:
        raw_paths: tuple[str, ...] = (str(DEFAULT_LIBRARY_PATH),)
    elif isinstance(source, (str, Path)):
        raw_paths = (str(source),)
    else:
        raw_paths = tuple(str(path) for path in source)
    if not raw_paths:
        raise ValueError("至少需要一个器件库文件或目录")
    return _expand_library_paths(raw_paths)


@lru_cache(maxsize=32)
def _expand_library_paths(raw_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Resolve a stable source tuple once for all node and edge lookups."""
    expanded: list[Path] = []
    for raw in raw_paths:
        path = Path(raw).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"器件库路径不存在: {path}")
        if path.is_dir():
            found = sorted(
                (
                    child
                    for child in path.rglob("*")
                    if child.is_file() and child.suffix.lower() == ".xml"
                ),
                key=lambda child: child.as_posix().casefold(),
            )
            if not found:
                raise ValueError(f"器件库目录中没有 XML 文件: {path}")
            expanded.extend(found)
        elif path.suffix.lower() == ".xml":
            expanded.append(path)
        else:
            raise ValueError(f"器件库文件必须是 XML: {path}")

    unique: list[str] = []
    seen: set[str] = set()
    for path in expanded:
        resolved = str(path.resolve())
        identity = os.path.normcase(resolved)
        if identity not in seen:
            seen.add(identity)
            unique.append(resolved)
    return tuple(unique)


def _load_library_file(lib_path: Path) -> list[dict[str, object]]:
    text = lib_path.read_text(encoding="utf-8").strip()
    if text.startswith("<mxlibrary>"):
        text = text[len("<mxlibrary>") : -len("</mxlibrary>")].strip()
    entries = json.loads(text)
    if not isinstance(entries, list):
        raise ValueError(f"器件库不是 mxlibrary 数组: {lib_path}")
    return entries


@lru_cache(maxsize=8)
def _load_library_shapes(library_paths: tuple[str, ...]) -> dict[str, LibraryShape]:
    shapes: dict[str, LibraryShape] = {}
    origins: dict[str, Path] = {}
    for library_path in library_paths:
        lib_path = Path(library_path)
        for entry in _load_library_file(lib_path):
            if not isinstance(entry, dict):
                continue
            title = entry.get("title")
            payload = entry.get("xml")
            w = entry.get("w")
            h = entry.get("h")
            if not title or not payload or w is None or h is None:
                continue
            title = str(title)
            if title in shapes:
                raise ValueError(
                    f"器件库存在重复 title {title}: {origins[title]}，{lib_path}"
                )
            parsed = _parse_library_payload(str(payload))
            if parsed is None:
                continue
            style, label, object_defaults = parsed
            shapes[title] = LibraryShape(
                title=title,
                style=style,
                label=label,
                w=int(w),
                h=int(h),
                object_defaults=object_defaults,
            )
            origins[title] = lib_path
    if not shapes:
        raise ValueError("器件库未解析到任何形状")
    return shapes


def load_library_shapes(source: LibrarySource | None = None) -> dict[str, LibraryShape]:
    """Load and merge draw.io library XML files or directories by title."""
    return _load_library_shapes(library_cache_key(source))


def load_library_cell_styles(source: LibrarySource | None = None) -> dict[str, str]:
    return {title: shape.style for title, shape in load_library_shapes(source).items()}


def _parse_library_payload(payload: str) -> tuple[str, str, dict[str, str]] | None:
    xml_text = payload.strip()
    if not xml_text.startswith("<"):
        xml_text = decompress_diagram_payload(payload)
    root = ET.fromstring(xml_text)
    style: str | None = None
    label = ""
    object_defaults: dict[str, str] = {}
    for obj in root.iter("object"):
        if obj.find("mxCell") is not None:
            label = obj.get("label") or ""
            object_defaults = {
                key: value
                for key, value in obj.attrib.items()
                if key not in ("id", "label") and value is not None
            }
            break
    for mxcell in root.iter("mxCell"):
        if mxcell.get("vertex") == "1":
            style = mxcell.get("style")
            break
    if not style:
        return None
    return style, label, object_defaults


DEFAULT_PLL_KIND = "SC"
DEFAULT_DIV_RATIO = "2"

def _div_r_ratio_font_px(digit_count: int) -> int:
    if digit_count <= 3:
        return 7
    if digit_count <= 4:
        return 7
    return 6


def _patch_div_r_ratio_font(label: str, ratio: str) -> str:
    """Shrink div_r ratio overlay font after bake (library template uses 3-digit default)."""
    marker = ">1</span>"
    if marker not in label or ratio not in label:
        return label
    div_end = label.index(marker) + len(marker)
    match = re.search(r"font-size:\d+px", label[div_end:])
    if match is None:
        return label
    font_px = _div_r_ratio_font_px(len(ratio))
    start = div_end + match.start()
    end = div_end + match.end()
    return label[:start] + f"font-size:{font_px}px" + label[end:]


def bake_label_placeholders(label: str, attrs: dict[str, str]) -> str:
    """Replace editable placeholders with object attribute values for draw.io display."""
    baked = label
    name = attrs.get("name", "")
    if name:
        baked = baked.replace("%name%", name)
    if "%pll_kind%" in baked:
        baked = baked.replace("%pll_kind%", attrs.get("pll_kind", DEFAULT_PLL_KIND))
    if "%ratio%" in baked:
        ratio = attrs.get("ratio", DEFAULT_DIV_RATIO)
        baked = baked.replace("%ratio%", ratio)
        baked = _patch_div_r_ratio_font(baked, ratio)
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
    library_path: LibrarySource | None = None,
) -> dict[str, str]:
    """Ensure object carries baked label HTML (no %placeholders%) for draw.io display."""
    out = dict(stored_attrs)
    shape = _load_library_shapes(library_cache_key(library_path)).get(
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
