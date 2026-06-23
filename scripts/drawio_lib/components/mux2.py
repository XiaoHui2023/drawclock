import sys

from drawio_lib.components.mux_component import MuxComponent, bind_module

_COMPONENT = MuxComponent(
    num_inputs=2,
    title="mux2",
    tags="mux2 mux clock drawclock",
)

bind_module(sys.modules[__name__], _COMPONENT)

from drawio_lib.components import mux2_geometry as _geom2


def _live_geometry() -> _geom2.Mux2Geometry:
    g = _COMPONENT.g
    return _geom2.Mux2Geometry(
        trap=g.trap,
        in0=g.inputs[0],
        in1=g.inputs[1],
        out=g.out,
        mux_h=g.mux_h,
        cell_h=g.cell_h,
    )


G = _live_geometry()
