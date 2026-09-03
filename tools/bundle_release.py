"""Assemble release archive: dist binaries plus docs and static assets."""

from __future__ import annotations

import hashlib
import json
import pathlib
import platform
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

BINARY_NAMES = ("drawclock",)

# 运行时资源、绘图专档、源码部署材料与分层质量样例。
RELEASE_PATHS = (
    "README.md",
    "draw.md",
    "pyproject.toml",
    "source-deploy.md",
    "licenses",
    "drawio-lib",
    "skills",
    "example/draw.json",
    "example/auto-layout/01-linear.json",
    "example/auto-layout/05-dense-cross-root.json",
    "example/auto-layout/08-stress-512-clocks.json",
    "example/auto-layout/19-dispersed-root-fanout.json",
    "example/auto-layout/20-asymmetric-merge-route-bulge.json",
    "example/auto-layout/21-layout-column-preference.json",
    "example/auto-layout/22-terminal-frequency-table.json",
    "example/auto-layout/23-middle-column-low-use-sources.json",
    "example/auto-layout/24-single-source-rendering-alias.json",
    "example/auto-layout/25-mixed-root-port-order-torture.json",
)

SOURCE_PATHS = (
    ("src", "src"),
)

RUNTIME_PATH = ".runtime"


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    for rel, dest_rel in SOURCE_PATHS:
        src = ROOT / rel
        if not src.exists():
            print(f"错误: 未找到 {src}", file=sys.stderr)
            return 1
        dest = bundle_dir / dest_rel
        if src.is_dir():
            shutil.copytree(
                src,
                dest,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "*.pyo", "*.egg-info"
                ),
            )
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    runtime = ROOT / RUNTIME_PATH
    if not (runtime / "runtime-manifest.json").is_file():
        print("错误: 发布运行时未准备完成。", file=sys.stderr)
        return 1
    shutil.copytree(runtime, bundle_dir / "runtime")

    manifest_paths = [
        path
        for base in (
            bundle_dir / "src", bundle_dir / "skills", bundle_dir / "licenses",
        )
        for path in base.rglob("*")
        if path.is_file()
    ]
    manifest_paths.extend(
        path
        for path in (bundle_dir / "drawio-lib" / "drawclock").rglob("*.xml")
        if path.is_file()
    )
    manifest_paths.extend(
        path for path in (bundle_dir / "example").rglob("*.json")
        if path.is_file()
    )
    manifest_paths.append(bundle_dir / "runtime/runtime-manifest.json")
    source_manifest = {
        "schema": 1,
        "files": {
            path.relative_to(bundle_dir).as_posix(): _sha256(path)
            for path in sorted(manifest_paths)
        },
    }
    (bundle_dir / "source-manifest.json").write_text(
        json.dumps(source_manifest, indent=2) + "\n", encoding="utf-8"
    )

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
