#!/usr/bin/env python3
"""Fresh-generate and independently quality-gate every public SVG example."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import feedback_layout_reproduction_oracle as geometry
import svg_quality_system as quality_system
import check_quality_contract_retention as quality_contract


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ANNOTATION_PROFILES = {
    "short", "long", "multiline", "blank_line",
    "trailing_line_break", "mixed_script",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path,
        default=ROOT / "example" / "auto-layout",
    )
    parser.add_argument(
        "--library", type=Path,
        default=ROOT / "drawio-lib" / "drawclock",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    contract_errors = quality_contract.validate()
    if contract_errors:
        print("all SVG quality gate: quality contract retention failed", file=sys.stderr)
        for error in contract_errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    inputs = sorted(args.input_dir.glob("*.json"))
    if not inputs:
        print("all SVG quality gate: no input JSON files", file=sys.stderr)
        return 2
    rows = []
    with tempfile.TemporaryDirectory(prefix="drawclock-all-svg-quality-") as temp:
        output_dir = Path(temp)
        for input_path in inputs:
            output_path = output_dir / f"{input_path.stem}.svg"
            process = subprocess.run(
                [
                    sys.executable, str(ROOT / "src"),
                    "-i", str(input_path), "-l", str(args.library),
                    "-o", str(output_path), "--crossing-style", "arc",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if process.returncode != 0:
                rows.append({
                    "input": input_path.name,
                    "producer_exit": process.returncode,
                    "failures": ["producer-failed"],
                    "stderr": process.stderr[-1000:],
                })
                continue
            try:
                report = geometry.analyze(input_path, output_path)
                quality = quality_system.evaluate(input_path, output_path)
                failures = [
                    f"metric:{metric_id}"
                    for metric_id in quality["failed_metric_ids"]
                ]
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                rows.append({
                    "input": input_path.name,
                    "producer_exit": 0,
                    "failures": ["oracle-invalid-evidence"],
                    "stderr": str(exc),
                })
                continue
            rows.append({
                "input": input_path.name,
                "producer_exit": 0,
                "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
                "crossings": report["totals"]["proper_crossing_events"],
                "bends": report["totals"]["bends"],
                "different_net_overlaps": report["totals"]["different_net_overlaps"],
                "annotation_failures": report["annotation_quality"]["failure_count"],
                "annotation_color_failures": report["annotation_quality"]["color_failure_count"],
                "annotation_profiles": report["annotation_quality"]["profiles_present"],
                "required_metric_ids": quality["required_metric_ids"],
                "executed_metric_ids": quality["executed_metric_ids"],
                "metric_results": quality["metric_results"],
                "failures": failures,
            })
    profile_counts = {
        profile: sum(profile in row.get("annotation_profiles", []) for row in rows)
        for profile in sorted(REQUIRED_ANNOTATION_PROFILES)
    }
    missing_profiles = sorted(
        profile for profile, count in profile_counts.items() if count == 0
    )
    registry_ids = [
        metric["id"] for metric in quality_system.load_registry()
    ]
    metric_execution_failures = [
        row.get("input", "<unknown>")
        for row in rows
        if row.get("producer_exit") == 0
        and (
            row.get("required_metric_ids") != registry_ids
            or row.get("executed_metric_ids") != registry_ids
        )
    ]
    payload = {
        "schema_version": 1,
        "input_dir": str(args.input_dir.resolve()),
        "library": str(args.library.resolve()),
        "expected_count": len(inputs),
        "observed_count": len(rows),
        "failed_count": sum(bool(row["failures"]) for row in rows),
        "annotation_profile_case_counts": profile_counts,
        "missing_annotation_profiles": missing_profiles,
        "quality_metric_registry_ids": registry_ids,
        "metric_execution_failures": metric_execution_failures,
        "batch_failures": (
            (["annotation-profile-coverage"] if missing_profiles else [])
            + (["full-metric-execution"] if metric_execution_failures else [])
        ),
        "cases": rows,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    if payload["failed_count"] or payload["batch_failures"]:
        print(
            f"all SVG quality gate: rejected {payload['failed_count']}/{len(inputs)}",
            file=sys.stderr,
        )
        return 1
    print(f"all SVG quality gate: PASS {len(inputs)}/{len(inputs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
