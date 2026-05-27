from __future__ import annotations

import pytest

from device_attrs_convert import clock_freq_to_number, convert_config
from device_attrs_validate import collect_device_attr_errors, validate_device_attrs


def test_clock_freq_valid_formats() -> None:
    config = {
        "a": {"kind": "clock", "freq": "100"},
        "b": {"kind": "clock", "freq": "1.5k"},
        "c": {"kind": "clock", "freq": "2M"},
        "d": {"kind": "clock", "freq": "3G"},
    }
    assert collect_device_attr_errors(config) == []


def test_clock_freq_invalid() -> None:
    config = {"clk": {"kind": "clock", "freq": "100hz"}}
    errors = collect_device_attr_errors(config)
    assert len(errors) == 1
    assert "clk" in errors[0]
    with pytest.raises(ValueError, match="clk"):
        validate_device_attrs(config)


def test_clock_freq_convert() -> None:
    assert clock_freq_to_number("100") == 100
    assert clock_freq_to_number("1.5k") == 1500
    assert clock_freq_to_number("2m") == 2_000_000
    assert clock_freq_to_number("3G") == 3_000_000_000


def test_convert_config_clock_freq() -> None:
    raw = {"clk": {"kind": "clock", "freq": "100k", "source": "x"}}
    out = convert_config(raw)
    assert out["clk"]["freq"] == 100_000
    assert out["clk"]["source"] == "x"
