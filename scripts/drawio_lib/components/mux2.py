import sys

from drawio_lib.components.mux_component import MuxComponent, bind_module

_COMPONENT = MuxComponent(
    num_inputs=2,
    title="mux2",
    tags="mux2 mux clock drawclock",
)

bind_module(sys.modules[__name__], _COMPONENT)

from drawio_lib.components import mux2_geometry as _geom2

G = _geom2.compute_geometry()
