#!/usr/bin/env python3
"""Verify reproduced feedback issues against the current public CLI."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
CORPUS = ROOT / "tests/reproduction-corpus/evidence-corpus.json"
ORACLE = ROOT / "tools/feedback_layout_reproduction_oracle.py"


def sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_tree_hash() -> str:
    files = sorted(
        path for path in (ROOT / "src").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
    )
    return canonical([(path.relative_to(ROOT).as_posix(), sha(path)) for path in files])


def library_tree_hash() -> str:
    files = sorted(path for path in (ROOT / "drawio-lib").rglob("*") if path.is_file())
    return canonical([(path.relative_to(ROOT).as_posix(), sha(path)) for path in files])


def run(command: list[str], output: Path, env: dict[str, str]) -> int:
    completed = subprocess.run(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, check=False,
    )
    payload = completed.stdout.replace(str(ROOT).encode(), b"{project}")
    output.write_bytes(payload)
    return completed.returncode


def main() -> int:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8-sig"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8-sig"))
    issues = {item["id"]: item for item in ledger["issues"]}
    group = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    evidence_root = ROOT / ".reproduction/fix-evidence" / group
    evidence_root.mkdir(parents=True)
    attempts: dict[str, list[dict[str, Any]]] = {identifier: [] for identifier in issues}
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    source_hash = source_tree_hash()
    library_hash = library_tree_hash()
    for case in [*corpus["cases"], *corpus.get("current_fix_cases", [])]:
        input_path = ROOT / case["input"]
        case_dir = evidence_root / case["id"]
        case_dir.mkdir()
        for index in range(corpus["attempts_per_case"]):
            trial = case_dir / f"attempt-{index + 1}"
            trial.mkdir()
            svg = trial / "output.svg"
            producer_log = trial / "producer.log"
            report_path = trial / "report.json"
            command = [
                sys.executable, str(ROOT / "src"), "-i", str(input_path),
                "-l", str(ROOT / "drawio-lib"), "-o", str(svg),
                "--crossing-style", "none",
            ]
            started = datetime.now(timezone.utc).isoformat()
            producer_exit = run(command, producer_log, env)
            if producer_exit != 0 or not svg.is_file():
                print(f"producer failed: {case['id']} attempt {index + 1}", file=sys.stderr)
                return 1
            before = sha(svg)
            report_log = trial / "report.log"
            report_exit = run(
                [sys.executable, str(ORACLE), "--input", str(input_path),
                 "--svg", str(svg), "--report", str(report_path)],
                report_log, env,
            )
            if report_exit != 0:
                print(f"oracle report failed: {case['id']} attempt {index + 1}", file=sys.stderr)
                return 1
            report = json.loads(report_path.read_text(encoding="utf-8"))
            for issue_id in case["issues"]:
                issue_log = trial / f"{issue_id}.log"
                issue_exit = run(
                    [sys.executable, str(ORACLE), "--input", str(input_path),
                     "--svg", str(svg), "--issue", issue_id], issue_log, env,
                )
                evidence = (svg, producer_log, report_path, report_log, issue_log)
                attempts[issue_id].append({
                    "run_id": f"{group}:{case['id']}:{index + 1}",
                    "case_id": case["id"], "public_entrypoint": "public_cli",
                    "producer_exit_code": producer_exit,
                    "issue_oracle_exit_code": issue_exit,
                    "detected_issue_ids": report["detected_issues"],
                    "artifact_before_oracle_sha256": before,
                    "artifact_after_oracle_sha256": sha(svg),
                    "input_sha256": sha(input_path),
                    "source_tree_sha256": source_hash,
                    "library_tree_sha256": library_hash,
                    "runner_sha256": sha(Path(__file__)),
                    "oracle_sha256": sha(ORACLE),
                    "started_at": started,
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "evidence_files": {
                        path.relative_to(ROOT).as_posix(): sha(path) for path in evidence
                    },
                })
    failures = []
    receipt_root = ROOT / ".reproduction/fix-receipts"
    receipt_root.mkdir(parents=True, exist_ok=True)
    for issue_id, issue_attempts in attempts.items():
        baseline_path = ROOT / issues[issue_id]["reproduction_receipt"]
        case_hashes: dict[str, set[str]] = {}
        for item in issue_attempts:
            case_hashes.setdefault(item["case_id"], set()).add(
                item["artifact_before_oracle_sha256"]
            )
        passed = (
            len(issue_attempts) >= 2
            and all(item["producer_exit_code"] == 0 for item in issue_attempts)
            and all(item["issue_oracle_exit_code"] == 1 for item in issue_attempts)
            and all(issue_id not in item["detected_issue_ids"] for item in issue_attempts)
            and all(len(hashes) == 1 for hashes in case_hashes.values())
        )
        if not passed:
            failures.append(issue_id)
        receipt = {
            "schema_version": 1,
            "hash_mode": "sha256-normalized-text-v1",
            "issue_id": issue_id,
            "result": "fixed_verified" if passed else "failed",
            "verification_group": group,
            "baseline_fails": True, "current_passes": passed,
            "baseline_receipt": baseline_path.relative_to(ROOT).as_posix(),
            "baseline_receipt_sha256": sha(baseline_path),
            "source_tree_sha256": source_hash,
            "library_tree_sha256": library_hash,
            "runner_sha256": sha(Path(__file__)), "oracle_sha256": sha(ORACLE),
            "attempts": issue_attempts,
        }
        (receipt_root / f"{issue_id}.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"verification_group": group, "failures": failures}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
