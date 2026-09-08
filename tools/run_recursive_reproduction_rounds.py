#!/usr/bin/env python3
"""Run a fail-closed defect-driven adversarial regression campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from feedback_layout_reproduction_oracle import analyze
from search_recurrent_mux_bends import build_case as build_mux_case


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/reproduction-corpus/recursive-attack-rounds.json"
ORACLE = ROOT / "tools/feedback_layout_reproduction_oracle.py"
RISK_MINIMUM_ROUNDS = {"low": 3, "medium": 5, "high": 7, "critical": 9}


def sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_tree_hash() -> str:
    files = [
        path
        for path in (ROOT / "src").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
    ]
    return canonical([(path.relative_to(ROOT).as_posix(), sha(path)) for path in sorted(files)])


def rename_config(config: dict[str, Any]) -> dict[str, Any]:
    names = {name: f"node_{index:03d}" for index, name in enumerate(sorted(config))}
    result: dict[str, Any] = {}
    for name in sorted(config, reverse=True):
        item = dict(config[name])
        source = item.get("source")
        if isinstance(source, str):
            item["source"] = names[source]
        elif isinstance(source, dict):
            item["source"] = {key: names[value] for key, value in source.items()}
        result[names[name]] = item
    return result


def build_bus_case(rows: int) -> dict[str, dict[str, object]]:
    config: dict[str, dict[str, object]] = {"shared_root": {"kind": "from"}}
    for index in range(rows):
        public = f"public_{index}"
        private = f"private_{index}"
        config[public] = {"kind": ("gate", "cell")[index % 2], "source": "shared_root"}
        config[private] = {"kind": "from"}
        parent = private
        for depth in range(1 + index % 3):
            node = f"private_{index}_{depth}"
            config[node] = {"kind": ("gate", "div", "cell")[depth % 3], "source": parent}
            parent = node
        merge = f"merge_{index}"
        config[merge] = {"kind": "mux2", "source": {"0": public, "1": parent}}
        tail = merge
        for depth in range(index % 2):
            node = f"post_{index}_{depth}"
            config[node] = {"kind": "gate", "source": tail}
            tail = node
        config[f"clock_{index}"] = {"kind": "clock", "source": tail}
    config["shared_extra"] = {"kind": "gate", "source": "shared_root"}
    config["shared_extra_clock"] = {"kind": "clock", "source": "shared_extra"}
    return config


def case_configs(round_spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    result = []
    for relative in round_spec.get("fixtures", []):
        path = ROOT / relative
        config = json.loads(path.read_text(encoding="utf-8"))
        if round_spec.get("transform") == "reverse":
            config = dict(reversed(config.items()))
        elif round_spec.get("transform") == "rename":
            config = rename_config(config)
        result.append((Path(relative).stem, config))
    generator = round_spec.get("generator")
    if generator in {"mux", "mixed"}:
        result.extend((f"mux-seed-{seed:03d}", build_mux_case(seed)) for seed in round_spec["seeds"])
    if generator == "mixed":
        result.extend((f"bus-rows-{rows:02d}", build_bus_case(rows)) for rows in round_spec["bus_rows"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    required = manifest["required_consecutive_clean_rounds"]
    risk_class = manifest.get("risk_class")
    minimum = RISK_MINIMUM_ROUNDS.get(risk_class)
    if (
        required != len(manifest["rounds"])
        or minimum is None
        or required < minimum
        or len({item.get("strategy") for item in manifest["rounds"]}) != required
    ):
        print("invalid recursive round contract", file=sys.stderr)
        return 2
    group = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    evidence_root = ROOT / ".reproduction/recursive-evidence" / group
    evidence_root.mkdir(parents=True)
    source_hash = source_tree_hash()
    completed_rounds = []
    consecutive_clean = 0
    target_issues = set(manifest["issues"])
    for round_spec in manifest["rounds"]:
        round_results = []
        for case_id, config in case_configs(round_spec):
            case_dir = evidence_root / round_spec["id"] / case_id
            case_dir.mkdir(parents=True)
            input_path = case_dir / "input.json"
            svg_path = case_dir / "output.svg"
            input_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            command = [sys.executable, str(ROOT / "src"), "-i", str(input_path), "-l", str(ROOT / "drawio-lib"), "-o", str(svg_path), "--crossing-style", "none"]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
            if run.returncode or not svg_path.is_file():
                print(f"public CLI failed: {round_spec['id']}:{case_id}", file=sys.stderr)
                return 2
            before = sha(svg_path)
            report = analyze(input_path, svg_path)
            after = sha(svg_path)
            observed = sorted(target_issues.intersection(report["detected_issues"]))
            round_results.append({
                "case_id": case_id,
                "public_entrypoint": "public_cli",
                "producer_exit_code": run.returncode,
                "input_sha256": sha(input_path),
                "artifact_before_oracle_sha256": before,
                "artifact_after_oracle_sha256": after,
                "observed_issue_ids": observed,
            })
            if observed:
                consecutive_clean = 0
                completed_rounds.append({"id": round_spec["id"], "strategy": round_spec["strategy"], "status": "reproduced", "cases": round_results})
                return write_receipt(args, manifest, group, source_hash, completed_rounds, consecutive_clean, "reproduction_found", 1)
        consecutive_clean += 1
        completed_rounds.append({"id": round_spec["id"], "strategy": round_spec["strategy"], "status": "clean", "cases": round_results})
    return write_receipt(args, manifest, group, source_hash, completed_rounds, consecutive_clean, "clean", 0)


def write_receipt(args: argparse.Namespace, manifest: dict[str, Any], group: str, source_hash: str, rounds: list[dict[str, Any]], consecutive: int, status: str, exit_code: int) -> int:
    receipt = {
        "schema_version": 1,
        "campaign_name": manifest.get("campaign_name"),
        "risk_class": manifest.get("risk_class"),
        "status": status,
        "run_id": group,
        "issues": manifest["issues"],
        "required_consecutive_clean_rounds": manifest["required_consecutive_clean_rounds"],
        "consecutive_clean_rounds": consecutive,
        "restart_semantics": "any reproduction resets to zero and requires a new run from R1",
        "source_tree_sha256": source_hash,
        "manifest_sha256": sha(args.manifest),
        "runner_sha256": sha(Path(__file__)),
        "oracle_sha256": sha(ORACLE),
        "rounds": rounds,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "consecutive_clean_rounds": consecutive, "run_id": group}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
