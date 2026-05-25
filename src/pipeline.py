from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_export import devices_to_config
from drawio_decode import extract_mxfile_xml, iter_diagram_models
from drawio_graph import ParsedDiagram, merge_diagrams, parse_models, validate_diagram_library
from drawio_library import DEFAULT_LIBRARY_PATH
from topology import build_device_states
from validate_config import validate_config


def drawio_to_clock_tree(
    paths: list[str | Path],
    *,
    library_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Parse draw.io diagram(s) into clock-tree JSON (library shapes only)."""
    lib = Path(library_path or DEFAULT_LIBRARY_PATH)
    parts = []
    for index, raw in enumerate(paths):
        path = Path(raw)
        mxfile = extract_mxfile_xml(str(path))
        models = iter_diagram_models(mxfile)
        prefix = f"f{index}_" if len(paths) > 1 else ""
        parts.append(parse_models(models, id_prefix=prefix))
    diagram = merge_diagrams(parts)
    validate_diagram_library(diagram, lib)
    devices, wire_by_name = build_device_states(diagram)
    config = devices_to_config(devices, wire_by_name)
    validate_config(config)
    return config


def parse_drawio_paths(
    paths: list[str | Path],
    *,
    library_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible alias for tests."""
    return drawio_to_clock_tree(paths, library_path=library_path)


def write_clock_tree_json(
    config: list[dict[str, Any]],
    output_path: Path | None,
) -> Path | None:
    text = json.dumps(config, ensure_ascii=False, indent=2)
    if output_path is None:
        return None
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")
    return output_path
