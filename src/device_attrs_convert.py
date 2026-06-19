from __future__ import annotations

from typing import Any


def convert_device_entry(item: dict[str, Any]) -> dict[str, Any]:
    """单条记录：按 kind 转换属性。"""
    return dict(item)


def convert_config(config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """转换整份 clock-tree 配置（各器件属性规范化）。"""
    return {name: convert_device_entry(item) for name, item in config.items()}
