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

import check_quality_contract_retention as quality_contract


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
USER_VALIDATOR = Path.home() / ".cursor/skills/agent-quality-workflow/scripts/validate_feedback_reproduction.py"
RELEASE_STATES = {"fixed_verified", "closed"}
RECURSIVE_MANIFEST = ROOT / "tests/reproduction-corpus/recursive-attack-rounds.json"
RECURSIVE_RECEIPT = ROOT / ".reproduction/receipts/recursive-attack.json"
RECURSIVE_RUNNER = ROOT / "tools/run_recursive_reproduction_rounds.py"
RECURSIVE_ORACLE = ROOT / "tools/feedback_layout_reproduction_oracle.py"
SEMANTICS = ROOT / "tools/reproduction_semantics.py"
QUALITY_SYSTEM = ROOT / "tools/svg_quality_system.py"
QUALITY_REGISTRY = ROOT / "tests/quality-metrics.json"


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


def _git_tracked_paths(errors: list[str]) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        errors.append(f"cannot enumerate Git-tracked release evidence: {exc}")
        return set()
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        errors.append(f"cannot enumerate Git-tracked release evidence: {detail or 'git ls-files failed'}")
        return set()
    return {
        item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    }


def _require_tracked(relative_path: object, tracked_paths: set[str], label: str, errors: list[str]) -> None:
    normalized = str(relative_path).replace("\\", "/")
    if normalized not in tracked_paths:
        errors.append(f"{label} is not Git-tracked for a clean release checkout: {normalized}")


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


def _validate_release_receipt(
    issue: dict[str, Any], errors: list[str], tracked_paths: set[str] | None = None,
) -> None:
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
    if tracked_paths is not None:
        _require_tracked(relative, tracked_paths, f"{issue_id}: reproduction receipt", errors)
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
    required_variants = issue.get("required_reproduction_variants", [])
    if required_variants and receipt.get("semantics_sha256") != _sha(SEMANTICS):
        errors.append(f"{issue_id}: reproduction semantics lineage is stale")
    if receipt.get("required_reproduction_variants", []) != required_variants:
        errors.append(f"{issue_id}: reproduction variant exact-set differs")
    for key in ("fault_injection", "output_mutated", "production_code_changed"):
        if receipt.get(key) is not False:
            errors.append(f"{issue_id}: {key} must be false")
    runs = receipt.get("attempts")
    if not isinstance(runs, list) or len(runs) < 2:
        errors.append(f"{issue_id}: two independent natural reproduction runs are required")
        return
    run_ids: list[str] = []
    variant_runs: dict[str, list[dict[str, Any]]] = {}
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
        variant = run.get("semantic_variant_id")
        if _text(variant):
            variant_runs.setdefault(variant, []).append(run)
    if not all(run_ids) or len(run_ids) != len(set(run_ids)):
        errors.append(f"{issue_id}: reproduction run IDs must be present and independent")
    for variant in required_variants:
        selected = variant_runs.get(variant, [])
        if len(selected) < 2:
            errors.append(f"{issue_id}: reproduction variant {variant} needs two runs")
            continue
        for run in selected:
            if run.get("semantic_preconditions_met") is not True:
                errors.append(f"{issue_id}: variant {variant} input semantics do not match")
            if run.get("semantic_symptom_observed") is not True:
                errors.append(f"{issue_id}: variant {variant} lacks its exact symptom")
            if not _text(run.get("semantic_contract_sha256")):
                errors.append(f"{issue_id}: variant {variant} lacks a contract hash")


def _validate_fix_receipt(
    issue: dict[str, Any], errors: list[str], tracked_paths: set[str] | None = None,
) -> None:
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
    if tracked_paths is not None:
        _require_tracked(relative, tracked_paths, f"{issue_id}: fix receipt", errors)
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
    if receipt.get("semantics_sha256") != _sha(SEMANTICS):
        errors.append(f"{issue_id}: fix semantics lineage is stale")
    required_variants = issue.get("required_reproduction_variants", [])
    if receipt.get("required_reproduction_variants", []) != required_variants:
        errors.append(f"{issue_id}: fix variant exact-set differs")
    attempts = receipt.get("attempts")
    if not isinstance(attempts, list) or len(attempts) < 2:
        errors.append(f"{issue_id}: fix receipt needs two current public runs")
        return
    run_ids = []
    case_runs: dict[str, list[dict[str, Any]]] = {}
    variant_runs: dict[str, list[dict[str, Any]]] = {}
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
        variant = attempt.get("semantic_variant_id")
        if _text(variant):
            variant_runs.setdefault(variant, []).append(attempt)
        evidence = attempt.get("evidence_files")
        if not isinstance(evidence, dict) or not evidence:
            errors.append(f"{issue_id}: fix attempt {index} has no evidence")
        else:
            for relative_path, expected in evidence.items():
                evidence_path = ROOT / relative_path
                if not evidence_path.is_file() or _sha(evidence_path) != expected:
                    errors.append(f"{issue_id}: fix evidence is missing or stale: {relative_path}")
                if tracked_paths is not None:
                    _require_tracked(relative_path, tracked_paths, f"{issue_id}: fix evidence", errors)
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
    for variant in required_variants:
        selected = variant_runs.get(variant, [])
        if len(selected) < 2:
            errors.append(f"{issue_id}: fix variant {variant} needs two runs")
            continue
        for run in selected:
            if run.get("semantic_preconditions_met") is not True:
                errors.append(f"{issue_id}: fix variant {variant} input semantics do not match")
            if run.get("semantic_symptom_observed") is not False:
                errors.append(f"{issue_id}: fix variant {variant} still has its exact symptom")
            if not _text(run.get("semantic_contract_sha256")):
                errors.append(f"{issue_id}: fix variant {variant} lacks a contract hash")


def _validate_recursive_attack_receipt(
    errors: list[str], receipt_path: Path = RECURSIVE_RECEIPT,
) -> None:
    try:
        contract = json.loads(RECURSIVE_MANIFEST.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"recursive attack evidence is invalid: {exc}")
        return
    expected_rounds = contract.get("rounds")
    actual_rounds = receipt.get("rounds")
    required = contract.get("required_consecutive_clean_rounds")
    risk_minimum = {"low": 3, "medium": 5, "high": 7, "critical": 9}
    risk_class = contract.get("risk_class")
    if (
        not isinstance(expected_rounds, list)
        or required != len(expected_rounds)
        or risk_class not in risk_minimum
        or required < risk_minimum[risk_class]
        or len({item.get("strategy") for item in expected_rounds}) != required
    ):
        errors.append("recursive attack manifest has an invalid round exact-set")
        return
    if receipt.get("schema_version") != 1 or receipt.get("status") != "clean":
        errors.append("recursive attack receipt is not clean")
    if receipt.get("issues") != contract.get("issues"):
        errors.append("recursive attack issue scope differs from the contract")
    required_variants = contract.get("required_semantic_variants")
    if (
        not isinstance(required_variants, list)
        or not required_variants
        or len(required_variants) != len(set(required_variants))
    ):
        errors.append("recursive attack semantic variant contract is invalid")
        required_variants = []
    if receipt.get("required_semantic_variants") != required_variants:
        errors.append("recursive attack required semantic variants differ")
    if receipt.get("covered_semantic_variants") != sorted(required_variants):
        errors.append("recursive attack semantic coverage exact-set is incomplete")
    if (
        receipt.get("campaign_name") != contract.get("campaign_name")
        or receipt.get("risk_class") != risk_class
    ):
        errors.append("recursive attack campaign/risk profile differs")
    if receipt.get("required_consecutive_clean_rounds") != required or receipt.get("consecutive_clean_rounds") != required:
        errors.append("recursive attack consecutive clean round requirement is unmet")
    expected_identity = [(item.get("id"), item.get("strategy")) for item in expected_rounds]
    actual_identity = (
        [(item.get("id"), item.get("strategy")) for item in actual_rounds]
        if isinstance(actual_rounds, list) else []
    )
    if actual_identity != expected_identity:
        errors.append("recursive attack executed round exact-set/order differs")
    if receipt.get("source_tree_sha256") != _tree_hash(ROOT / "src"):
        errors.append("recursive attack source tree is stale")
    for key, path in (
        ("manifest_sha256", RECURSIVE_MANIFEST),
        ("runner_sha256", RECURSIVE_RUNNER),
        ("oracle_sha256", RECURSIVE_ORACLE),
        ("semantics_sha256", SEMANTICS),
        ("quality_system_sha256", QUALITY_SYSTEM),
        ("quality_registry_sha256", QUALITY_REGISTRY),
    ):
        if receipt.get(key) != _sha(path):
            errors.append(f"recursive attack {key} is stale")
    if not isinstance(actual_rounds, list):
        return
    try:
        quality_contract_payload = json.loads(QUALITY_REGISTRY.read_text(encoding="utf-8"))
        required_metric_ids = [item["id"] for item in quality_contract_payload["metrics"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f"recursive attack quality registry is invalid: {exc}")
        return
    for expected, actual in zip(expected_rounds, actual_rounds):
        cases = actual.get("cases")
        expected_count = (len(expected.get("fixtures", []))
                          + 2 * len(expected.get("seeds", []))
                          + len(expected.get("bus_rows", [])))
        if actual.get("status") != "clean" or not isinstance(cases, list) or len(cases) != expected_count:
            errors.append(f"recursive attack round {expected.get('id')} is incomplete")
            continue
        case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
        if len(case_ids) != len(set(case_ids)):
            errors.append(f"recursive attack round {expected.get('id')} repeats a case")
        for case in cases:
            if not isinstance(case, dict):
                errors.append(f"recursive attack round {expected.get('id')} has an invalid case")
                continue
            if case.get("public_entrypoint") != "public_cli" or case.get("producer_exit_code") != 0:
                errors.append(f"recursive attack case {case.get('case_id')} did not use the public CLI")
            if case.get("artifact_before_oracle_sha256") != case.get("artifact_after_oracle_sha256"):
                errors.append(f"recursive attack case {case.get('case_id')} mutated the artifact")
            if case.get("observed_issue_ids") != []:
                errors.append(f"recursive attack case {case.get('case_id')} reproduced a target issue")
            variants = case.get("semantic_variants")
            if (not isinstance(variants, list)
                    or len(variants) != len(set(variants))
                    or not set(variants).issubset(set(required_variants))):
                errors.append(f"recursive attack case {case.get('case_id')} has invalid semantic coverage")
            metric_results = case.get("metric_results")
            receipted_metric_ids = (
                [item.get("metric_id") for item in metric_results]
                if isinstance(metric_results, list)
                and all(isinstance(item, dict) for item in metric_results)
                else []
            )
            if not (
                case.get("required_metric_ids") == required_metric_ids
                and case.get("executed_metric_ids") == required_metric_ids
                and receipted_metric_ids == required_metric_ids
            ):
                errors.append(f"recursive attack case {case.get('case_id')} lacks the full metric exact-set")
            statuses = [item.get("status") for item in metric_results] if isinstance(metric_results, list) else []
            if (
                case.get("quality_passed") is not True
                or case.get("failed_metric_ids") != []
                or any(status not in {"pass", "not_applicable"} for status in statuses)
            ):
                errors.append(f"recursive attack case {case.get('case_id')} failed full artifact quality")


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
    errors: list[str] = [
        f"quality-contract: {error}"
        for error in quality_contract.validate()
    ]
    tracked_paths = _git_tracked_paths(errors)
    _validate_recursive_attack_receipt(errors)
    for issue in issues:
        if not isinstance(issue, dict):
            errors.append("issues[] must contain objects")
            continue
        issue_id = issue.get("id", "<missing>")
        _validate_attempt_log(issue, errors)
        _validate_input_lineage(issue, errors)
        if issue.get("status") not in RELEASE_STATES:
            errors.append(f"{issue_id}: release blocked; status is {issue.get('status')}")
        _validate_release_receipt(issue, errors, tracked_paths)
        _validate_fix_receipt(issue, errors, tracked_paths)
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
