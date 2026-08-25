from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_TOPOLOGY_SUFFIXES = (".json",)


def _read_utf8(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def load_config(path: str | Path) -> dict[str, Any]:
    input_path = Path(path)
    if input_path.suffix.lower() != ".json":
        raise ValueError(
            f"不支持输入格式 {input_path.suffix or '<无后缀>'}；只支持：.json"
        )
    data = json.loads(_read_utf8(input_path))
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象")
    return data
