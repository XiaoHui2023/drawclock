"""Parse portable CSS colors into deterministic SVG sRGB hex values."""

from __future__ import annotations

import colorsys
import math
import re


DEFAULT_DESCRIPTION_COLOR = "#4b5563"

_NAMED_COLOR_TEXT = """
aliceblue=f0f8ff antiquewhite=faebd7 aqua=00ffff aquamarine=7fffd4 azure=f0ffff beige=f5f5dc bisque=ffe4c4 black=000000 blanchedalmond=ffebcd blue=0000ff blueviolet=8a2be2 brown=a52a2a burlywood=deb887 cadetblue=5f9ea0 chartreuse=7fff00 chocolate=d2691e coral=ff7f50 cornflowerblue=6495ed cornsilk=fff8dc crimson=dc143c cyan=00ffff darkblue=00008b darkcyan=008b8b darkgoldenrod=b8860b darkgray=a9a9a9 darkgreen=006400 darkgrey=a9a9a9 darkkhaki=bdb76b darkmagenta=8b008b darkolivegreen=556b2f darkorange=ff8c00 darkorchid=9932cc darkred=8b0000 darksalmon=e9967a darkseagreen=8fbc8f darkslateblue=483d8b darkslategray=2f4f4f darkslategrey=2f4f4f darkturquoise=00ced1 darkviolet=9400d3 deeppink=ff1493 deepskyblue=00bfff dimgray=696969 dimgrey=696969 dodgerblue=1e90ff firebrick=b22222 floralwhite=fffaf0 forestgreen=228b22 fuchsia=ff00ff gainsboro=dcdcdc ghostwhite=f8f8ff gold=ffd700 goldenrod=daa520 gray=808080 green=008000 greenyellow=adff2f grey=808080 honeydew=f0fff0 hotpink=ff69b4 indianred=cd5c5c indigo=4b0082 ivory=fffff0 khaki=f0e68c lavender=e6e6fa lavenderblush=fff0f5 lawngreen=7cfc00 lemonchiffon=fffacd lightblue=add8e6 lightcoral=f08080 lightcyan=e0ffff lightgoldenrodyellow=fafad2 lightgray=d3d3d3 lightgreen=90ee90 lightgrey=d3d3d3 lightpink=ffb6c1 lightsalmon=ffa07a lightseagreen=20b2aa lightskyblue=87cefa lightslategray=778899 lightslategrey=778899 lightsteelblue=b0c4de lightyellow=ffffe0 lime=00ff00 limegreen=32cd32 linen=faf0e6 magenta=ff00ff maroon=800000 mediumaquamarine=66cdaa mediumblue=0000cd mediumorchid=ba55d3 mediumpurple=9370db mediumseagreen=3cb371 mediumslateblue=7b68ee mediumspringgreen=00fa9a mediumturquoise=48d1cc mediumvioletred=c71585 midnightblue=191970 mintcream=f5fffa mistyrose=ffe4e1 moccasin=ffe4b5 navajowhite=ffdead navy=000080 oldlace=fdf5e6 olive=808000 olivedrab=6b8e23 orange=ffa500 orangered=ff4500 orchid=da70d6 palegoldenrod=eee8aa palegreen=98fb98 paleturquoise=afeeee palevioletred=db7093 papayawhip=ffefd5 peachpuff=ffdab9 peru=cd853f pink=ffc0cb plum=dda0dd powderblue=b0e0e6 purple=800080 rebeccapurple=663399 red=ff0000 rosybrown=bc8f8f royalblue=4169e1 saddlebrown=8b4513 salmon=fa8072 sandybrown=f4a460 seagreen=2e8b57 seashell=fff5ee sienna=a0522d silver=c0c0c0 skyblue=87ceeb slateblue=6a5acd slategray=708090 slategrey=708090 snow=fffafa springgreen=00ff7f steelblue=4682b4 tan=d2b48c teal=008080 thistle=d8bfd8 tomato=ff6347 turquoise=40e0d0 violet=ee82ee wheat=f5deb3 white=ffffff whitesmoke=f5f5f5 yellow=ffff00 yellowgreen=9acd32
"""
CSS_NAMED_COLORS = {
    name: "#" + value
    for name, value in (token.split("=", 1) for token in _NAMED_COLOR_TEXT.split())
}

_HEX_RE = re.compile(r"#[0-9a-f]+", re.IGNORECASE)
_FUNCTION_RE = re.compile(r"([a-z]+)\((.*)\)", re.IGNORECASE)
_NUMBER_RE = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?", re.IGNORECASE
)


def _number(text: str) -> float:
    token = text.strip()
    if not _NUMBER_RE.fullmatch(token):
        raise ValueError("数值格式无效")
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("数值必须有限")
    return value


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _byte(value: float) -> int:
    return int(math.floor(_clamp(value, 0.0, 1.0) * 255.0 + 0.5))


def _alpha(text: str) -> float:
    token = text.strip()
    if token.endswith("%"):
        return _clamp(_number(token[:-1]) / 100.0, 0.0, 1.0)
    return _clamp(_number(token), 0.0, 1.0)


def _rgb_channel(text: str) -> float:
    token = text.strip()
    if token.endswith("%"):
        return _clamp(_number(token[:-1]) / 100.0, 0.0, 1.0)
    return _clamp(_number(token) / 255.0, 0.0, 1.0)


def _percentage(text: str) -> float:
    token = text.strip()
    if not token.endswith("%"):
        raise ValueError("饱和度、亮度和白黑比例必须使用百分数")
    return _clamp(_number(token[:-1]) / 100.0, 0.0, 1.0)


def _hue(text: str) -> float:
    token = text.strip().lower()
    factors = (("grad", 0.9), ("turn", 360.0), ("rad", 180.0 / math.pi), ("deg", 1.0))
    for suffix, factor in factors:
        if token.endswith(suffix):
            return (_number(token[:-len(suffix)]) * factor) % 360.0
    return _number(token) % 360.0


def _function_parts(body: str, legacy_name: str) -> tuple[list[str], str | None]:
    if "," in body:
        if legacy_name == "hwb":
            raise ValueError("hwb 只接受空格分隔语法")
        if "/" in body:
            raise ValueError("逗号语法不能与斜杠透明度混用")
        parts = [part.strip() for part in body.split(",")]
        expected = 4 if legacy_name in {"rgba", "hsla"} else 3
        if len(parts) != expected or any(not part for part in parts):
            raise ValueError("颜色函数参数数量无效")
        return parts[:3], parts[3] if len(parts) == 4 else None
    if body.count("/") > 1:
        raise ValueError("颜色函数透明度分隔符无效")
    main, separator, alpha = body.partition("/")
    parts = main.split()
    if len(parts) != 3 or (separator and not alpha.strip()):
        raise ValueError("颜色函数参数数量无效")
    return parts, alpha.strip() if separator else None


def _format_color(red: float, green: float, blue: float, alpha: float = 1.0) -> str:
    channels = [_byte(red), _byte(green), _byte(blue)]
    result = "#" + "".join(f"{channel:02x}" for channel in channels)
    alpha_byte = _byte(alpha)
    return result if alpha_byte == 255 else result + f"{alpha_byte:02x}"


def _parse_hex(value: str) -> str:
    digits = value[1:].lower()
    if len(digits) in {3, 4}:
        digits = "".join(char * 2 for char in digits)
    if len(digits) not in {6, 8}:
        raise ValueError("十六进制颜色必须使用 3、4、6 或 8 位")
    return "#" + digits


def parse_css_color(value: str) -> str:
    """Return a portable lowercase #rrggbb[aa] color or raise ValueError."""
    if not isinstance(value, str):
        raise ValueError("颜色必须是字符串")
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("颜色不能为空")
    if normalized == "transparent":
        return "#00000000"
    if normalized in CSS_NAMED_COLORS:
        return CSS_NAMED_COLORS[normalized]
    if _HEX_RE.fullmatch(normalized):
        return _parse_hex(normalized)
    match = _FUNCTION_RE.fullmatch(normalized)
    if not match:
        raise ValueError("不支持的颜色格式")
    name, body = match.groups()
    if name in {"rgb", "rgba"}:
        channels, alpha = _function_parts(body, name)
        return _format_color(
            *(_rgb_channel(channel) for channel in channels),
            1.0 if alpha is None else _alpha(alpha),
        )
    if name in {"hsl", "hsla"}:
        channels, alpha = _function_parts(body, name)
        hue = _hue(channels[0]) / 360.0
        saturation = _percentage(channels[1])
        lightness = _percentage(channels[2])
        red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
        return _format_color(red, green, blue, 1.0 if alpha is None else _alpha(alpha))
    if name == "hwb":
        channels, alpha = _function_parts(body, name)
        whiteness = _percentage(channels[1])
        blackness = _percentage(channels[2])
        if whiteness + blackness >= 1.0:
            gray = whiteness / (whiteness + blackness)
            red = green = blue = gray
        else:
            red, green, blue = colorsys.hsv_to_rgb(_hue(channels[0]) / 360.0, 1.0, 1.0)
            scale = 1.0 - whiteness - blackness
            red, green, blue = (
                red * scale + whiteness,
                green * scale + whiteness,
                blue * scale + whiteness,
            )
        return _format_color(red, green, blue, 1.0 if alpha is None else _alpha(alpha))
    raise ValueError("仅支持命名色、十六进制、rgb、hsl 和 hwb")
