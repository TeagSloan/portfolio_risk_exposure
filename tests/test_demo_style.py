"""The demo dashboard's stylesheet must survive Streamlit's HTML sanitizer, and use the product's three fonts."""

import re

from demo import style


def _inner_css() -> str:
    return style.CSS.split("<style>", 1)[1].rsplit("</style>", 1)[0]


def test_css_has_no_raw_tags():
    # Streamlit drops the WHOLE <style> block if its text contains anything that looks like a tag ("<svg", "<i...").
    assert re.findall(r"<[/\w]", _inner_css()) == []


def test_fonts_are_the_scoreboard_set():
    css = style.CSS
    for family in ("Barlow+Condensed", "Inter", "JetBrains+Mono"):
        assert family in style.FONTS
    assert "display=swap" in style.FONTS
    for old in ("Fraunces", "Manrope"):
        assert old not in css and old not in style.FONTS


def test_signed_tile_values_are_mint_or_coral():
    html = style.tiles([("Return", "+4%", ""), ("Bad year", "−17%", ""), ("Chance", "8%", "")])
    assert f"color:{style.GAIN}" in html and f"color:{style.LOSS}" in html and f"color:{style.TEXT}" in html
