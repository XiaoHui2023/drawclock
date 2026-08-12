from __future__ import annotations

from pathlib import Path

import layout_preview


def test_browser_path_honors_explicit_chrome_path(
    tmp_path: Path, monkeypatch,
) -> None:
    browser = tmp_path / "custom-browser"
    browser.touch()
    monkeypatch.setenv("CHROME_PATH", str(browser))
    monkeypatch.setattr(layout_preview.shutil, "which", lambda _name: None)

    assert layout_preview._browser_path() == browser


def test_browser_path_discovers_common_linux_chromium_name(
    tmp_path: Path, monkeypatch,
) -> None:
    browser = tmp_path / "chromium"
    browser.touch()
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(layout_preview, "_runtime_roots", lambda: ())
    monkeypatch.setattr(
        layout_preview.shutil,
        "which",
        lambda name: str(browser) if name == "chromium" else None,
    )

    assert layout_preview._browser_path() == browser


def test_browser_path_discovers_bundled_headless_shell(
    tmp_path: Path, monkeypatch,
) -> None:
    executable = (
        "chrome-headless-shell.exe" if layout_preview.os.name == "nt"
        else "chrome-headless-shell"
    )
    browser = tmp_path / "headless-shell" / executable
    browser.parent.mkdir()
    browser.touch()
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(layout_preview, "_runtime_roots", lambda: (tmp_path,))
    monkeypatch.setattr(layout_preview.shutil, "which", lambda _name: None)

    assert layout_preview._browser_path() == browser


def test_runtime_roots_use_original_staticx_program_path(
    tmp_path: Path, monkeypatch,
) -> None:
    installed = tmp_path / "installed" / "drawclock"
    extracted = tmp_path / "staticx-bundle" / "drawclock"
    monkeypatch.setenv("STATICX_PROG_PATH", str(installed))
    monkeypatch.setattr(layout_preview.sys, "frozen", True, raising=False)
    monkeypatch.setattr(layout_preview.sys, "executable", str(extracted))

    assert layout_preview._runtime_roots()[0] == installed.parent / "runtime"
