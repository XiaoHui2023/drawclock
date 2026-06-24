from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components.internal_kind import STYLE_CELL_KIND, variant_style_suffix
from drawio_lib.components.simple_component import SimpleComponent

CELL_MAJOR_KIND = "cell"


@dataclass
class CellComponent(SimpleComponent):
    """Cell family; kind metadata lives in mxCell style for JSON export."""

    @property
    def json_kind(self) -> str:
        return CELL_MAJOR_KIND

    def cell_style(self) -> str:
        return (
            f"{super().cell_style()}"
            f"{variant_style_suffix(STYLE_CELL_KIND, self.drawclock_type)}"
        )
