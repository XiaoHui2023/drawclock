from __future__ import annotations

from dataclasses import dataclass

from drawio_lib.components.label_attrs import ATTR_NAME
from drawio_lib.components.simple_component import SimpleComponent, xml_attr

ATTR_KIND = "kind"
ATTR_SOURCE_KIND = "source_kind"
SOURCE_MAJOR_KIND = "source"


@dataclass
class ClockSourceComponent(SimpleComponent):
    """Clock-source family; kind / source_kind are internal object attrs for JSON export."""

    @property
    def required_object_attrs(self) -> tuple[str, ...]:
        return (ATTR_NAME, ATTR_KIND, ATTR_SOURCE_KIND)

    def cell_fragment(
        self,
        cell_id: str,
        instance_name: str | None = None,
        *,
        x: int | None = None,
        y: int | None = None,
    ) -> str:
        style = self.cell_style()
        name = xml_attr(self._resolve_instance_name(instance_name))
        label = xml_attr(self.label_html())
        attrs = [
            f'{ATTR_NAME}="{name}"',
            f'label="{label}"',
            'placeholders="1"',
            f'id="{cell_id}"',
            f'{ATTR_KIND}="{SOURCE_MAJOR_KIND}"',
            f'{ATTR_SOURCE_KIND}="{xml_attr(self.drawclock_type)}"',
        ]
        if x is None and y is None:
            geom_xml = f'<mxGeometry width="{self.w}" height="{self.h}" as="geometry"/>'
        else:
            geom_xml = (
                f'<mxGeometry x="{x or 0}" y="{y or 0}" width="{self.w}" '
                f'height="{self.h}" as="geometry"/>'
            )
        return (
            f"<object {' '.join(attrs)}>"
            f'<mxCell style="{style}" vertex="1" parent="1">'
            f"{geom_xml}"
            "</mxCell>"
            "</object>"
        )
