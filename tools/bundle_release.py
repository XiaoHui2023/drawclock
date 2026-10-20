"""Assemble release archive: binaries, public assets, and Linux source."""

from __future__ import annotations

import pathlib
import platform
import re
import shutil
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

BINARY_NAMES = ("drawclock",)

# 默认附件只保留最终用户运行所需文件。源路径与发布路径显式分离，
# 让仓库内部结构不泄漏为用户接口。
RELEASE_FILES = (
    ("README.md", "doc/README.md"),
    ("draw.md", "doc/draw.md"),
    ("example/draw.json", "example/draw.json"),
    ("example/README.md", "example/README.md"),
    ("example/auto-layout/README.md", "example/auto-layout/README.md"),
)
LIBRARY_SOURCE = "drawio-lib/drawclock"
LIBRARY_DESTINATION = "libraries"


def _product_source_files(root: pathlib.Path) -> list[pathlib.Path]:
    source_root = root / "src"
    return [
        path
        for path in sorted(source_root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
        and path.suffix.lower() == ".py"
    ]


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

    release_files = [
        *RELEASE_FILES,
        *(
            (str(path.relative_to(ROOT)), str(path.relative_to(ROOT)))
            for path in sorted((ROOT / "example" / "auto-layout").glob("*.json"))
        ),
    ]
    script_suffix = ".bat" if platform.system() == "Windows" else ".sh"
    platform_scripts = sorted(
        (ROOT / "example" / "run-example").glob(f"*{script_suffix}")
    )
    if not platform_scripts:
        print(
            f"错误: example/run-example 中没有 {script_suffix} 演示脚本。",
            file=sys.stderr,
        )
        return 1
    release_files.extend(
        (str(path.relative_to(ROOT)), str(path.relative_to(ROOT)))
        for path in platform_scripts
    )

    for source_rel, destination_rel in release_files:
        src = ROOT / source_rel
        if not src.exists():
            print(f"错误: 未找到 {src}", file=sys.stderr)
            return 1
        dest = bundle_dir / destination_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if platform.system() == "Linux" and dest.suffix == ".sh":
            dest.chmod(dest.stat().st_mode | 0o111)
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

    if platform.system() == "Linux":
        source_files = _product_source_files(ROOT)
        if not source_files:
            print("错误: src 中没有产品源码。", file=sys.stderr)
            return 1
        for src in source_files:
            destination = bundle_dir / src.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, destination)

    archive_base = dist / tag
    is_windows = platform.system() == "Windows"
    for old in (dist / f"{tag}.zip", dist / f"{tag}.tar.gz"):
        if old.is_file():
            old.unlink()

    if is_windows:
        shutil.make_archive(str(archive_base), "zip", staging_root, tag)
    else:
        def executable_release_files(info: tarfile.TarInfo) -> tarfile.TarInfo:
            if info.isfile() and (
                info.name == f"{tag}/drawclock" or info.name.endswith(".sh")
            ):
                info.mode |= 0o111
            return info

        with tarfile.open(f"{archive_base}.tar.gz", "w:gz") as archive:
            archive.add(bundle_dir, arcname=tag, filter=executable_release_files)
    shutil.rmtree(staging_root)

    suffix = ".zip" if is_windows else ".tar.gz"
    print(f"完成: {archive_base}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
