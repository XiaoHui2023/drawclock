from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config_export import devices_to_config
from drawio_build import build_drawio_xml
from drawio_decode import extract_mxfile_xml, iter_diagram_models
from drawio_graph import merge_diagrams, parse_models
from drawio_layout import (
    LayoutDocument,
    layout_from_diagram,
    layout_from_dict,
    layout_to_dict,
)
from drawio_library import load_library_titles, validate_layout_types
from layout_validate import validate_layout_matches_config
from topology import build_device_states
from validate_config import validate_config


@dataclass
class EncodeResult:
    config: list[dict[str, Any]]
    layout: LayoutDocument | None


def parse_drawio_paths(
    paths: list[str | Path],
    *,
    include_layout: bool = False,
) -> EncodeResult:
    parts = []
    for index, raw in enumerate(paths):
        path = Path(raw)
        mxfile = extract_mxfile_xml(str(path))
        models = iter_diagram_models(mxfile)
        prefix = f"f{index}_" if len(paths) > 1 else ""
        parts.append(parse_models(models, id_prefix=prefix))
    diagram = merge_diagrams(parts)
    devices, wire_by_name = build_device_states(diagram)
    config = devices_to_config(devices, wire_by_name)
    validate_config(config)
    layout = layout_from_diagram(diagram) if include_layout else None
    return EncodeResult(config=config, layout=layout)


def encode_drawio_paths(
    paths: list[str | Path],
    output_dir: Path | None,
    *,
    include_layout: bool,
) -> tuple[Path | None, Path | None]:
    result = parse_drawio_paths(paths, include_layout=include_layout)
    config_path = write_json(result.config, output_dir, filename="clock-tree.json")
    layout_path = None
    if include_layout and result.layout is not None:
        layout_path = write_json(
            layout_to_dict(result.layout),
            output_dir,
            filename="drawio-layout.json",
        )
    return config_path, layout_path


def decode_to_drawio(
    config_path: str | Path,
    layout_path: str | Path,
    library_path: str | Path,
    output_path: str | Path,
) -> Path:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    layout_data = json.loads(Path(layout_path).read_text(encoding="utf-8"))
    layout = layout_from_dict(layout_data)
    validate_config(config)
    validate_layout_matches_config(layout, config)
    library_titles = load_library_titles(library_path)
    layout_types = {vertex.drawclock_type for vertex in layout.vertices}
    validate_layout_types(layout_types, library_titles)
    xml_text = build_drawio_xml(layout)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml_text, encoding="utf-8")
    return out


def write_json(
    payload: list[dict[str, Any]] | dict[str, Any],
    output_dir: Path | None,
    *,
    filename: str,
) -> Path | None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_dir is None:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    out_path.write_text(text + "\n", encoding="utf-8")
    return out_path
