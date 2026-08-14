from __future__ import annotations

import re


_SOURCE_REF_RE = re.compile(r"^(?P<name>.+?)(?:\[(?P<output>[^\[\]]+)\])?$")


def parse_source_ref(value: str) -> tuple[str, str | None]:
    if not isinstance(value, str) or not value:
        raise ValueError("source 必须是非空字符串")
    match = _SOURCE_REF_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"source 引用格式错误：{value}")
    return match.group("name"), match.group("output")
