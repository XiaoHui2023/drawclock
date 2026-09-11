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

from feedback_layout_reproduction_oracle import analyze
from svg_quality_system import evaluate


BASE = ROOT / "tests/reproduction-corpus/premature-interior-trunk-entry.json"
REGISTRY = ROOT / "tests/quality-metrics.json"


def build_case(seed: int) -> dict[str, dict[str, object]]:
    config = json.loads(BASE.read_text(encoding="utf-8"))
    primary = sorted(name for name in config if name.startswith("select_primary_"))
    reconvergent = sorted(
        name for name in config if name.startswith("select_reconvergent_")
    )
    target = primary[-1 - seed % min(6, len(primary))]
    config[target]["layout_column"] = 2 + seed % 5
    if seed % 2:
        source = config[target].get("source")
        if isinstance(source, dict):
            config[target]["source"] = dict(reversed(list(source.items())))
    if seed % 3 == 0:
        second = reconvergent[-1 - (seed // 3) % min(6, len(reconvergent))]
        config[second]["layout_column"] = 3 + seed % 4
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
    for seed in range(args.attempts):
        case_dir = args.output / f"seed-{seed:03d}"
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input.json"
        svg_path = case_dir / "output.svg"
        input_path.write_text(
            json.dumps(build_case(seed), indent=2) + "\n", encoding="utf-8"
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
        report = analyze(input_path, svg_path)
        quality = evaluate(input_path, svg_path, REGISTRY)
        row = {
            "seed": seed,
            "issues": report["detected_issues"],
            "quality_failed": quality["failed_metric_ids"],
            "premature_witnesses": report["witnesses"][
                "premature_interior_trunk_entry_witnesses"
            ],
        }
        summary.append(row)
        if row["quality_failed"]:
            (args.output / "first-failure.json").write_text(
                json.dumps(row, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(row, indent=2))
            return 1
    (args.output / "search-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"not_reproduced attempts={args.attempts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
