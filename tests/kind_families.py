"""Families with major/minor kind in JSON export."""

from __future__ import annotations

VARIANT_FAMILIES: dict[str, tuple[str, ...]] = {
    "source": ("source", "pad"),
    "inv": ("inv", "inv_cell", "inv_mux"),
    "cell": ("cell", "occ_clk_cell", "gen_cell", "bist_clk_cell", "occ_bist_clk_cell"),
}

STYLE_VARIANT_KEYS: dict[str, str] = {
    "source": "drawclockSourceKind",
    "inv": "drawclockInvKind",
    "cell": "drawclockCellKind",
}

JSON_VARIANT_KEYS: dict[str, str] = {
    "source": "source_kind",
    "inv": "inv_kind",
    "cell": "cell_kind",
}

ALL_VARIANT_TYPES: frozenset[str] = frozenset(
    variant for variants in VARIANT_FAMILIES.values() for variant in variants
)

# JSON kind is unified; drawclockType stays muxN (port count). No {kind}_kind field.
MAJOR_KIND_ONLY: dict[str, tuple[str, ...]] = {
    "mux": ("mux2", "mux3", "mux4", "mux5", "mux6"),
    "pll": ("pll", "pll2"),
}

ALL_MAJOR_KIND_ONLY_TYPES: frozenset[str] = frozenset(
    title for titles in MAJOR_KIND_ONLY.values() for title in titles
)
