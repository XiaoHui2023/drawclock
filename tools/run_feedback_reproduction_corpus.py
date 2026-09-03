#!/usr/bin/env python3
"""Run a many-to-many feedback corpus through frozen public CLIs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
ORACLE = ROOT / "tools/feedback_layout_reproduction_oracle.py"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def issue_contract(issue: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "summary", "expected", "actual", "owner_paths", "reproduction_paths", "baseline_revision", "entrypoint", "oracle", "reproduction_proves", "reproduction_does_not_prove")
    return {key: issue.get(key) for key in keys}


def tree_hash(root: Path) -> str:
    return canonical([(path.relative_to(root).as_posix(), sha(path)) for path in sorted(root.rglob("*")) if path.is_file()])


def archive(revision: str, destination: Path) -> str:
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", f"{revision}^{{commit}}"], capture_output=True, text=True, check=True).stdout.strip()
    bundle = destination.parent / "baseline.zip"
    with bundle.open("wb") as output:
        subprocess.run(["git", "-C", str(ROOT), "archive", "--format=zip", commit], stdout=output, check=True)
    destination.mkdir()
    with zipfile.ZipFile(bundle) as value:
        value.extractall(destination)
    return commit


def run(
    command: list[str],
    cwd: Path,
    output: Path,
    env: dict[str, str],
    redactions: tuple[tuple[Path, str], ...] = (),
) -> int:
    completed = subprocess.run(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, check=False,
    )
    payload = completed.stdout
    for private_path, token in redactions:
        for spelling in {str(private_path), private_path.as_posix()}:
            payload = payload.replace(spelling.encode("utf-8"), token.encode("ascii"))
    output.write_bytes(payload)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "tests/reproduction-corpus/evidence-corpus.json")
    parser.add_argument("--legacy-python", type=Path)
    args = parser.parse_args(argv)
    corpus = json.loads(args.corpus.read_text(encoding="utf-8-sig"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8-sig"))
    issues = {item["id"]: item for item in ledger["issues"]}
    run_group = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    evidence_root = ROOT / ".reproduction/evidence" / run_group
    evidence_root.mkdir(parents=True)
    attempts_by_issue: dict[str, list[dict[str, Any]]] = {issue: [] for issue in issues}
    case_summary = []
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for case in corpus["cases"]:
        if case["python_role"] == "legacy" and args.legacy_python is None:
            print("legacy corpus case requires --legacy-python", file=sys.stderr)
            return 2
        case_dir = evidence_root / case["id"]
        case_dir.mkdir()
        with tempfile.TemporaryDirectory(prefix="drawclock-frozen-") as temporary:
            snapshot = Path(temporary) / "snapshot"
            commit = archive(case["baseline_revision"], snapshot)
            before_tree = tree_hash(snapshot)
            python = str(args.legacy_python if case["python_role"] == "legacy" else Path(sys.executable))
            input_path = ROOT / case["input"]
            for index in range(corpus["attempts_per_case"]):
                trial = case_dir / f"attempt-{index + 1}"
                trial.mkdir()
                svg = trial / "output.svg"
                producer_log = trial / "producer.log"
                report_path = trial / "report.json"
                command = [python, str(snapshot / "src")]
                if case["cli_mode"] == "draw_subcommand":
                    command.append("draw")
                command.extend(["-i", str(input_path), "-l", str(snapshot / case["library"]), "-o", str(svg), "--crossing-style", "none"])
                started = datetime.now(timezone.utc).isoformat()
                redactions = ((ROOT, "{project}"), (snapshot, "{snapshot}"), (trial, "{trial}"))
                producer_exit = run(command, ROOT, producer_log, env, redactions)
                if producer_exit != 0 or not svg.is_file():
                    print(f"producer failed: {case['id']} attempt {index + 1}", file=sys.stderr)
                    return 1
                artifact_before = sha(svg)
                report_command = [sys.executable, str(ORACLE), "--input", str(input_path), "--svg", str(svg), "--report", str(report_path)]
                report_log = trial / "report.log"
                if run(report_command, ROOT, report_log, env, redactions) != 0:
                    print(f"oracle report failed: {case['id']} attempt {index + 1}", file=sys.stderr)
                    return 1
                report = json.loads(report_path.read_text(encoding="utf-8"))
                for issue_id in case["issues"]:
                    oracle_log = trial / f"{issue_id}.log"
                    oracle_command = [sys.executable, str(ORACLE), "--input", str(input_path), "--svg", str(svg), "--issue", issue_id]
                    oracle_exit = run(oracle_command, ROOT, oracle_log, env, redactions)
                    evidence = [svg, producer_log, report_path, report_log, oracle_log]
                    attempts_by_issue[issue_id].append({
                        "run_id": f"{run_group}:{case['id']}:{index + 1}",
                        "corpus_id": run_group, "case_id": case["id"],
                        "observed_issue_ids": report["detected_issues"],
                        "public_entrypoint": "public_cli", "entrypoint_reached": True,
                        "producer_exit_code": producer_exit, "oracle_exit_code": oracle_exit,
                        "baseline_revision": commit,
                        "artifact_before_oracle_sha256": artifact_before,
                        "artifact_after_oracle_sha256": sha(svg),
                        "producer_tree_before_sha256": before_tree,
                        "producer_tree_after_sha256": tree_hash(snapshot),
                        "command_sha256": canonical(command), "input_sha256": sha(input_path),
                        "runner_sha256": sha(Path(__file__)), "oracle_sha256": sha(ORACLE),
                        "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(),
                        "evidence_files": {path.relative_to(ROOT).as_posix(): sha(path) for path in evidence},
                    })
                case_summary.append({"case_id": case["id"], "attempt": index + 1, "detected_issues": report["detected_issues"], "totals": report["totals"]})
    missing = [issue for issue, attempts in attempts_by_issue.items() if len(attempts) < 2 or any(item["oracle_exit_code"] != 0 for item in attempts)]
    corpus_receipt = {"schema_version": 1, "corpus_id": run_group, "coverage_model": "many_to_many", "cases": case_summary, "issue_attempt_counts": {key: len(value) for key, value in attempts_by_issue.items()}, "missing_issues": missing}
    corpus_receipt_path = ROOT / ".reproduction/receipts/corpus.json"
    corpus_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_receipt_path.write_text(json.dumps(corpus_receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for issue_id, attempts in attempts_by_issue.items():
        if not attempts:
            continue
        issue = issues[issue_id]
        receipt = {
            "schema_version": 1, "issue_id": issue_id, "result": "reproduced" if len(attempts) >= 2 and all(item["oracle_exit_code"] == 0 for item in attempts) else "not_reproduced",
            "evidence_class": "user_reproduction", "origin": "natural_user_workflow",
            "fault_injection": False, "output_mutated": False, "production_code_changed": False,
            "coverage_model": "many_to_many", "corpus_id": run_group,
            "issue_contract_sha256": canonical(issue_contract(issue)), "attempts": attempts,
        }
        (ROOT / issue["reproduction_receipt"]).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(corpus_receipt, ensure_ascii=False, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
