"""Validate a feature/interaction/scenario coverage manifest."""

from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROLES = {"success", "boundary", "fault", "environment", "release"}


def _objects(items: Any, owner: str, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{owner} must be a list")
        return []
    result = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{owner}[{index}] must be an object")
        else:
            result.append(item)
    return result


def _id_map(items: list[dict[str, Any]], owner: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in items:
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier:
            errors.append(f"{owner} item has no non-empty id")
        elif identifier in result:
            errors.append(f"duplicate {owner} id: {identifier}")
        else:
            result[identifier] = item
    return result


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def validate(data: dict[str, Any], project_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != 1:
        errors.append("schema must equal 1")
    features = _id_map(_objects(data.get("features"), "features", errors), "feature", errors)
    interactions = _id_map(_objects(data.get("interactions"), "interactions", errors), "interaction", errors)
    scenarios = _id_map(_objects(data.get("scenarios"), "scenarios", errors), "scenario", errors)
    covered_feature_roles: dict[str, set[str]] = defaultdict(set)
    covered_interaction_roles: dict[str, set[str]] = defaultdict(set)
    for identifier, item in features.items():
        for field in ("category", "requirement", "oracle", "proves", "does_not_prove"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"feature {identifier} missing {field}")
        roles = item.get("required_roles")
        if not isinstance(roles, list) or not roles:
            errors.append(f"feature {identifier} has no required_roles")
        elif any(role not in ROLES for role in roles):
            errors.append(f"feature {identifier} has invalid required_roles")
    for identifier, item in interactions.items():
        members = item.get("features")
        if not isinstance(members, list) or len(members) < 2:
            errors.append(f"interaction {identifier} must name at least two features")
        else:
            unknown = sorted(set(members) - set(features))
            if unknown:
                errors.append(f"interaction {identifier} has unknown features: {unknown}")
        if item.get("risk") not in {"medium", "high", "critical"}:
            errors.append(f"interaction {identifier} has invalid risk")
        roles = item.get("required_roles")
        if not isinstance(roles, list) or not roles or any(role not in ROLES for role in roles):
            errors.append(f"interaction {identifier} has invalid required_roles")
        if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
            errors.append(f"interaction {identifier} missing rationale")
    test_cache: dict[Path, set[str]] = {}
    for identifier, item in scenarios.items():
        role = item.get("role")
        if role not in ROLES:
            errors.append(f"scenario {identifier} has invalid role")
            continue
        feature_refs = item.get("covers_features")
        interaction_refs = item.get("covers_interactions")
        if not isinstance(feature_refs, list):
            errors.append(f"scenario {identifier} covers_features must be a list")
            feature_refs = []
        if not isinstance(interaction_refs, list):
            errors.append(f"scenario {identifier} covers_interactions must be a list")
            interaction_refs = []
        if not feature_refs and not interaction_refs:
            errors.append(f"scenario {identifier} covers nothing")
        for ref in feature_refs:
            if ref not in features:
                errors.append(f"scenario {identifier} has unknown feature {ref}")
            else:
                covered_feature_roles[ref].add(role)
        for ref in interaction_refs:
            if ref not in interactions:
                errors.append(f"scenario {identifier} has unknown interaction {ref}")
            else:
                covered_interaction_roles[ref].add(role)
        tests = item.get("tests")
        oracles = item.get("oracles")
        if not isinstance(tests, list) or not tests:
            errors.append(f"scenario {identifier} has no tests")
            tests = []
        if not isinstance(oracles, list) or not oracles or any(not isinstance(value, str) or not value.strip() for value in oracles):
            errors.append(f"scenario {identifier} has no valid oracles")
        if project_root is not None:
            for fixture in item.get("fixtures", []):
                if not (project_root / fixture).is_file():
                    errors.append(f"scenario {identifier} missing fixture: {fixture}")
            for test_id in tests:
                if not isinstance(test_id, str) or "::" not in test_id:
                    errors.append(f"scenario {identifier} invalid test id: {test_id}")
                    continue
                relative, function = test_id.split("::", 1)
                path = project_root / relative
                if not path.is_file():
                    errors.append(f"scenario {identifier} missing test file: {relative}")
                    continue
                if path not in test_cache:
                    try:
                        test_cache[path] = _test_functions(path)
                    except (OSError, SyntaxError, UnicodeError) as exc:
                        errors.append(f"cannot parse {relative}: {exc}")
                        test_cache[path] = set()
                if function not in test_cache[path]:
                    errors.append(f"scenario {identifier} missing test function: {test_id}")
    for identifier, item in features.items():
        missing = set(item.get("required_roles", [])) - covered_feature_roles[identifier]
        if missing:
            errors.append(f"feature {identifier} missing roles: {sorted(missing)}")
    for identifier, item in interactions.items():
        missing = set(item.get("required_roles", [])) - covered_interaction_roles[identifier]
        if missing:
            errors.append(f"interaction {identifier} missing roles: {sorted(missing)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(exc)
        return 1
    if not isinstance(data, dict):
        print("manifest root must be an object")
        return 1
    errors = validate(data, args.project_root)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS features={len(data['features'])} interactions={len(data['interactions'])} scenarios={len(data['scenarios'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
