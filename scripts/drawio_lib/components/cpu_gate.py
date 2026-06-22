import sys

from drawio_lib.components.module_component import ModuleComponent, bind_module

_CPU_GATE_OUTPUTS = ("hclk_en", "hclk", "clk_arm_core")

_COMPONENT = ModuleComponent(
    title="cpu_gate",
    tags="cpu_gate divider clock drawclock",
    output_labels=_CPU_GATE_OUTPUTS,
)

bind_module(sys.modules[__name__], _COMPONENT)
