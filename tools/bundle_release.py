"""Assemble release archive: dist binaries plus docs and static assets."""

from __future__ import annotations

import pathlib
import platform
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

BINARY_NAMES = ("drawclock",)

# 默认附件只保留最终用户运行所需文件。源路径与发布路径显式分离，
# 让仓库内部结构不泄漏为用户接口。
RELEASE_FILES = (
    ("README.md", "doc/README.md"),
    ("draw.md", "doc/draw.md"),
    ("licenses/NotoSansCJK-OFL-1.1.txt", "doc/licenses/NotoSansCJK-OFL-1.1.txt"),
    ("example/draw.json", "example/draw.json"),
    (
        "example/auto-layout/33-description-colors.json",
        "example/auto-layout/33-description-colors.json",
    ),
)
LIBRARY_SOURCE = "drawio-lib/drawclock"
LIBRARY_DESTINATION = "libraries"


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

    for source_rel, destination_rel in RELEASE_FILES:
        src = ROOT / source_rel
        if not src.exists():
            print(f"错误: 未找到 {src}", file=sys.stderr)
            return 1
        dest = bundle_dir / destination_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if dest.suffix.lower() == ".md":
            text = dest.read_text(encoding="utf-8")
            text = text.replace("drawio-lib/drawclock", "libraries")
            text = text.replace("drawio-lib\\drawclock", "libraries")
            dest.write_text(text, encoding="utf-8")

    library_source = ROOT / LIBRARY_SOURCE
    if not library_source.is_dir():
        print(f"错误: 未找到 {library_source}", file=sys.stderr)
        return 1
    library_destination = bundle_dir / LIBRARY_DESTINATION
    library_destination.mkdir(parents=True)
    library_files = sorted(library_source.glob("*.xml"))
    if not library_files:
        print(f"错误: {library_source} 中没有 XML 器件库", file=sys.stderr)
        return 1
    for src in library_files:
        shutil.copy2(src, library_destination / src.name)

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
