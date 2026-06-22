from __future__ import annotations

from drawio_lib.xml_io import xml_attr

STYLE_KIND = "drawclockKind"
STYLE_SOURCE_KIND = "drawclockSourceKind"
STYLE_INV_KIND = "drawclockInvKind"

INTERNAL_OBJECT_KEYS = frozenset({"kind", "source_kind", "inv_kind"})


def kind_style_suffix(json_kind: str) -> str:
    return f"{STYLE_KIND}={xml_attr(json_kind)};"


def variant_style_suffix(style_key: str, value: str) -> str:
    return f"{style_key}={xml_attr(value)};"
