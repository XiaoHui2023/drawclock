from __future__ import annotations

from pathlib import Path
from typing import Any

from device_attrs_validate import collect_device_attr_errors
from from_resolve import parse_source_ref
from library_ports import topology_for_type


def validate_config(
  config: dict[str, dict[str, Any]],
  *,
  library_path: str | Path,
) -> None:
  errors: list[str] = []
  errors.extend(collect_device_attr_errors(config))
  device_names = set(config.keys())

  for name, item in config.items():
    kind = item.get("kind")
    if kind == "from":
      errors.append("clock-tree.json 不应包含 kind 为 from 的记录")
      continue

    refs = _referenced_peers(item)
    for peer in refs:
      base, index = parse_source_ref(peer)
      if base not in device_names:
        errors.append(f"器件 {name} 连接到未知器件 {peer}")
        continue
      if index is not None:
        upstream_kind = config[base].get("kind", "")
        try:
          output_count = topology_for_type(
            str(upstream_kind), library_path=library_path
          ).output_count
        except KeyError:
          output_count = 1
        if output_count <= 1:
          errors.append(
            f"器件 {name} 的 source {peer} 指向无多路输出的器件 {base}"
          )
          continue
        if index >= output_count:
          errors.append(
            f"器件 {name} 的 source {peer} 超出 {base} 的输出路数 {output_count}"
          )

    if isinstance(item.get("source"), dict) and not item.get("source"):
      errors.append(f"器件 {name} 的输入未全部连接")

  if errors:
    raise ValueError("\n".join(errors))


def _referenced_peers(item: dict[str, Any]) -> list[str]:
  peers: list[str] = []
  source = item.get("source")
  if isinstance(source, dict):
    peers.extend(v for v in source.values() if isinstance(v, str))
  elif isinstance(source, str):
    peers.append(source)
  target = item.get("target")
  if isinstance(target, dict):
    peers.extend(v for v in target.values() if isinstance(v, str))
  elif isinstance(target, str):
    peers.append(target)
  return peers
