"""Download pinned runtime executables used by the self-contained release bundle."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / ".runtime"
CACHE_ROOT = ROOT / ".runtime-cache"
CHROME_VERSION = "151.0.7922.138"
NODE_VERSION = "16.20.2"


def _platform_key() -> str:
    machine = platform.machine().lower()
    system = platform.system()
    if system == "Windows" and machine in {"amd64", "x86_64"}:
        return "win64"
    if system == "Linux" and machine in {"amd64", "x86_64"}:
        return "linux64"
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return "mac-arm64"
    if system == "Darwin" and machine in {"amd64", "x86_64"}:
        return "mac-x64"
    raise SystemExit(f"unsupported release runtime platform: {system} {machine}")


def _asset_urls(key: str) -> tuple[str, str]:
    chrome = (
        "https://storage.googleapis.com/chrome-for-testing-public/"
        f"{CHROME_VERSION}/{key}/chrome-headless-shell-{key}.zip"
    )
    node_platform = {
        "win64": "win-x64.zip",
        "linux64": "linux-x64.tar.xz",
        "mac-arm64": "darwin-arm64.tar.gz",
        "mac-x64": "darwin-x64.tar.gz",
    }[key]
    node = f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-{node_platform}"
    return chrome, node


def _download(url: str) -> tuple[Path, str, float]:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    output = CACHE_ROOT / url.rsplit("/", 1)[-1]
    started = time.perf_counter()
    for attempt in range(1, 4):
        try:
            if not output.is_file() or output.stat().st_size == 0:
                request = urllib.request.Request(url, headers={"User-Agent": "drawclock-pack"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    with output.open("wb") as stream:
                        shutil.copyfileobj(response, stream)
            digest_hash = hashlib.sha256()
            with output.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest_hash.update(block)
            digest = digest_hash.hexdigest()
            return output, digest, (time.perf_counter() - started) * 1000
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            output.unlink(missing_ok=True)
            if attempt == 3:
                raise SystemExit(f"failed to download {url}: {exc}") from exc
            time.sleep(attempt * 2)
    raise AssertionError("unreachable")


def _safe_extract_tar(bundle: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in bundle.getmembers():
        target = (destination / member.name).resolve()
        if target != destination and destination not in target.parents:
            raise SystemExit(f"unsafe path in runtime archive: {member.name}")
    bundle.extractall(destination)


def _extract(archive: Path, destination: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="drawclock-runtime-") as temp:
        temp_root = Path(temp)
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(temp_root)
        else:
            with tarfile.open(archive, "r:*") as bundle:
                _safe_extract_tar(bundle, temp_root)
        entries = list(temp_root.iterdir())
        source = entries[0] if len(entries) == 1 and entries[0].is_dir() else temp_root
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)


def _executables(key: str) -> tuple[Path, Path]:
    chrome_name = "chrome-headless-shell.exe" if key == "win64" else "chrome-headless-shell"
    node_name = "node.exe" if key == "win64" else "bin/node"
    return RUNTIME_ROOT / "headless-shell" / chrome_name, RUNTIME_ROOT / "node" / node_name


def _copy_elk_runtime() -> None:
    source = ROOT / "node_modules" / "elkjs"
    if not (source / "lib" / "elk.bundled.js").is_file():
        raise SystemExit("node_modules/elkjs is missing; run npm install before packaging")
    target = RUNTIME_ROOT / "elk"
    if target.exists():
        shutil.rmtree(target)
    (target / "node_modules" / "elkjs" / "lib").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "elk_layout.mjs", target / "elk_layout.mjs")
    for name in ("package.json", "LICENSE.md"):
        shutil.copy2(source / name, target / "node_modules" / "elkjs" / name)
    shutil.copy2(
        source / "lib" / "elk.bundled.js",
        target / "node_modules" / "elkjs" / "lib" / "elk.bundled.js",
    )


def main() -> int:
    key = _platform_key()
    chrome_url, node_url = _asset_urls(key)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    downloads = []
    for name, url in (("headless-shell", chrome_url), ("node", node_url)):
        archive, digest, duration_ms = _download(url)
        _extract(archive, RUNTIME_ROOT / name)
        downloads.append(
            {"name": name, "url": url, "sha256": digest, "duration_ms": round(duration_ms, 3)}
        )
    _copy_elk_runtime()
    chrome, node = _executables(key)
    if not chrome.is_file() or not node.is_file():
        raise SystemExit("release runtime archive did not contain expected executables")
    if os.name != "nt":
        chrome.chmod(chrome.stat().st_mode | 0o111)
        node.chmod(node.stat().st_mode | 0o111)
    chrome_version = subprocess.run(
        [str(chrome), "--version"], check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()
    node_version = subprocess.run(
        [str(node), "--version"], check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()
    manifest = {
        "platform": key,
        "chrome_version": chrome_version,
        "node_version": node_version,
        "elkjs_version": "0.11.1",
        "downloads": downloads,
    }
    (RUNTIME_ROOT / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
