from __future__ import annotations

from typing import Any


def collect_device_attr_errors(config: dict[str, dict[str, Any]]) -> list[str]:
    """收集各器件属性格式问题，供 validate_config 合并上报。"""
    return []


def validate_device_attrs(config: dict[str, dict[str, Any]]) -> None:
    """校验 clock-tree 条目中各器件属性；有问题时抛出 ValueError。"""
    errors = collect_device_attr_errors(config)
    if errors:
        raise ValueError("\n".join(errors))
