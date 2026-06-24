from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config_export import devices_to_config, entries_to_clock_tree
from drawio_decode import extract_mxfile_xml, iter_diagram_models
from drawio_graph import ParsedDiagram, merge_diagrams, parse_models, validate_diagram_library
from drawio_library import DEFAULT_LIBRARY_PATH
from topology import build_device_states
from validate_config import validate_config

_DEVICE_NAME_RE = re.compile(r"^(?:器件|from)\s+(\S+)")
_DUPLICATE_NAME_RE = re.compile(r"^器件名\s+(\S+)\s+重复")
_UPSTREAM_PEER_RE = re.compile(r"^上游器件\s+(\S+)\s+的输出")


def _wrap_input_error(path: Path, exc: BaseException) -> None:
    raise ValueError(f"图片 {path}: {exc}") from exc


def _name_to_source_map(diagram: ParsedDiagram) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for cell_id, cell in diagram.cells.items():
        if cell.is_edge or not cell.drawclock_type:
            continue
        source = diagram.cell_sources.get(cell_id)
        if source is None or not cell.name:
            continue
        mapping.setdefault(cell.name, source)
    return mapping


def _source_for_error_line(line: str, name_to_source: dict[str, Path]) -> Path | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("·"):
        return None
    for pattern in (_DEVICE_NAME_RE, _DUPLICATE_NAME_RE, _UPSTREAM_PEER_RE):
        match = pattern.match(stripped)
        if match:
            return name_to_source.get(match.group(1))
    if stripped.startswith("from "):
        parts = stripped.split()
        if len(parts) >= 2:
            return name_to_source.get(parts[1])
    return None


def _annotate_multi_input_error(message: str, name_to_source: dict[str, Path]) -> str:
    lines: list[str] = []
    for line in message.split("\n"):
        source = _source_for_error_line(line, name_to_source)
        if source is not None:
            lines.append(f"图片 {source}: {line}")
        else:
            lines.append(line)
    return "\n".join(lines)


def drawio_to_clock_tree(
    paths: list[str | Path],
    *,
    library_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Parse draw.io diagram(s) into clock-tree JSON (library shapes only)."""
    lib = Path(library_path or DEFAULT_LIBRARY_PATH)
    paths_list = [Path(raw) for raw in paths]
    multi = len(paths_list) > 1
    parts: list[ParsedDiagram] = []
    for index, path in enumerate(paths_list):
        try:
            mxfile = extract_mxfile_xml(str(path))
            models = iter_diagram_models(mxfile)
            prefix = f"f{index}_" if multi else ""
            part = parse_models(models, id_prefix=prefix)
            if multi:
                part = ParsedDiagram(
                    cells=part.cells,
                    cell_sources={cell_id: path for cell_id in part.cells},
                )
                validate_diagram_library(part, lib)
            parts.append(part)
        except (ValueError, OSError) as exc:
            if multi:
                _wrap_input_error(path, exc)
            raise
    diagram = merge_diagrams(parts)
    if not multi:
        validate_diagram_library(diagram, lib)
    lib_str = str(lib)
    name_to_source = _name_to_source_map(diagram) if multi else {}
    try:
        devices, from_by_name = build_device_states(diagram, library_path=lib_str)
        entries = devices_to_config(devices, from_by_name, library_path=lib_str)
        config = entries_to_clock_tree(entries)
        validate_config(config, library_path=lib_str)
    except ValueError as exc:
        if multi:
            raise ValueError(
                _annotate_multi_input_error(str(exc), name_to_source)
            ) from exc
        raise
    return config


def parse_drawio_paths(
    paths: list[str | Path],
    *,
    library_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Backward-compatible alias for tests."""
    return drawio_to_clock_tree(paths, library_path=library_path)


def write_clock_tree_json(
    config: dict[str, dict[str, Any]],
    output_path: Path | None,
) -> Path | None:
    text = json.dumps(config, ensure_ascii=False, indent=2)
    if output_path is None:
        return None
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")
    return output_path
