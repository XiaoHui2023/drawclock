"""Assemble release archive: dist binaries plus docs and static assets."""

from __future__ import annotations

import pathlib
import platform
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

BINARY_NAMES = ("drawclock",)

# 默认附件只保留最终用户运行所需文件。
RELEASE_PATHS = (
    "README.md",
    "draw.md",
    "licenses/NotoSansCJK-OFL-1.1.txt",
    "drawio-lib/drawclock",
    "example/draw.json",
    "example/auto-layout/33-description-colors.json",
)


def _project_version(root: pathlib.Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        print("错误: 未在 pyproject.toml 找到 version。", file=sys.stderr)
        raise SystemExit(1)
    return match.group(1)


def _platform_tag() -> str:
    return {
        "Linux": "linux",
        "Darwin": "macos",
        "Windows": "windows",
    }.get(platform.system(), platform.system().lower())


def main() -> int:
    dist = ROOT / "dist"
    version = _project_version(ROOT)
    tag = f"drawclock-{version}-{_platform_tag()}"
    staging_root = dist / ".release-staging"
    bundle_dir = staging_root / tag
    if staging_root.exists():
        shutil.rmtree(staging_root)
    bundle_dir.mkdir(parents=True)

    copied_binary = False
    for name in BINARY_NAMES:
        for candidate in (dist / name, dist / f"{name}.exe"):
            if candidate.is_file():
                shutil.copy2(candidate, bundle_dir / candidate.name)
                copied_binary = True

    if not copied_binary:
        print("错误: dist 中未找到可执行文件。", file=sys.stderr)
        return 1

    for rel in RELEASE_PATHS:
        src = ROOT / rel
        if not src.exists():
            print(f"错误: 未找到 {src}", file=sys.stderr)
            return 1
        dest = bundle_dir / rel
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    archive_base = dist / tag
    fmt = "zip" if platform.system() == "Windows" else "gztar"
    for old in (dist / f"{tag}.zip", dist / f"{tag}.tar.gz"):
        if old.is_file():
            old.unlink()

    shutil.make_archive(str(archive_base), fmt, staging_root, tag)
    shutil.rmtree(staging_root)

    suffix = ".zip" if fmt == "zip" else ".tar.gz"
    print(f"完成: {archive_base}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
