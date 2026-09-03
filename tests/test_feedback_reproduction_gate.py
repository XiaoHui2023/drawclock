from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
POLICY = ROOT / ".codex/quality-gate.json"
CHECKER = ROOT / "tools/check_feedback_reproduction_gate.py"
WORKFLOW = ROOT / ".github/workflows/release.yml"
DELIVERY_GATE = ROOT / "tools/run_agent_delivery_gate.py"


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

    def test_every_open_issue_is_named_by_release_failure(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        result = self.run_gate("release")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for issue in manifest["issues"]:
            self.assertIn(f"ISSUE {issue['id']}", result.stderr)
            self.assertIn("hypothesis:", result.stderr)
            self.assertIn("why_not_reproduced:", result.stderr)

    def test_release_workflow_cannot_build_or_publish_past_feedback_gate(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("feedback-reproduction-gate:", workflow)
        self.assertIn("needs: feedback-reproduction-gate", workflow)
        self.assertIn("needs: [feedback-reproduction-gate, build-linux-ubuntu16]", workflow)
        self.assertNotIn("if: always()", workflow)

    def test_pack_entrypoints_gate_before_dependencies_and_output_mutation(self) -> None:
        shell = (ROOT / "tools/pack.sh").read_text(encoding="utf-8")
        batch = (ROOT / "tools/pack.bat").read_text(encoding="utf-8")
        for script in (shell, batch):
            gate = script.index("check_feedback_reproduction_gate.py --phase release")
            self.assertLess(gate, script.index("pip install"))
            self.assertLess(gate, script.index("PyInstaller"))

    def test_delivery_gate_selects_release_from_actual_protected_command(self) -> None:
        spec = importlib.util.spec_from_file_location("drawclock_delivery_gate", DELIVERY_GATE)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for command in ("cmd /c tools\\pack.bat", "bash tools/pack.sh", "gh release create v1.0.0"):
            self.assertEqual(module.delivery_phase([], command), "release", command)
        self.assertEqual(module.delivery_phase(["src/auto_layout.py"], "git commit -m fix"), "solve")
        self.assertEqual(module.delivery_phase(["tests/test_gate.py"], "git push"), "structure")

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
