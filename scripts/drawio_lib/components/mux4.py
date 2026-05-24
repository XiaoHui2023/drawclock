import sys

from drawio_lib.components.mux_component import MuxComponent, bind_module

_COMPONENT = MuxComponent(
    num_inputs=4,
    title="mux4",
    tags="mux4 mux clock drawclock",
)

bind_module(sys.modules[__name__], _COMPONENT)
