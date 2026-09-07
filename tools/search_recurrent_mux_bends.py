#!/usr/bin/env python3
"""Deterministically search complex public-CLI mux layouts for bend recurrence."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

from feedback_layout_reproduction_oracle import analyze


ROOT = Path(__file__).resolve().parents[1]


def build_case(seed: int) -> dict[str, dict[str, object]]:
    rng = random.Random(seed)
    items: list[tuple[str, dict[str, object]]] = []
    roots = [f"source_{index}" for index in range(4)]
    for index, root in enumerate(roots):
        item: dict[str, object] = {"kind": "source"}
        column_patterns = (None, (0, 1, 2, 1), (0, 2, 1, 3), (2, 0, 3, 1))
        column = column_patterns[seed % len(column_patterns)][index] if column_patterns[seed % len(column_patterns)] else None
        if column is not None:
            item["layout_column"] = column
        items.append((root, item))

        parent = root
        depth = 1 + ((seed * 3 + index * 5) % 5)
        kinds = ("gate", "div", "cell")
        for level in range(depth):
            node = f"aux_{index}_{level}"
            items.append((node, {"kind": kinds[(seed + index + level) % len(kinds)], "source": parent}))
            parent = node
        items.append((f"aux_clock_{index}", {"kind": "clock", "source": parent}))

    ports = roots[:]
    rng.shuffle(ports)
    items.append(("main_mux", {"kind": "mux4", "source": {str(i): root for i, root in enumerate(ports)}}))
    downstream = "main_mux"
    for level in range(seed % 4):
        node = f"post_{level}"
        items.append((node, {"kind": ("gate", "div", "cell")[level % 3], "source": downstream}))
        downstream = node
    items.append(("main_clock", {"kind": "clock", "source": downstream}))

    if seed % 3 == 0:
        items.append(("side_mux", {"kind": "mux2", "source": {"0": roots[(seed + 1) % 4], "1": roots[(seed + 3) % 4]}}))
        items.append(("side_clock", {"kind": "clock", "source": "side_mux"}))
    rng.shuffle(items)
    return dict(items)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=96)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = []
    for seed in range(args.rounds):
        config = build_case(seed)
        input_path = args.output / f"seed-{seed:03d}.json"
        svg_path = args.output / f"seed-{seed:03d}.svg"
        input_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "src"), "-i", str(input_path),
             "-l", str(ROOT / "drawio-lib"), "-o", str(svg_path),
             "--crossing-style", "none"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if completed.returncode:
            raise SystemExit(completed.stdout + completed.stderr)
        report = analyze(input_path, svg_path)
        direct = [edge for edge in report["edges"] if edge["target"] == "main_mux"]
        row = {
            "seed": seed,
            "direct_bends": sum(edge["bends"] for edge in direct),
            "direct_bent_edges": [edge["edge_id"] for edge in direct if edge["bends"]],
            "detected_issues": report["detected_issues"],
            "axis_witnesses": report["witnesses"]["root_fanout_axis_dominance_witnesses"],
            "avoidable_edges": report["witnesses"]["avoidable_bend_edges"],
        }
        summary.append(row)
        if "FB-BEND-017" in report["detected_issues"]:
            (args.output / "first-reproduction.json").write_text(
                json.dumps(row, indent=2) + "\n", encoding="utf-8",
            )
            print(json.dumps(row, indent=2))
            return 0
    (args.output / "search-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8",
    )
    print(f"FB-BEND-017 not reproduced in {args.rounds} deterministic cases", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
