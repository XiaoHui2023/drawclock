import sys

from drawio_lib.components.colored_cell_shared import register_colored_cell
from drawio_lib.components.simple_shapes import gen_cell_body

register_colored_cell(
    sys.modules[__name__],
    title="gen_cell",
    fill="#ffb3b3",
    tags="gen_cell cell clock drawclock",
    body_svg=gen_cell_body,
)
