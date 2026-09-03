from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
POLICY = ROOT / ".codex/quality-gate.json"
CHECKER = ROOT / "tools/check_feedback_reproduction_gate.py"


class FeedbackReproductionGateTest(unittest.TestCase):
    def run_gate(self, phase: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--phase", phase],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_open_issue_ledger_is_structurally_valid(self) -> None:
        result = self.run_gate("structure")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_open_issues_block_product_solution_phase(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        issue_ids = [issue["id"] for issue in manifest["issues"]]
        result = self.run_gate("solve")
        self.assertNotEqual(result.returncode, 0)
        for issue_id in issue_ids:
            self.assertIn(issue_id, result.stderr)
        self.assertIn("solve blocked", result.stderr)

    def test_policy_checks_product_writes_before_side_effect(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        preconditions = policy["write_preconditions"]
        self.assertEqual(len(preconditions), 1)
        self.assertEqual(preconditions[0]["paths"], ["src/**"])
        self.assertEqual(
            preconditions[0]["command_windows"],
            ["python", "tools/check_feedback_reproduction_gate.py", "--phase", "solve"],
        )

    def test_artificial_faults_are_not_registered_as_user_reproduction(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        forbidden = ("pytest", "unittest", "monkeypatch", "fault_inject", "mutation", "rewrite_output")
        for issue in manifest["issues"]:
            command = " ".join(issue["entrypoint"]["command"]).casefold()
            self.assertFalse(any(marker in command for marker in forbidden), issue["id"])
            self.assertEqual(issue["status"], "reported")
            self.assertFalse((ROOT / issue["reproduction_receipt"]).exists(), issue["id"])


if __name__ == "__main__":
    unittest.main()
