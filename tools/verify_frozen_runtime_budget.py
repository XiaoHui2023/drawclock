#!/usr/bin/env python3
"""Fail closed unless a frozen binary renders a real regression case twice in budget."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from search_dual_public_bus_coverage import REQUIRED_SCENARIOS_ALL, build_case
from svg_quality_system import DEFAULT_REGISTRY, evaluate_with_geometry


DEFAULT_SCENARIO = "dual-public-small-staggered-triple-four"
TARGET_WITNESS = "premature_interior_trunk_entry"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_once(
    binary: Path,
    input_path: Path,
    library: Path,
    svg_path: Path,
    max_seconds: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    command = [
        str(binary),
        "-i", str(input_path),
        "-l", str(library),
        "-o", str(svg_path),
        "--crossing-style", "arc",
    ]
    environment = os.environ.copy()
    isolated_path = svg_path.parent / "empty-path"
    isolated_path.mkdir(exist_ok=True)
    environment["PATH"] = str(isolated_path)
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=max_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "duration_seconds": round(time.perf_counter() - started, 6),
            "max_seconds": max_seconds,
            "returncode": None,
            "output_exists": svg_path.is_file(),
            "stdout_tail": (exc.stdout or "")[-1000:],
            "stderr_tail": (exc.stderr or "")[-1000:],
        }

    duration = time.perf_counter() - started
    status = "passed"
    if completed.returncode != 0 or not svg_path.is_file():
        status = "cli-failed"
    elif duration > max_seconds:
        status = "budget-exceeded"
    return {
        "status": status,
        "duration_seconds": round(duration, 6),
        "max_seconds": max_seconds,
        "returncode": completed.returncode,
        "output_exists": svg_path.is_file(),
        "output_bytes": svg_path.stat().st_size if svg_path.is_file() else None,
        "output_sha256": _sha256(svg_path) if svg_path.is_file() else None,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    input_path = output / "input.json"
    input_path.write_text(
        json.dumps(build_case(REQUIRED_SCENARIOS_ALL[args.scenario]), indent=2) + "\n",
        encoding="utf-8",
    )

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "gate": "frozen-runtime-budget",
        "scenario": args.scenario,
        "max_render_seconds": args.max_render_seconds,
        "binary": str(args.binary.resolve()),
        "binary_sha256": _sha256(args.binary),
        "input": str(input_path),
        "input_bytes": input_path.stat().st_size,
        "input_sha256": _sha256(input_path),
        "runs": [],
        "deterministic": False,
        "quality": [],
        "target_witness": TARGET_WITNESS,
        "target_witness_count": None,
        "status": "failed",
        "failures": [],
    }

    for index in (1, 2):
        svg_path = output / f"run-{index}.svg"
        run = _run_once(
            args.binary.resolve(),
            input_path,
            args.library.resolve(),
            svg_path,
            args.max_render_seconds,
        )
        receipt["runs"].append(run)
        if run["status"] != "passed":
            receipt["failures"].append(f"run-{index}:{run['status']}")

    successful = all(run["status"] == "passed" for run in receipt["runs"])
    if successful:
        hashes = [run["output_sha256"] for run in receipt["runs"]]
        receipt["deterministic"] = len(set(hashes)) == 1
        if not receipt["deterministic"]:
            receipt["failures"].append("nondeterministic-output")

        witness_count = 0
        for index in (1, 2):
            quality, geometry = evaluate_with_geometry(
                input_path,
                output / f"run-{index}.svg",
                args.registry.resolve(),
            )
            witnesses = geometry["witnesses"].get(TARGET_WITNESS, [])
            witness_count += len(witnesses)
            receipt["quality"].append({
                "run": index,
                "required_metric_ids": quality["required_metric_ids"],
                "executed_metric_ids": quality["executed_metric_ids"],
                "failed_metric_ids": quality["failed_metric_ids"],
                "passed": quality["passed"],
                "target_witness_count": len(witnesses),
            })
            if not quality["passed"]:
                receipt["failures"].append(
                    f"run-{index}:quality:{','.join(quality['failed_metric_ids'])}"
                )
            if witnesses:
                receipt["failures"].append(f"run-{index}:{TARGET_WITNESS}")
        receipt["target_witness_count"] = witness_count

    if not receipt["failures"] and receipt["deterministic"]:
        receipt["status"] = "passed"
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--library", type=Path, default=ROOT / "drawio-lib")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--scenario", choices=tuple(REQUIRED_SCENARIOS_ALL), default=DEFAULT_SCENARIO)
    parser.add_argument("--max-render-seconds", type=float, required=True)
    args = parser.parse_args()
    if args.max_render_seconds <= 0:
        parser.error("--max-render-seconds must be positive")
    if not args.binary.is_file():
        parser.error(f"binary does not exist: {args.binary}")
    if not args.library.is_dir():
        parser.error(f"library does not exist: {args.library}")

    receipt_path = args.output.resolve() / "receipt.json"
    try:
        receipt = verify(args)
    except Exception as exc:
        args.output.resolve().mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema_version": 1,
            "gate": "frozen-runtime-budget",
            "status": "failed",
            "failures": [f"gate-exception:{type(exc).__name__}:{exc}"],
        }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "frozen-runtime-budget: "
        + ("PASS" if receipt["status"] == "passed" else "FAIL")
        + f" receipt={receipt_path}"
    )
    for failure in receipt.get("failures", []):
        print(f"- {failure}", file=sys.stderr)
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
