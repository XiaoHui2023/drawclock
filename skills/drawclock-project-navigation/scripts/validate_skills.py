"""Validate the project skills shipped in a drawclock release."""

from __future__ import annotations

import re
import sys
from pathlib import Path


EXPECTED_SKILLS = (
    "clock-diagram-design",
    "clock-json-schema",
    "clock-layout-algorithms",
    "component-library-design",
    "drawclock-project-navigation",
)
FORBIDDEN_PATTERNS = (
    ("Windows user path", re.compile(r"(?i)[a-z]:[/\\]users[/\\]")),
    ("Unix home path", re.compile(r"/(?:home|users)/[^/\s]+/")),
    ("private skill store", re.compile(r"(?i)(?:\.cursor|\.agents)[/\\]skills")),
    ("workspace-specific drive path", re.compile(r"(?i)\b[a-z]:\\")),
    ("placeholder", re.compile(r"\b(?:TO[D]O|TB[D])\b")),
)
FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
NAME_RE = re.compile(r"(?m)^name:\s*([^\n]+)$")
DESCRIPTION_RE = re.compile(r"(?m)^description:\s*(\S.*)$")
REFERENCE_LINK_RE = re.compile(r"\[[^\]]+\]\((references/[^)#]+)(?:#[^)]+)?\)")


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def validate(skills_root: Path) -> list[str]:
    root = skills_root.resolve()
    errors: list[str] = []
    actual = sorted(path.name for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
    if actual != list(EXPECTED_SKILLS):
        errors.append(
            f"skill directories differ: expected={list(EXPECTED_SKILLS)} actual={actual}"
        )
        return errors

    all_text_files = sorted(
        path for path in root.rglob("*") if path.is_file() and path.suffix in {".md", ".py"}
    )
    for path in all_text_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{_relative(path, root)} is not UTF-8: {exc}")
            continue
        for label, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(f"{_relative(path, root)} contains {label}")

    for name in EXPECTED_SKILLS:
        skill_dir = root / name
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"{name}/SKILL.md is missing")
            continue
        text = skill_file.read_text(encoding="utf-8")
        frontmatter = FRONTMATTER_RE.match(text)
        if frontmatter is None:
            errors.append(f"{name}/SKILL.md has invalid frontmatter")
            continue
        name_match = NAME_RE.search(frontmatter.group("body"))
        description_match = DESCRIPTION_RE.search(frontmatter.group("body"))
        if name_match is None or name_match.group(1).strip() != name:
            errors.append(f"{name}/SKILL.md frontmatter name does not match directory")
        if description_match is None:
            errors.append(f"{name}/SKILL.md has no one-line description")

        references = skill_dir / "references"
        if not references.is_dir():
            errors.append(f"{name}/references is missing")
            continue
        nested = [path for path in references.rglob("*") if path.is_dir()]
        if nested:
            errors.append(f"{name}/references must stay one level deep")
        linked = set(REFERENCE_LINK_RE.findall(text))
        present = {
            path.relative_to(skill_dir).as_posix()
            for path in references.iterdir()
            if path.is_file()
        }
        missing = sorted(linked - present)
        unlinked = sorted(present - linked)
        if missing:
            errors.append(f"{name} has broken reference links: {missing}")
        if unlinked:
            errors.append(f"{name} has unlinked reference files: {unlinked}")

    return errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parents[2]
    errors = validate(root)
    if errors:
        print("project skill validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"project skill validation passed: {len(EXPECTED_SKILLS)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
