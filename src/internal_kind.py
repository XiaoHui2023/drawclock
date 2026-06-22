from __future__ import annotations

STYLE_KIND = "drawclockKind"
STYLE_SOURCE_KIND = "drawclockSourceKind"
STYLE_INV_KIND = "drawclockInvKind"

INTERNAL_OBJECT_KEYS = frozenset({"kind", "source_kind", "inv_kind"})

STYLE_KEY_TO_JSON: dict[str, str] = {
    STYLE_KIND: "kind",
    STYLE_SOURCE_KIND: "source_kind",
    STYLE_INV_KIND: "inv_kind",
}
