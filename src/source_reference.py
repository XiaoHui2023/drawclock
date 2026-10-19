from __future__ import annotations

import re
from collections.abc import Iterable, Mapping


_SOURCE_REF_RE = re.compile(r"^(?P<name>.+?)(?:\[(?P<output>[^\[\]]+)\])?$", re.DOTALL)


def parse_source_ref(value: str) -> tuple[str, str | None]:
    if not isinstance(value, str) or not value:
        raise ValueError("source 必须是非空字符串")
    match = _SOURCE_REF_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"source 引用格式错误：{value}")
    return match.group("name"), match.group("output")


def reference_name(value: str) -> str:
    """Return connection identity while retaining whitespace used for display."""
    return value.replace("\r", "").replace("\n", "")


def build_reference_name_index(names: Iterable[str]) -> dict[str, str]:
    """Index display names by newline-insensitive connection identity."""
    index: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    for name in names:
        key = reference_name(name)
        previous = index.get(key)
        if previous is not None and previous != name:
            collisions.setdefault(key, [previous]).append(name)
        else:
            index[key] = name
    if collisions:
        details = "; ".join(
            ", ".join(repr(name) for name in values)
            for _, values in sorted(collisions.items())
        )
        raise ValueError(f"节点名忽略换行后不能唯一匹配：{details}")
    return index


def resolve_source_ref(
    value: str, name_index: Mapping[str, str]
) -> tuple[str, str | None]:
    """Resolve a source reference to its original display name."""
    name, output = parse_source_ref(value)
    resolved = name_index.get(reference_name(name))
    if resolved is None:
        raise KeyError(name)
    return resolved, output
