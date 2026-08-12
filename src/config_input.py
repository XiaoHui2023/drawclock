from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any

import configlib
import json5
import yaml
from configlib.loading import register_loader

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import toml as tomllib


SUPPORTED_TOPOLOGY_SUFFIXES = (
    ".json",
    ".jsonc",
    ".json5",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".conf",
    ".config",
)


def _read_utf8(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


@register_loader("json", nowarn=True)
def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(_read_utf8(path))


@register_loader("jsonc", "json5", nowarn=True)
def _load_json5(path: str | Path) -> dict[str, Any]:
    return json5.loads(_read_utf8(path))


@register_loader("toml", nowarn=True)
def _load_toml(path: str | Path) -> dict[str, Any]:
    return tomllib.loads(_read_utf8(path))


@register_loader("yaml", "yml", nowarn=True)
def _load_yaml(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(_read_utf8(path))


@register_loader("ini", "conf", "config", nowarn=True)
def _load_ini(path: str | Path) -> dict[str, dict[str, str]]:
    parser = configparser.ConfigParser(
        allow_no_value=False,
        strict=True,
        empty_lines_in_values=False,
        interpolation=configparser.ExtendedInterpolation(),
    )
    parser.optionxform = lambda option: option.lower().replace("-", "_")
    parser.read_string(_read_utf8(path))
    return {
        section: {option: parser.get(section, option) for option in parser.options(section)}
        for section in parser.sections()
    }


def load_config(path: str | Path) -> dict[str, Any]:
    input_path = Path(path)
    if input_path.suffix.lower() not in SUPPORTED_TOPOLOGY_SUFFIXES:
        supported = ", ".join(SUPPORTED_TOPOLOGY_SUFFIXES)
        raise ValueError(
            f"不支持输入格式 {input_path.suffix or '<无后缀>'}；支持：{supported}"
        )
    return configlib.load(input_path).get()
