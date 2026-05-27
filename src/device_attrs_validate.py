from __future__ import annotations

import re
from typing import Any

# 数字 + 可选后缀 k/m/g（大小写不敏感）
CLOCK_FREQ_RE = re.compile(r"^(\d+(?:\.\d+)?)([kmg])?$", re.IGNORECASE)


def collect_device_attr_errors(config: dict[str, dict[str, Any]]) -> list[str]:
    """收集各器件属性格式问题，供 validate_config 合并上报。"""
    errors: list[str] = []
    for name, item in config.items():
        if item.get("kind") == "clock":
            errors.extend(_clock_freq_errors(name, item.get("freq")))
    return errors


def validate_device_attrs(config: dict[str, dict[str, Any]]) -> None:
    """校验 clock-tree 条目中各器件属性；有问题时抛出 ValueError。"""
    errors = collect_device_attr_errors(config)
    if errors:
        raise ValueError("\n".join(errors))


def _clock_freq_errors(name: str, freq: Any) -> list[str]:
    if freq is None or freq == "":
        return []
    if isinstance(freq, (int, float)) and not isinstance(freq, bool):
        return []
    if not isinstance(freq, str):
        return [f"器件 {name} 的 freq 须为字符串（数字，可选后缀 k/m/g）"]
    text = freq.strip()
    if not text:
        return []
    if not CLOCK_FREQ_RE.fullmatch(text):
        return [
            f"器件 {name} 的 freq 格式无效：须为数字，可选后缀 k、m 或 g（大小写均可）"
        ]
    return []
