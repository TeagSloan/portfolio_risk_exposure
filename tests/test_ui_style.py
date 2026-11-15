"""Tests for engine/ui_style.py: the HTML it builds for the fund header and the rejection panel."""

import plotly.graph_objects as go

from engine import ui_style

NAMES = {"ai": "AI", "oil": "Oil"}


def test_fund_header_shows_name_symbol_and_rules_wants_first():
    html = ui_style.fund_header_html("AI ex-Oil Fund", "AIXO", {"oil": "avoid", "ai": "want"}, NAMES)
    assert "AI ex-Oil Fund" in html and "$AIXO" in html
    assert html.index("Want AI") < html.index("Avoid Oil")
    assert "tf-rule-want" in html and "tf-rule-avoid" in html
    assert "Not launched yet" in html


def test_fund_header_skips_dont_care_and_unknown_theme_names_fall_back_to_the_key():
    html = ui_style.fund_header_html("F", "F", {"gold": "dont_care", "cyber": "want"}, NAMES)
    assert "Want cyber" in html and "gold" not in html.lower()


def test_fund_header_once_launched():
    fund = {"network": "Monad testnet", "address": "0xAbC0000000000000000000000000000000000001"}
    html = ui_style.fund_header_html("AI ex-Oil Fund", "AIXO", {"ai": "want"}, NAMES, fund,
                                     "https://testnet.monadexplorer.com/address/0xAbC")
    assert "Live on Monad testnet" in html and fund["address"] in html
    assert 'href="https://testnet.monadexplorer.com/address/0xAbC"' in html
    assert "Not launched yet" not in html
    # A local test chain has no explorer, so no link is drawn.
    assert "<a " not in ui_style.fund_header_html("F", "F", {"ai": "want"}, NAMES, fund, None)


def test_text_typed_by_the_user_is_escaped():
    html = ui_style.fund_header_html("<script>x</script>", "A&B", {"ai": "want"}, {"ai": "<b>AI</b>"})
    assert "<script>" not in html and "&lt;script&gt;" in html and "A&amp;B" in html and "<b>AI</b>" not in html
    panel = ui_style.rejection_html("<img>", ["Mandate: <i>Oil</i> exposure too high"], on_chain=True)
    assert "<img>" not in panel and "<i>" not in panel


def test_rejection_panel():
    on_chain = ui_style.rejection_html("XOM", ["Mandate: Oil exposure too high"], on_chain=True)
    assert "Rejected: XOM can't be added" in on_chain
    assert "Mandate: Oil exposure too high" in on_chain
    assert "Refused by the fund contract on Monad" in on_chain and 'role="alert"' in on_chain

    preview = ui_style.rejection_html("XOM", ["one", "", "two"], on_chain=False)
    assert "checked off-chain" in preview and preview.count("tf-reject-reason") == 2


def test_chart_sets_the_typeface_and_passes_none_through():
    fig = ui_style.chart(go.Figure())
    assert "Schibsted Grotesk" in fig.layout.font.family and fig.layout.font.color == ui_style.INK
    assert ui_style.chart(None) is None
