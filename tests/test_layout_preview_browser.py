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
    monkeypatch.setattr(
        layout_preview.shutil,
        "which",
        lambda name: str(browser) if name == "chromium" else None,
    )

    assert layout_preview._browser_path() == browser
