from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import escape


SVG_NS = "http://www.w3.org/2000/svg"
HTML_NS = "http://www.w3.org/1999/xhtml"
_FORBIDDEN_STATIC_TAGS = {"foreignObject", "script", "iframe", "audio", "video", "canvas"}
_NATIVE_TAGS = {
    "a", "circle", "clipPath", "defs", "desc", "ellipse", "g", "image",
    "line", "linearGradient", "marker", "mask", "metadata", "path", "pattern",
    "polygon", "polyline", "radialGradient", "rect", "stop", "style", "svg",
    "symbol", "text", "title", "tspan", "use",
}
_TEXT_TAGS = {"div", "span"}
_HTML_STYLE_PROPERTIES = {
    "box-sizing", "color", "display", "font-family", "font-size", "font-style",
    "font-weight", "height", "left", "line-height", "margin", "overflow", "padding",
    "padding-top", "position", "text-align", "top", "transform", "white-space", "width",
}


class NativeSvgLabelError(ValueError):
    """A component label cannot be represented as self-contained static SVG."""


@dataclass(frozen=True)
class _Box:
    x: float
    y: float
    width: float
    height: float


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _style_map(raw: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for declaration in (raw or "").split(";"):
        if ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        result[key.strip().lower()] = value.strip()
    return result


def _length(raw: str | None, reference: float, default: float = 0.0) -> float:
    if raw is None or not raw.strip():
        return default
    value = raw.strip()
    if value.endswith("%"):
        return reference * float(value[:-1]) / 100.0
    if value.endswith("px"):
        value = value[:-2]
    return float(value)


def _box_for(element: ET.Element, parent: _Box) -> _Box:
    style = _style_map(element.get("style"))
    unsupported = sorted(set(style) - _HTML_STYLE_PROPERTIES)
    if unsupported:
        raise NativeSvgLabelError(
            "器件标签包含不兼容的 HTML 样式: " + ", ".join(unsupported)
        )
    width = _length(style.get("width"), parent.width, parent.width)
    height = _length(style.get("height"), parent.height, parent.height)
    x = parent.x + _length(style.get("left"), parent.width)
    y = parent.y + _length(style.get("top"), parent.height)
    return _Box(x=x, y=y, width=width, height=height)


def _safe_native_element(element: ET.Element) -> ET.Element:
    tag = _local_name(element.tag)
    if tag not in _NATIVE_TAGS or tag in _FORBIDDEN_STATIC_TAGS:
        raise NativeSvgLabelError(f"器件标签包含不兼容的 SVG 元素: {tag}")
    attrs: dict[str, str] = {}
    for raw_key, value in element.attrib.items():
        key = _local_name(raw_key)
        if key.lower().startswith("on"):
            raise NativeSvgLabelError(f"器件标签包含脚本事件属性: {key}")
        if "url(" in value.lower() or "@import" in value.lower():
            raise NativeSvgLabelError("器件标签包含外部 CSS 资源")
        if key in {"href", "xlink:href"} and not (
            value.startswith("#") or value.startswith("data:")
        ):
            raise NativeSvgLabelError("器件标签包含外部资源引用")
        if key != "xmlns":
            attrs[key] = value
    result = ET.Element(tag, attrs)
    result.text = element.text
    for child in element:
        result.append(_safe_native_element(child))
    return result


def _native_svg_fragment(element: ET.Element, box: _Box) -> str:
    native = _safe_native_element(element)
    attrs = {
        "class": "component-graphic",
        "x": _number(box.x),
        "y": _number(box.y),
        **native.attrib,
        "overflow": "visible",
    }
    attrs.setdefault("width", _number(box.width))
    attrs.setdefault("height", _number(box.height))
    positioned = ET.Element("svg", attrs)
    positioned.text = native.text
    positioned.extend(list(native))
    return ET.tostring(positioned, encoding="unicode", short_empty_elements=True)


def _text_fragment(element: ET.Element, box: _Box) -> str:
    text = "".join(element.itertext()).strip()
    if not text:
        return ""
    style = _style_map(element.get("style"))
    font_size = _length(style.get("font-size"), 1.0, 11.0)
    padding_top = _length(style.get("padding-top"), box.height)
    transform = style.get("transform", "").replace(" ", "")
    centered_x = "translateX(-50%)" in transform or transform.startswith("translate(-50%")
    centered_y = transform.endswith(",-50%)")
    x = box.x
    y = box.y + padding_top + font_size * (0.32 if centered_y else 0.82)
    family = style.get("font-family", "Helvetica,Arial,sans-serif")
    color = style.get("color", "#000000")
    attrs = [
        f'x="{_number(x)}"', f'y="{_number(y)}"',
        f'font-size="{_number(font_size)}"',
        f'font-family="{escape(family, quote=True)}"',
        f'fill="{escape(color, quote=True)}"',
    ]
    if "font-weight" in style:
        attrs.append(f'font-weight="{escape(style["font-weight"], quote=True)}"')
    if "font-style" in style:
        attrs.append(f'font-style="{escape(style["font-style"], quote=True)}"')
    if centered_x:
        attrs.append('text-anchor="middle"')
    return f"<text {' '.join(attrs)}>{escape(text)}</text>"


def _render_html_element(element: ET.Element, parent: _Box) -> list[str]:
    tag = _local_name(element.tag)
    box = _box_for(element, parent)
    if tag == "svg":
        return [_native_svg_fragment(element, box)]
    if tag not in _TEXT_TAGS:
        raise NativeSvgLabelError(f"器件标签包含不兼容的 HTML 元素: {tag}")
    children = list(element)
    if not children:
        fragment = _text_fragment(element, box)
        return [fragment] if fragment else []
    transform = _style_map(element.get("style")).get("transform")
    if transform:
        raise NativeSvgLabelError("器件标签的容器 transform 无法转换为静态 SVG")
    fragments: list[str] = []
    if (element.text or "").strip():
        fragments.append(_text_fragment(element, box))
    for child in children:
        fragments.extend(_render_html_element(child, box))
    return fragments


def render_native_label(
    label: str,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    content_offset_x: float,
    content_offset_y: float,
) -> str:
    """Convert the library's deterministic HTML label subset to native SVG."""
    try:
        root = ET.fromstring(f"<root>{label}</root>")
    except ET.ParseError as error:
        raise NativeSvgLabelError(f"器件标签不是可解析的 XML/HTML: {error}") from error
    parent = _Box(
        x=x + content_offset_x,
        y=y + content_offset_y,
        width=width,
        height=height,
    )
    fragments: list[str] = []
    for child in root:
        fragments.extend(_render_html_element(child, parent))
    if not any('class="component-graphic"' in fragment for fragment in fragments):
        raise NativeSvgLabelError("器件标签没有可渲染的原生 SVG 图形")
    return "<g class=\"component\">" + "".join(fragments) + "</g>"


def validate_static_svg(svg_text: str) -> None:
    """Reject browser-only, active, or externally referenced final SVG content."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as error:
        raise ValueError(f"输出不是有效 SVG XML: {error}") from error
    if _local_name(root.tag) != "svg" or not root.tag.startswith(f"{{{SVG_NS}}}"):
        raise ValueError("输出根元素必须位于 SVG 命名空间")
    for element in root.iter():
        tag = _local_name(element.tag)
        if tag in _FORBIDDEN_STATIC_TAGS or element.tag.startswith(f"{{{HTML_NS}}}"):
            raise ValueError(f"输出包含非静态通用 SVG 元素: {tag}")
        for raw_key, value in element.attrib.items():
            key = _local_name(raw_key)
            if key.lower().startswith("on"):
                raise ValueError(f"输出包含脚本事件属性: {key}")
            if "url(" in value.lower() or "@import" in value.lower():
                raise ValueError("输出包含外部 CSS 资源")
            if key in {"href", "xlink:href"} and not (
                value.startswith("#") or value.startswith("data:")
            ):
                raise ValueError("输出包含外部资源引用")
        if _local_name(element.tag) == "style" and (
            "url(" in (element.text or "").lower()
            or "@import" in (element.text or "").lower()
        ):
            raise ValueError("输出包含外部 CSS 资源")


def _number(value: float) -> str:
    return f"{float(value):.4f}".rstrip("0").rstrip(".") or "0"
