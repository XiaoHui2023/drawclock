from __future__ import annotations

import pytest

from css_color import CSS_NAMED_COLORS, parse_css_color


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("red", "#ff0000"),
        ("RebeccaPurple", "#663399"),
        (" transparent ", "#00000000"),
        ("#0f8", "#00ff88"),
        ("#0f8c", "#00ff88cc"),
        ("#102030", "#102030"),
        ("#10203040", "#10203040"),
        ("rgb(255, 0, 127)", "#ff007f"),
        ("rgba(100%, 0%, 50%, 25%)", "#ff008040"),
        ("rgb(300 -20 127.5 / .5)", "#ff008080"),
        ("hsl(0, 100%, 50%)", "#ff0000"),
        ("hsl(.5turn 100% 50% / 50%)", "#00ffff80"),
        ("hsla(3.141592653589793rad,100%,50%,.25)", "#00ffff40"),
        ("hwb(120 0% 0% / 20%)", "#00ff0033"),
        ("hwb(0 80% 80%)", "#808080"),
    ],
)
def test_parse_css_color_normalizes_portable_syntax(source: str, expected: str) -> None:
    assert parse_css_color(source) == expected


def test_named_color_table_covers_the_css_named_set() -> None:
    assert len(CSS_NAMED_COLORS) == 148


@pytest.mark.parametrize(
    "source",
    [
        "", "#12", "#xyz", "rgb()", "rgb(1 2)", "rgb(1,2,3 / .5)",
        "hsl(0 50 50)", "hwb(0 0 0)", "hwb(0, 0%, 0%)",
        "url(javascript:alert(1))",
        "var(--brand)", "currentColor", "color(display-p3 1 0 0)",
        "lab(50% 0 0)", "rgb(calc(1) 2 3)", "rgb(nan 0 0)",
    ],
)
def test_parse_css_color_rejects_dynamic_unsafe_or_unsupported_values(source: str) -> None:
    with pytest.raises(ValueError):
        parse_css_color(source)


@pytest.mark.parametrize("source", [None, 1, True, [], {}])
def test_parse_css_color_requires_a_string(source: object) -> None:
    with pytest.raises(ValueError, match="颜色必须是字符串"):
        parse_css_color(source)  # type: ignore[arg-type]
