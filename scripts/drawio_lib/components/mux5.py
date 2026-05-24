import sys

from drawio_lib.components.mux_component import MuxComponent, bind_module

_COMPONENT = MuxComponent(
    num_inputs=5,
    title="mux5",
    tags="mux5 mux clock drawclock",
)

bind_module(sys.modules[__name__], _COMPONENT)
