from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from drawio_graph import _parse_points
from drawio_library import DEFAULT_LIBRARY_PATH, load_library_shapes

INPUT_X_MAX = 0.5


@dataclass(frozen=True)
class PortTopology:
  """Input/output port keys derived from mxCell style points."""

  inputs: tuple[str, ...]
  outputs: tuple[str, ...]
  index_to_key: tuple[str, ...]

  @property
  def output_count(self) -> int:
    return len(self.outputs)


def port_topology_from_points(points: tuple[tuple[float, float], ...]) -> PortTopology:
  if not points:
    return PortTopology(inputs=(), outputs=(), index_to_key=())

  inputs: list[tuple[float, float, int]] = []
  outputs: list[tuple[float, float, int]] = []
  for index, (x, y) in enumerate(points):
    if x < INPUT_X_MAX:
      inputs.append((y, x, index))
    else:
      outputs.append((y, x, index))

  inputs.sort()
  outputs.sort()

  index_to_key: list[str] = [""] * len(points)
  input_keys: list[str] = []
  for rank, (_, _, index) in enumerate(inputs):
    key = "left" if len(inputs) == 1 else f"in{rank}"
    input_keys.append(key)
    index_to_key[index] = key

  output_keys: list[str] = []
  for rank, (_, _, index) in enumerate(outputs):
    if len(outputs) == 1:
      key = "out" if len(input_keys) > 1 else "right"
    else:
      key = f"out{rank}"
    output_keys.append(key)
    index_to_key[index] = key

  return PortTopology(
    inputs=tuple(input_keys),
    outputs=tuple(output_keys),
    index_to_key=tuple(index_to_key),
  )


def port_topology_from_style(style: str) -> PortTopology:
  return port_topology_from_points(_parse_points(style))


@lru_cache(maxsize=8)
def load_library_port_topologies(library_path: str) -> dict[str, PortTopology]:
  shapes = load_library_shapes(library_path)
  return {
    title: port_topology_from_style(shape.style)
    for title, shape in shapes.items()
  }


def topology_for_type(drawclock_type: str, *, library_path: str | Path | None = None) -> PortTopology:
  lib = str(library_path or DEFAULT_LIBRARY_PATH)
  topologies = load_library_port_topologies(lib)
  if drawclock_type not in topologies:
    raise KeyError(f"器件类型不在器件库中: {drawclock_type}")
  return topologies[drawclock_type]


def port_anchors(style: str) -> dict[str, tuple[float, float]]:
  points = _parse_points(style)
  topology = port_topology_from_points(points)
  anchors: dict[str, tuple[float, float]] = {}
  for index, key in enumerate(topology.index_to_key):
    if index < len(points):
      anchors[key] = points[index]
  return anchors


def port_key_for_index(
  points: tuple[tuple[float, float], ...],
  index: int,
) -> str | None:
  topology = port_topology_from_points(points)
  if index < 0 or index >= len(topology.index_to_key):
    return None
  return topology.index_to_key[index]


def resolve_port(
  points: tuple[tuple[float, float], ...],
  xy: tuple[float, float] | None,
) -> str | None:
  if not points or xy is None:
    return None
  best_idx = 0
  best_dist = float("inf")
  for idx, point in enumerate(points):
    dist = (point[0] - xy[0]) ** 2 + (point[1] - xy[1]) ** 2
    if dist < best_dist:
      best_dist = dist
      best_idx = idx
  if best_dist > 0.04:
    return None
  return port_key_for_index(points, best_idx)


def out_port_index(port: str) -> int | None:
  if port.startswith("out") and port[3:].isdigit():
    return int(port[3:])
  if port in ("right", "out"):
    return 0
  return None


def connection_dict_key(port: str) -> str:
  if port.startswith("in") and port[2:].isdigit():
    return port[2:]
  if port.startswith("out") and port[3:].isdigit():
    return port[3:]
  if port in ("left", "right", "out"):
    return "0"
  return port


def is_input_port(port: str, topology: PortTopology) -> bool:
  return port in topology.inputs


def is_output_port(port: str, topology: PortTopology) -> bool:
  return port in topology.outputs
