"""Generate Agent-only per-node and per-edge layout statistics.

This helper belongs to the packaged project skill, not to drawclock's public CLI.
It runs the same one-shot layout computation and exposes its internal geometry
report for regression diagnosis. CI independently recomputes the report from the
final LayoutDocument before accepting it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from auto_layout import load_clock_tree  # noqa: E402
from elk_layout import generate_elk_layout  # noqa: E402


def validate_statistics(
    statistics: dict[str, Any], config: dict[str, Any], edge_count: int
) -> list[str]:
    errors = []
    if set(statistics.get("nodes", {})) != set(config):
        errors.append("node statistics do not cover the input node set")
    if statistics.get("totals", {}).get("edges") != edge_count:
        errors.append("edge statistics do not cover the generated edge set")
    if len(statistics.get("edges", {})) != edge_count:
        errors.append("per-edge statistics count differs from generated edges")
    return errors


def build_report(input_path: Path, libraries: list[Path]) -> dict[str, Any]:
    started = time.perf_counter()
    config = load_clock_tree(input_path)
    document, report = generate_elk_layout(
        config, library_path=libraries, include_statistics=True
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    statistics = report["selection"]["routing_statistics"]
    errors = validate_statistics(statistics, config, len(document.edges))
    if errors:
        raise RuntimeError("; ".join(errors))
    return {
        "schema": 1,
        "input": str(input_path),
        "libraries": [str(path) for path in libraries],
        "generation_ms": round(elapsed_ms, 3),
        "statistics": statistics,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agent-only per-node/per-edge layout statistics"
    )
    parser.add_argument("-i", "--input", required=True, type=Path)
    parser.add_argument(
        "-l", "--library", required=True, action="append", nargs="+", type=Path
    )
    parser.add_argument("-o", "--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    libraries = [path for group in args.library for path in group]
    try:
        report = build_report(args.input, libraries)
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
