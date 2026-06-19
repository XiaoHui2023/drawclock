import sys

from drawio_lib.components.colored_cell_shared import register_colored_cell
from drawio_lib.components.simple_shapes import cell_body

register_colored_cell(
    sys.modules[__name__],
    title="cell",
    fill="none",
    tags="cell clock drawclock",
    body_svg=cell_body,
)
