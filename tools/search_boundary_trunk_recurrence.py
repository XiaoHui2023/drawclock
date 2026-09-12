#!/usr/bin/env python3
"""Search public-CLI layout mutations for dominated interior bus entry."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import feedback_layout_reproduction_oracle as oracle
from svg_quality_system import evaluate


BASE = ROOT / "tests/reproduction-corpus/premature-interior-trunk-entry.json"
REGISTRY = ROOT / "tests/quality-metrics.json"


def _public_root_and_targets(
    config: dict[str, dict[str, object]],
) -> tuple[str, list[str], list[str]]:
    public_roots = sorted(
        name for name, item in config.items()
        if item.get("kind") == "from" and "source" not in item
    )
    if len(public_roots) != 1:
        raise ValueError("boundary attack requires exactly one public from root")
    public_root = public_roots[0]
    reconvergent = sorted(
        name for name in config if name.startswith("select_reconvergent_")
    )
    public_targets = [
        name for name in reconvergent
        if public_root in config[name].get("source", {}).values()
    ]
    if not public_targets:
        raise ValueError("boundary attack requires a public from mux target")
    return public_root, reconvergent, public_targets


def build_case(seed: int) -> dict[str, dict[str, object]]:
    config = json.loads(BASE.read_text(encoding="utf-8"))
    _public_root, reconvergent, public_targets = _public_root_and_targets(config)
    for name in reconvergent:
        config[name]["layout_column"] = 5
    target = public_targets[-1 - seed % len(public_targets)]
    config[target]["layout_column"] = 8 + seed % 2
    if seed % 2:
        source = config[target].get("source")
        if isinstance(source, dict):
            config[target]["source"] = dict(reversed(list(source.items())))
    items = list(config.items())
    random.Random(seed).shuffle(items)
    return dict(items)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = []
    progress_path = args.output / "search-progress.json"
    for seed in range(args.attempts):
        case_dir = args.output / f"seed-{seed:03d}"
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input.json"
        svg_path = case_dir / "output.svg"
        config = build_case(seed)
        input_path.write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )
        run = subprocess.run(
            [sys.executable, str(ROOT / "src"), "-i", str(input_path),
             "-l", str(ROOT / "drawio-lib"), "-o", str(svg_path),
             "--crossing-style", "arc"],
            cwd=ROOT, capture_output=True, check=False,
        )
        if run.returncode or not svg_path.is_file():
            print(f"operational_error seed={seed}", file=sys.stderr)
            return 2
        report = oracle.analyze(input_path, svg_path)
        quality = evaluate(input_path, svg_path, REGISTRY)
        public_root, reconvergent, _public_targets = _public_root_and_targets(config)
        target = max(
            reconvergent,
            key=lambda name: int(config[name]["layout_column"]),
        )
        boxes, _routes = oracle.parse_svg(svg_path, set(config))
        rendered_x: dict[str, list[float]] = {
            name: [] for name in reconvergent
        }
        for box in boxes:
            if box.node in rendered_x:
                rendered_x[box.node].append(box.x + box.w / 2.0)
        semantic_errors = []
        if public_root not in config[target].get("source", {}).values():
            semantic_errors.append("shifted target does not receive public from")
        if any(len(rendered_x[name]) != 1 for name in reconvergent):
            semantic_errors.append("mux rendering count is not exactly one")
            target_offset = None
        else:
            peer_x = max(rendered_x[name][0] for name in reconvergent if name != target)
            target_offset = rendered_x[target][0] - peer_x
            if target_offset <= oracle.EPS:
                semantic_errors.append("target mux is not right of ordinary muxes")
        row = {
            "seed": seed,
            "public_root": public_root,
            "shifted_target": target,
            "target_offset_px": (
                None if target_offset is None else round(target_offset, 4)
            ),
            "semantic_preconditions_met": not semantic_errors,
            "semantic_errors": semantic_errors,
            "issues": report["detected_issues"],
            "quality_failed": quality["failed_metric_ids"],
            "premature_witnesses": report["witnesses"][
                "premature_interior_trunk_entry_witnesses"
            ],
        }
        summary.append(row)
        (case_dir / "result.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8"
        )
        progress_path.write_text(
            json.dumps({
                "requested_attempts": args.attempts,
                "completed_attempts": len(summary),
                "complete": False,
                "results": summary,
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        if row["quality_failed"]:
            (args.output / "first-failure.json").write_text(
                json.dumps(row, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(row, indent=2))
            return 1
        if semantic_errors:
            (args.output / "first-precondition-failure.json").write_text(
                json.dumps(row, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(row, indent=2))
            return 3
    progress_path.write_text(
        json.dumps({
            "requested_attempts": args.attempts,
            "completed_attempts": len(summary),
            "complete": True,
            "results": summary,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output / "search-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"not_reproduced attempts={args.attempts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
