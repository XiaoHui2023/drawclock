"""Fail closed unless a runnable release artifact is bound to its build inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any, Dict, List


REQUIRED_FIELDS = (
    "schema_version", "artifact", "artifact_sha256", "source_revision",
    "build_entrypoint", "platform",
)


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_revision(root: pathlib.Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), text=True,
        encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise ValueError("cannot resolve current Git revision")
    return completed.stdout.strip()


def load_manifest(path: pathlib.Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("invalid build manifest: {0}".format(exc))
    if not isinstance(payload, dict):
        raise ValueError("build manifest must be an object")
    return payload


def validate(artifact: pathlib.Path, manifest_path: pathlib.Path,
             expected_revision: str) -> List[str]:
    errors: List[str] = []
    if not artifact.is_file():
        return ["artifact is missing: {0}".format(artifact)]
    if not manifest_path.is_file():
        return ["build manifest is missing: {0}".format(manifest_path)]
    try:
        manifest = load_manifest(manifest_path)
    except ValueError as exc:
        return [str(exc)]
    missing = [field for field in REQUIRED_FIELDS if not manifest.get(field)]
    if missing:
        errors.append("build manifest fields missing: {0}".format(", ".join(missing)))
    if manifest.get("schema_version") != 1:
        errors.append("unsupported build manifest schema")
    if manifest.get("artifact") != artifact.name:
        errors.append("manifest artifact name differs from target artifact")
    if manifest.get("artifact_sha256", "").lower() != sha256(artifact).lower():
        errors.append("manifest artifact SHA-256 differs from target artifact")
    if manifest.get("source_revision") != expected_revision:
        errors.append("manifest source revision differs from expected revision")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="verify a runnable artifact is bound to its source revision"
    )
    parser.add_argument("--artifact", required=True, type=pathlib.Path)
    parser.add_argument("--manifest", type=pathlib.Path)
    parser.add_argument("--source-revision")
    parser.add_argument("--project-root", type=pathlib.Path,
                        default=pathlib.Path(__file__).parents[1])
    args = parser.parse_args()
    artifact = args.artifact.resolve()
    manifest = (args.manifest or artifact.with_name("build-manifest.json")).resolve()
    try:
        revision = args.source_revision or current_revision(args.project_root.resolve())
    except ValueError as exc:
        print("release lineage: FAIL {0}".format(exc), file=sys.stderr)
        return 2
    errors = validate(artifact, manifest, revision)
    if errors:
        print("release lineage: FAIL", file=sys.stderr)
        for error in errors:
            print("- {0}".format(error), file=sys.stderr)
        return 1
    print("release lineage: PASS artifact={0} revision={1}".format(artifact.name, revision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
