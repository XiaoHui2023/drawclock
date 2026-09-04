from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor/skills/project-goals/issues/user-feedback-natural-reproduction.json"
POLICY = ROOT / ".codex/quality-gate.json"
CHECKER = ROOT / "tools/check_feedback_reproduction_gate.py"
WORKFLOW = ROOT / ".github/workflows/release.yml"
DELIVERY_GATE = ROOT / "tools/run_agent_delivery_gate.py"
USER_VALIDATOR = Path.home() / ".cursor/skills/agent-quality-workflow/scripts/validate_feedback_reproduction.py"


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

    def test_release_hashes_are_stable_across_lf_and_crlf_checkouts(self) -> None:
        spec = importlib.util.spec_from_file_location("drawclock_feedback_checker", CHECKER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            lf = Path(directory) / "lf.txt"
            crlf = Path(directory) / "crlf.txt"
            lf.write_bytes(b"first\nsecond\n")
            crlf.write_bytes(b"first\r\nsecond\r\n")
            self.assertEqual(module._sha(lf), module._sha(crlf))

    def test_source_hash_ignores_generated_egg_info(self) -> None:
        spec = importlib.util.spec_from_file_location("drawclock_feedback_checker", CHECKER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = module._tree_hash(ROOT / "src")
        with tempfile.TemporaryDirectory(dir=ROOT / "src", suffix=".egg-info") as directory:
            (Path(directory) / "PKG-INFO").write_text("generated\n", encoding="utf-8")
            self.assertEqual(module._tree_hash(ROOT / "src"), before)
        self.assertEqual(module._tree_hash(ROOT / "src"), before)

    def test_tree_hash_uses_platform_neutral_posix_order(self) -> None:
        spec = importlib.util.spec_from_file_location("drawclock_feedback_checker", CHECKER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paths = [path for path in (ROOT / "drawio-lib").rglob("*") if path.is_file()]
        records = sorted(
            (path.relative_to(ROOT).as_posix(), module._sha(path)) for path in paths
        )
        self.assertEqual(module._tree_hash(ROOT / "drawio-lib"), module._canonical(records))

    def test_naturally_reproduced_issues_unlock_solution_phase(self) -> None:
        result = self.run_gate("solve")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_release_gate_accepts_hash_bound_fix_receipts(self) -> None:
        result = self.run_gate("release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_generic_user_root_release_gate_accepts_multi_case_fix_evidence(self) -> None:
        result = subprocess.run(
            [sys.executable, str(USER_VALIDATOR), str(MANIFEST),
             "--project-root", str(ROOT), "--phase", "release"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_open_process_incident_blocks_generic_release_gate(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["process_incidents"][0]["status"] = "open"
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "manifest.json"
            mutated.write_text(json.dumps(manifest), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(USER_VALIDATOR), str(mutated),
                 "--project-root", str(ROOT), "--phase", "release"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("META-CLAIM-007", result.stderr)

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

    def test_delivery_gate_direct_invocation_is_an_explicit_negative_control(self) -> None:
        environment = os.environ.copy()
        for name in (
            "CODEX_GATE_CHALLENGE",
            "CODEX_GATE_POLICY_SHA256",
            "CODEX_GATE_COMMAND_SHA256",
        ):
            environment.pop(name, None)
        result = subprocess.run(
            [sys.executable, str(DELIVERY_GATE)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("managed-hook-only delivery gate", result.stderr)
        self.assertIn("expected negative control", result.stderr)
        self.assertIn("do not set these variables manually", result.stderr)

    def test_policy_checks_product_writes_before_side_effect(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        preconditions = policy["write_preconditions"]
        self.assertEqual(len(preconditions), 1)
        self.assertEqual(preconditions[0]["paths"], ["src/**"])
        self.assertEqual(
            preconditions[0]["command_windows"],
            ["python", "tools/check_feedback_reproduction_gate.py", "--phase", "solve"],
        )

    def test_receipts_are_natural_and_bind_direct_many_to_many_observations(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        forbidden = ("pytest", "unittest", "monkeypatch", "fault_inject", "mutation", "rewrite_output")
        for issue in manifest["issues"]:
            command = " ".join(issue["entrypoint"]["command"]).casefold()
            self.assertFalse(any(marker in command for marker in forbidden), issue["id"])
            self.assertIn(
                issue["status"],
                {"reproduced", "fix_in_progress", "fixed_verified", "closed"},
            )
            receipt = json.loads((ROOT / issue["reproduction_receipt"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt["coverage_model"], "many_to_many")
            self.assertTrue(receipt["corpus_id"])
            self.assertFalse(receipt["fault_injection"])
            self.assertFalse(receipt["output_mutated"])
            self.assertFalse(receipt["production_code_changed"])
            self.assertGreaterEqual(len(receipt["attempts"]), 2)
            for attempt in receipt["attempts"]:
                self.assertEqual(attempt["corpus_id"], receipt["corpus_id"])
                self.assertTrue(attempt["case_id"])
                self.assertIn(issue["id"], attempt["observed_issue_ids"])

    def test_corpus_is_actually_many_to_many_and_complete(self) -> None:
        corpus = json.loads((ROOT / ".reproduction/receipts/corpus.json").read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        target_ids = {issue["id"] for issue in manifest["issues"]}
        observed = {issue_id for case in corpus["cases"] for issue_id in case["detected_issues"]}
        self.assertEqual(corpus["coverage_model"], "many_to_many")
        self.assertEqual(corpus["missing_issues"], [])
        self.assertTrue(any(len(case["detected_issues"]) > 1 for case in corpus["cases"]))
        self.assertTrue(target_ids.issubset(observed))

    def test_producer_and_oracle_bind_the_same_input(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location("drawclock_feedback_checker", CHECKER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for issue in manifest["issues"]:
            errors: list[str] = []
            module._validate_input_lineage(issue, errors)
            self.assertEqual(errors, [], issue["id"])
            changed = json.loads(json.dumps(issue))
            input_index = changed["oracle"]["command"].index("--input") + 1
            changed["oracle"]["command"][input_index] = "{project}/wrong.json"
            errors = []
            module._validate_input_lineage(changed, errors)
            self.assertTrue(any("lineage differs" in error for error in errors), issue["id"])

    def test_fix_receipts_bind_current_source_and_reject_stale_lineage(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location("drawclock_feedback_checker", CHECKER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for issue in manifest["issues"]:
            errors: list[str] = []
            module._validate_fix_receipt(issue, errors)
            self.assertEqual(errors, [], issue["id"])

            changed = json.loads(json.dumps(issue))
            changed["fix_verification"]["receipt"] = ".reproduction/receipts/corpus.json"
            errors = []
            module._validate_fix_receipt(changed, errors)
            self.assertTrue(errors, issue["id"])

    def test_fix_determinism_is_scoped_to_each_input_case(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        route_issue = next(issue for issue in manifest["issues"] if issue["id"] == "FB-ROUTE-002")
        receipt_path = ROOT / route_issue["fix_verification"]["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        grouped: dict[str, list[dict[str, object]]] = {}
        for attempt in receipt["attempts"]:
            grouped.setdefault(attempt["case_id"], []).append(attempt)
        self.assertGreaterEqual(len(grouped), 2)
        for runs in grouped.values():
            self.assertGreaterEqual(len(runs), 2)
            self.assertEqual(len({run["input_sha256"] for run in runs}), 1)
            self.assertEqual(len({run["artifact_before_oracle_sha256"] for run in runs}), 1)
        self.assertGreater(
            len({runs[0]["artifact_before_oracle_sha256"] for runs in grouped.values()}),
            1,
            "different inputs should be allowed to produce different deterministic outputs",
        )

        spec = importlib.util.spec_from_file_location("drawclock_feedback_checker", CHECKER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        changed = json.loads(json.dumps(receipt))
        changed["attempts"][1]["artifact_before_oracle_sha256"] = "0" * 64
        changed["attempts"][1]["artifact_after_oracle_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_receipt = Path(temp_dir) / "receipt.json"
            temp_receipt.write_text(json.dumps(changed), encoding="utf-8")
            changed_issue = json.loads(json.dumps(route_issue))
            changed_issue["fix_verification"]["receipt"] = str(temp_receipt.relative_to(ROOT))
            errors: list[str] = []
            module._validate_fix_receipt(changed_issue, errors)
        self.assertTrue(any("nondeterministic" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
