from __future__ import annotations

from typing import Any

from device_attrs_validate import CLOCK_FREQ_RE

_FREQ_MULTIPLIER: dict[str, float] = {
    "k": 1e3,
    "m": 1e6,
    "g": 1e9,
}


def clock_freq_to_number(freq: str) -> int | float:
    """将 clock 的 freq 字符串转为赫兹数值（k→10³，m→10⁶，g→10⁹）。"""
    text = freq.strip()
    match = CLOCK_FREQ_RE.fullmatch(text)
    if not match:
        raise ValueError(f"freq 格式无效: {freq!r}")
    base = float(match.group(1))
    suffix = match.group(2)
    if suffix:
        base *= _FREQ_MULTIPLIER[suffix.lower()]
    if base == int(base):
        return int(base)
    return base


def convert_device_entry(item: dict[str, Any]) -> dict[str, Any]:
    """单条记录：按 kind 转换属性（当前仅 clock.freq → 数字）。"""
    out = dict(item)
    if item.get("kind") == "clock" and "freq" in item:
        raw = item["freq"]
        if isinstance(raw, str) and raw.strip():
            out["freq"] = clock_freq_to_number(raw)
        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
            out["freq"] = int(raw) if raw == int(raw) else raw
    return out


def convert_config(config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """转换整份 clock-tree 配置（各器件属性规范化）。"""
    return {name: convert_device_entry(item) for name, item in config.items()}
