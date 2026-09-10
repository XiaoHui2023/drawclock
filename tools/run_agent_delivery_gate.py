#!/usr/bin/env python3
"""Issue a Codex delivery receipt without allowing unreproduced product edits."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
USER_VALIDATOR = Path.home() / ".cursor/skills/agent-quality-workflow/scripts/validate_feedback_reproduction.py"
PROJECT_VALIDATOR = ROOT / "tools/check_feedback_reproduction_gate.py"
READY = ROOT / ".codex/evidence/delivery-ready.json"
BLOCKED = ROOT / ".codex/evidence/delivery-blocked.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    entries = result.stdout.decode("utf-8", errors="strict").split("\0")
    paths: list[str] = []
    for entry in entries:
        if len(entry) >= 4:
            paths.append(entry[3:].replace("\\", "/"))
    return paths


def prospective_tree() -> str:
    """Match the managed hard-gate Git-state fingerprint exactly."""
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=ROOT, capture_output=True, check=False,
    )
    tracked = subprocess.run(
        (["git", "diff", "--binary", "--no-ext-diff", "HEAD"]
         if head.returncode == 0 else
         ["git", "diff", "--binary", "--no-ext-diff"]),
        cwd=ROOT, check=True, capture_output=True,
    )
    cached = subprocess.run(
        ["git", "diff", "--cached", "--binary", "--no-ext-diff"],
        cwd=ROOT, check=True, capture_output=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v2", "-z", "--untracked-files=normal"],
        cwd=ROOT, check=True, capture_output=True,
    )
    digest = hashlib.sha256()
    for label, value in (
        (b"head", head.stdout if head.returncode == 0 else b"<unborn>"),
        (b"tracked", tracked.stdout),
        (b"cached", cached.stdout),
        (b"status", status.stdout),
    ):
        digest.update(label + b"\0" + value + b"\0")
    return "git-state-sha256:" + digest.hexdigest()


def write_blocked(phase: str, detail: str) -> None:
    READY.unlink(missing_ok=True)
    BLOCKED.parent.mkdir(parents=True, exist_ok=True)
    BLOCKED.write_text(
        json.dumps({"schema_version": 1, "status": "blocked", "phase": phase, "detail": detail}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def delivery_phase(paths: list[str], trigger_command: str) -> str:
    release_trigger = bool(re.search(r"(?i)(?:^|[\\/\s])(pack(?:\.bat|\.sh)?|bundle_release\.py)(?:\s|$)|\bgh\s+release\b", trigger_command))
    if release_trigger:
        return "release"
    return "release" if any(path == "src" or path.startswith("src/") for path in paths) else "structure"


def main() -> int:
    required_environment = ("CODEX_GATE_CHALLENGE", "CODEX_GATE_POLICY_SHA256", "CODEX_GATE_COMMAND_SHA256")
    missing = [name for name in required_environment if not os.environ.get(name)]
    if missing:
        print(
            "managed-hook-only delivery gate: missing managed challenge environment: "
            f"{', '.join(missing)}. Direct invocation is an expected negative control and "
            "cannot issue a trusted receipt; do not set these variables manually. Let the "
            "managed Stop hook run, or use a host path whose protected command is covered by "
            "PreToolUse, then verify the receipt artifact_tree against the current prospective "
            "Git tree. If the receipt stays stale, diagnose host tool-hook coverage.",
            file=sys.stderr,
        )
        return 2
    paths = changed_paths()
    trigger_command = os.environ.get("CODEX_GATE_TRIGGER_COMMAND", "")
    phase = delivery_phase(paths, trigger_command)
    validator = PROJECT_VALIDATOR if phase == "release" else USER_VALIDATOR
    if not validator.is_file():
        print(f"reproduction validator is missing: {validator}", file=sys.stderr)
        return 2
    validation = subprocess.run(
        ([sys.executable, str(validator), "--phase", phase] if phase == "release" else
         [sys.executable, str(validator), str(MANIFEST), "--project-root", str(ROOT), "--phase", phase]),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    detail = (validation.stdout + validation.stderr).strip()
    if validation.returncode != 0:
        write_blocked(phase, detail)
        print(detail, file=sys.stderr)
        return 1
    policy = ROOT / ".codex/quality-gate.json"
    receipt = {
        "schema_version": 2,
        "status": "delivery-ready",
        "artifact_tree": prospective_tree(),
        "artifact_hashes": {},
        "policy_sha256": os.environ["CODEX_GATE_POLICY_SHA256"],
        "delivery_command_sha256": os.environ["CODEX_GATE_COMMAND_SHA256"],
        "validator_id": "drawclock-feedback-reproduction-gate-v2",
        "challenge": os.environ["CODEX_GATE_CHALLENGE"],
        "evidence": {
            "phase": phase,
            "manifest_sha256": sha256(MANIFEST),
            "validator_sha256": sha256(validator),
            "changed_paths": paths,
            "trigger_command": trigger_command,
            "policy_file_sha256": sha256(policy),
        },
    }
    BLOCKED.unlink(missing_ok=True)
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"drawclock Agent delivery gate: PASS phase={phase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
