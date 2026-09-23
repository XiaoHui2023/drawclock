"""Tests for the independent release-artifact lineage oracle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_release_lineage", ROOT / "tools" / "verify_release_lineage.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

RUNTIME_SPEC = importlib.util.spec_from_file_location(
    "verify_frozen_runtime_budget", ROOT / "tools" / "verify_frozen_runtime_budget.py"
)
assert RUNTIME_SPEC and RUNTIME_SPEC.loader
RUNTIME_MODULE = importlib.util.module_from_spec(RUNTIME_SPEC)
RUNTIME_SPEC.loader.exec_module(RUNTIME_MODULE)


def _manifest(artifact: pathlib.Path, revision: str) -> dict:
    return {
        "schema_version": 1,
        "artifact": artifact.name,
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "source_revision": revision,
        "build_entrypoint": "tools/build_windows_release.py",
        "platform": "windows",
    }


def test_lineage_accepts_exact_artifact_and_revision(tmp_path: pathlib.Path) -> None:
    artifact = tmp_path / "drawclock.exe"
    artifact.write_bytes(b"drawclock test artifact")
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(json.dumps(_manifest(artifact, "abc123")), encoding="utf-8")
    assert MODULE.validate(artifact, manifest, "abc123") == []


def test_lineage_rejects_missing_manifest(tmp_path: pathlib.Path) -> None:
    artifact = tmp_path / "drawclock.exe"
    artifact.write_bytes(b"old artifact")
    errors = MODULE.validate(artifact, tmp_path / "build-manifest.json", "abc123")
    assert any("manifest is missing" in error for error in errors)


def test_lineage_rejects_stale_artifact_or_revision(tmp_path: pathlib.Path) -> None:
    artifact = tmp_path / "drawclock.exe"
    artifact.write_bytes(b"old artifact")
    manifest = tmp_path / "build-manifest.json"
    manifest.write_text(json.dumps(_manifest(artifact, "old-revision")), encoding="utf-8")
    artifact.write_bytes(b"mutated after build")
    errors = MODULE.validate(artifact, manifest, "new-revision")
    assert any("SHA-256 differs" in error for error in errors)
    assert any("source revision differs" in error for error in errors)


def test_frozen_runtime_budget_reports_timeout(
    tmp_path: pathlib.Path, monkeypatch,
) -> None:
    binary = tmp_path / "drawclock.exe"
    input_path = tmp_path / "input.json"
    library = tmp_path / "library"
    output = tmp_path / "output.svg"
    binary.write_bytes(b"binary")
    input_path.write_text("{}", encoding="utf-8")
    library.mkdir()

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("drawclock", 0.01, stderr="budget hit")

    monkeypatch.setattr(RUNTIME_MODULE.subprocess, "run", timeout)
    result = RUNTIME_MODULE._run_once(binary, input_path, library, output, 0.01)
    assert result["status"] == "timeout"
    assert result["returncode"] is None
    assert result["output_exists"] is False
    assert result["stderr_tail"] == "budget hit"


def test_release_requires_windows_frozen_runtime_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "build-windows:" in workflow
    assert "tools/verify_frozen_runtime_budget.py" in workflow
    assert "--max-render-seconds 60" in workflow
    assert "needs: [feedback-reproduction-gate, build-linux-ubuntu16, build-windows]" in workflow
    assert "name: windows-release" in workflow
    assert "verify-published-windows:" in workflow
    assert "needs: publish-release" in workflow
    assert 'releases/download/$tag' in workflow
    assert "published runtime receipt does not prove the complete quality metric set" in workflow
    assert workflow.count("tools/verify_frozen_runtime_budget.py") == 2
