from __future__ import annotations

from device_attrs_convert import convert_config
from device_attrs_validate import validate_device_attrs


def test_validate_device_attrs_accepts_clock_without_freq() -> None:
    config = {"clk": {"kind": "clock", "source": "pll0"}}
    validate_device_attrs(config)


def test_convert_config_is_identity() -> None:
    raw = {"clk": {"kind": "clock", "source": "x"}}
    assert convert_config(raw) == raw
