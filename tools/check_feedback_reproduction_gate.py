#!/usr/bin/env python3
"""Validate feedback reproduction locally and block releases in clean CI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
USER_VALIDATOR = Path.home() / ".cursor/skills/agent-quality-workflow/scripts/validate_feedback_reproduction.py"
RELEASE_STATES = {"fixed_verified", "closed"}


def _sha(path: Path) -> str:
    # All artifacts bound by this gate are text. Git may materialize the same
    # blob as CRLF on Windows and LF in Linux CI, so checkout policy must not
    # change its identity.
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _tree_hash(root: Path) -> str:
    files = [
        path for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
    ]
    records = sorted(
        (path.relative_to(ROOT).as_posix(), _sha(path)) for path in files
    )
    return _canonical(records)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _attempts(issue: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = issue.get("reproduction_attempts")
    return [item for item in attempts if isinstance(item, dict)] if isinstance(attempts, list) else []


def _command_value(command: object, flags: tuple[str, ...]) -> str | None:
    if not isinstance(command, list):
        return None
    for flag in flags:
        if flag in command:
            index = command.index(flag)
            if index + 1 < len(command) and isinstance(command[index + 1], str):
                value = command[index + 1].replace("\\", "/")
                for prefix in ("{project}/", "{snapshot}/"):
                    if value.startswith(prefix):
                        value = value[len(prefix):]
                return value
    return None


def _validate_input_lineage(issue: dict[str, Any], errors: list[str]) -> None:
    issue_id = issue.get("id", "<missing>")
    entrypoint = issue.get("entrypoint")
    oracle = issue.get("oracle")
    if not isinstance(entrypoint, dict) or not isinstance(oracle, dict):
        errors.append(f"{issue_id}: entrypoint/oracle contract is missing")
        return
    produced = _command_value(entrypoint.get("command"), ("-i", "--input"))
    observed = _command_value(oracle.get("command"), ("--input", "-i"))
    if produced is None or observed is None or produced != observed:
        errors.append(f"{issue_id}: producer and oracle input lineage differs")


def _print_issue(issue: dict[str, Any]) -> None:
    print(f"ISSUE {issue.get('id', '<missing>')}", file=sys.stderr)
    print(f"  summary: {issue.get('summary', '<missing>')}", file=sys.stderr)
    print(f"  status: {issue.get('status', '<missing>')}", file=sys.stderr)
    attempts = _attempts(issue)
    if not attempts:
        print("  attempts: none recorded", file=sys.stderr)
        print("  why_not_reproduced: no qualifying normal-user-path attempt is recorded", file=sys.stderr)
        return
    print(f"  attempts: {len(attempts)}", file=sys.stderr)
    for index, attempt in enumerate(attempts, start=1):
        for key in ("hypothesis", "method", "observed", "analysis", "why_not_reproduced", "next_condition"):
            print(f"  attempt[{index}].{key}: {attempt.get(key, '<missing>')}", file=sys.stderr)


def _validate_attempt_log(issue: dict[str, Any], errors: list[str]) -> None:
    attempts = issue.get("reproduction_attempts")
    issue_id = issue.get("id", "<missing>")
    if not isinstance(attempts, list):
        errors.append(f"{issue_id}: reproduction_attempts must be an array")
        return
    required = ("attempted_at", "hypothesis", "method", "result", "observed", "analysis", "evidence", "next_condition")
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            errors.append(f"{issue_id}: reproduction_attempts[{index}] must be an object")
            continue
        for key in required:
            if not _text(attempt.get(key)):
                errors.append(f"{issue_id}: reproduction_attempts[{index}].{key} is missing")
        if attempt.get("result") not in {"not_reproduced", "reproduction_blocked", "reproduced"}:
            errors.append(f"{issue_id}: reproduction_attempts[{index}].result is invalid")
        if attempt.get("result") != "reproduced" and not _text(attempt.get("why_not_reproduced")):
            errors.append(f"{issue_id}: reproduction_attempts[{index}].why_not_reproduced is missing")


def _validate_release_receipt(issue: dict[str, Any], errors: list[str]) -> None:
    issue_id = issue.get("id", "<missing>")
    relative = issue.get("reproduction_receipt")
    if not _text(relative):
        errors.append(f"{issue_id}: reproduction receipt path is missing")
        return
    receipt_path = (ROOT / relative).resolve()
    try:
        receipt_path.relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"{issue_id}: reproduction receipt escapes the repository")
        return
    if not receipt_path.is_file():
        errors.append(f"{issue_id}: reproduction receipt is missing")
        return
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{issue_id}: reproduction receipt is invalid: {exc}")
        return
    if receipt.get("schema_version") != 1 or receipt.get("issue_id") != issue_id:
        errors.append(f"{issue_id}: reproduction receipt identity is invalid")
    if receipt.get("result") != "reproduced":
        errors.append(f"{issue_id}: reproduction receipt does not report reproduced")
    if receipt.get("evidence_class") != "user_reproduction" or receipt.get("origin") != "natural_user_workflow":
        errors.append(f"{issue_id}: reproduction receipt is not natural user evidence")
    if receipt.get("coverage_model") != "many_to_many" or not _text(receipt.get("corpus_id")):
        errors.append(f"{issue_id}: reproduction receipt must bind a many-to-many corpus")
    for key in ("fault_injection", "output_mutated", "production_code_changed"):
        if receipt.get(key) is not False:
            errors.append(f"{issue_id}: {key} must be false")
    runs = receipt.get("attempts")
    if not isinstance(runs, list) or len(runs) < 2:
        errors.append(f"{issue_id}: two independent natural reproduction runs are required")
        return
    run_ids: list[str] = []
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            errors.append(f"{issue_id}: receipt attempt {index} is invalid")
            continue
        run_ids.append(str(run.get("run_id", "")))
        if run.get("entrypoint_reached") is not True or run.get("producer_exit_code") != 0:
            errors.append(f"{issue_id}: receipt attempt {index} did not complete through the public entrypoint")
        if run.get("oracle_exit_code") != 0:
            errors.append(f"{issue_id}: receipt attempt {index} did not observe the reported symptom")
        if run.get("corpus_id") != receipt.get("corpus_id") or not _text(run.get("case_id")):
            errors.append(f"{issue_id}: receipt attempt {index} has invalid corpus/case identity")
        observed = run.get("observed_issue_ids")
        if not isinstance(observed, list) or issue_id not in observed:
            errors.append(f"{issue_id}: receipt attempt {index} lacks direct issue observation")
        if run.get("artifact_before_oracle_sha256") != run.get("artifact_after_oracle_sha256"):
            errors.append(f"{issue_id}: receipt attempt {index} changed the artifact")
    if not all(run_ids) or len(run_ids) != len(set(run_ids)):
        errors.append(f"{issue_id}: reproduction run IDs must be present and independent")


def _validate_fix_receipt(issue: dict[str, Any], errors: list[str]) -> None:
    issue_id = issue.get("id", "<missing>")
    fix = issue.get("fix_verification")
    if not isinstance(fix, dict):
        errors.append(f"{issue_id}: fix verification is missing")
        return
    relative = fix.get("receipt")
    if not _text(relative):
        errors.append(f"{issue_id}: fix verification receipt path is missing")
        return
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"{issue_id}: fix verification receipt escapes repository")
        return
    try:
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{issue_id}: invalid fix verification receipt: {exc}")
        return
    if receipt.get("schema_version") != 1 or receipt.get("issue_id") != issue_id:
        errors.append(f"{issue_id}: fix receipt identity/schema mismatch")
    if receipt.get("hash_mode") != "sha256-normalized-text-v1":
        errors.append(f"{issue_id}: fix receipt hash mode is missing or unsupported")
    if receipt.get("result") != "fixed_verified" or receipt.get("baseline_fails") is not True or receipt.get("current_passes") is not True:
        errors.append(f"{issue_id}: fix receipt does not prove failing baseline and passing current output")
    baseline = ROOT / str(receipt.get("baseline_receipt", ""))
    if not baseline.is_file() or receipt.get("baseline_receipt_sha256") != _sha(baseline):
        errors.append(f"{issue_id}: fix receipt baseline lineage is stale")
    if receipt.get("source_tree_sha256") != _tree_hash(ROOT / "src"):
        errors.append(f"{issue_id}: fix receipt source tree is stale")
    if receipt.get("library_tree_sha256") != _tree_hash(ROOT / "drawio-lib"):
        errors.append(f"{issue_id}: fix receipt library tree is stale")
    runner = ROOT / "tools/run_feedback_fix_verification.py"
    oracle = ROOT / "tools/feedback_layout_reproduction_oracle.py"
    if receipt.get("runner_sha256") != _sha(runner) or receipt.get("oracle_sha256") != _sha(oracle):
        errors.append(f"{issue_id}: fix receipt runner/oracle lineage is stale")
    attempts = receipt.get("attempts")
    if not isinstance(attempts, list) or len(attempts) < 2:
        errors.append(f"{issue_id}: fix receipt needs two current public runs")
        return
    run_ids = []
    case_runs: dict[str, list[dict[str, Any]]] = {}
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            errors.append(f"{issue_id}: invalid fix attempt {index}")
            continue
        run_ids.append(attempt.get("run_id"))
        case_id = attempt.get("case_id")
        if not _text(case_id):
            errors.append(f"{issue_id}: fix attempt {index} has no case identity")
        else:
            case_runs.setdefault(case_id, []).append(attempt)
        if attempt.get("public_entrypoint") != "public_cli" or attempt.get("producer_exit_code") != 0:
            errors.append(f"{issue_id}: fix attempt {index} did not use a successful public CLI")
        if attempt.get("issue_oracle_exit_code") != 1 or issue_id in attempt.get("detected_issue_ids", []):
            errors.append(f"{issue_id}: fix attempt {index} still observes the symptom")
        if attempt.get("artifact_before_oracle_sha256") != attempt.get("artifact_after_oracle_sha256"):
            errors.append(f"{issue_id}: fix attempt {index} mutated the output")
        evidence = attempt.get("evidence_files")
        if not isinstance(evidence, dict) or not evidence:
            errors.append(f"{issue_id}: fix attempt {index} has no evidence")
        else:
            for relative_path, expected in evidence.items():
                evidence_path = ROOT / relative_path
                if not evidence_path.is_file() or _sha(evidence_path) != expected:
                    errors.append(f"{issue_id}: fix evidence is missing or stale: {relative_path}")
    if not all(run_ids) or len(run_ids) != len(set(run_ids)):
        errors.append(f"{issue_id}: fix run IDs must be independent")
    for case_id, runs in case_runs.items():
        if len(runs) < 2:
            errors.append(f"{issue_id}: fix case {case_id} needs two independent runs")
            continue
        inputs = {run.get("input_sha256") for run in runs}
        artifacts = {run.get("artifact_before_oracle_sha256") for run in runs}
        if None in inputs or len(inputs) != 1:
            errors.append(f"{issue_id}: fix case {case_id} does not bind one input")
        if None in artifacts or len(artifacts) != 1:
            errors.append(f"{issue_id}: fix case {case_id} is nondeterministic")


def _release_gate() -> int:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"feedback release gate: invalid manifest: {exc}", file=sys.stderr)
        return 2
    issues = manifest.get("issues") if isinstance(manifest, dict) else None
    if not isinstance(issues, list) or not issues:
        print("feedback release gate: issue list is missing or empty", file=sys.stderr)
        return 2
    errors: list[str] = []
    for issue in issues:
        if not isinstance(issue, dict):
            errors.append("issues[] must contain objects")
            continue
        issue_id = issue.get("id", "<missing>")
        _validate_attempt_log(issue, errors)
        _validate_input_lineage(issue, errors)
        if issue.get("status") not in RELEASE_STATES:
            errors.append(f"{issue_id}: release blocked; status is {issue.get('status')}")
        _validate_release_receipt(issue, errors)
        _validate_fix_receipt(issue, errors)
    incidents = manifest.get("process_incidents", [])
    if not isinstance(incidents, list):
        errors.append("process_incidents must be an array")
    else:
        for incident in incidents:
            if isinstance(incident, dict) and incident.get("release_blocking") is True and incident.get("status") != "closed":
                errors.append(f"{incident.get('id', '<missing>')}: release-blocking process incident is {incident.get('status')}")
    if errors:
        print(f"feedback release gate: FAIL ({len(errors)} errors)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("feedback reproduction issue checklist:", file=sys.stderr)
        for issue in issues:
            if isinstance(issue, dict):
                _print_issue(issue)
        return 1
    print(f"feedback release gate: PASS issues={len(issues)}")
    return 0


def _delegated_gate(phase: str) -> int:
    if not USER_VALIDATOR.is_file():
        print(f"natural-reproduction validator missing: {USER_VALIDATOR}", file=sys.stderr)
        return 2
    return subprocess.run(
        [sys.executable, str(USER_VALIDATOR), str(MANIFEST), "--project-root", str(ROOT), "--phase", phase],
        cwd=ROOT,
        check=False,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("structure", "reproduce", "solve", "release", "complete"), required=True)
    args = parser.parse_args()
    return _release_gate() if args.phase == "release" else _delegated_gate(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
