"""Tests for engine/builder.py (Way 2). The exposure table and Way 1 re-check are faked."""

import json

import pandas as pd
import pytest

from engine import builder, screen

H, M, L, LL, ND = "High", "Moderate", "Limited", "Limited (lower confidence)", "Not determined"

THEMES = {k: {"key": k, "name": n, "references": {"High": [{"ticker": "A1"}], "Moderate": []}}
          for k, n in (("ai", "AI"), ("oil", "Oil"), ("gold", "Gold"))}

# ticker -> (country, {theme: (tier, business_linked)})
ROWS = {
    "A1": ("US", {"ai": (H, True), "oil": (L, False), "gold": (L, False)}),
    "A2": ("US", {"ai": (M, True), "oil": (LL, False), "gold": (ND, False)}),
    "A3": ("US", {"ai": (H, False), "oil": (L, False), "gold": (L, False)}),   # price link only
    "A4": ("US", {"ai": (H, True), "oil": (ND, False), "gold": (L, False)}),  # oil can't tell -> out
    "A5": ("US", {"ai": (H, True), "oil": (M, False), "gold": (L, False)}),
    "A6": ("TW", {"ai": (H, True), "oil": (L, False), "gold": (L, False)}),   # international
    "A7": ("US", {"ai": (M, True), "oil": (L, False), "gold": (H, True)}),
    "A8": ("US", {"ai": (H, True), "oil": (L, False), "gold": (L, False)}),
    "A9": ("US", {"ai": (M, True), "oil": (L, False), "gold": (L, False)}),
    "O1": ("US", {"ai": (L, False), "oil": (H, True), "gold": (L, False)}),
    "G1": ("CA", {"ai": (ND, False), "oil": (L, False), "gold": (H, True)}),
}


def table():
    rows = []
    for t, (c, d) in ROWS.items():
        for k, (tier, bl) in d.items():
            reg = tier != ND
            rows.append({"ticker": t, "theme": k, "tier": tier, "business_linked": bl, "country": c,
                         "method": "regression", "sentence": "x", "n_obs": 498, "r_squared": 0.5, "p_threshold": 0.01,
                         "controls_used": "SPY,TLT", "High_sum": 0.4 if reg else None, "High_se": 0.1, "High_p": 0.001,
                         "High_upper": 0.56, "High_eligible": True})
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(builder, "load_all", lambda: THEMES)
    monkeypatch.setattr(builder, "load_table", table)
    monkeypatch.setattr(screen, "load_theme", lambda k: {"key": k, "name": THEMES[k]["name"]})
    monkeypatch.setattr(screen, "_screen_one", lambda t, th, s, e: {
        "ticker": t, "theme": th["name"], "tier": ROWS[t][1][th["key"]][0], "method": "fake", "sentence": "x"})


def w(out):
    return {h["ticker"]: h["weight_pct"] for h in out["holdings"]}


def test_want_ai_avoid_oil_funnel_and_basket():
    out = builder.build({"ai": "want", "oil": "avoid"})
    # 6 equal picks would be 16.7% each, over the 15% cap: each is held at 15% and 10% stays in cash.
    assert w(out) == {"A1": 15.0, "A2": 15.0, "A6": 15.0, "A7": 15.0, "A8": 15.0, "A9": 15.0, "CASH": 10.0}
    assert [f["left"] for f in out["funnel"]] == [11, 9, 8, 6]
    assert out["funnel"][2]["step"] == "Want AI: business-linked"  # A3 dropped here
    a2 = next(h for h in out["holdings"] if h["ticker"] == "A2")
    assert a2["labels"] == ["Oil: lower confidence"]
    assert out["verification"]["all_pass"]


def test_region_filter():
    us = builder.build({"ai": "want", "oil": "avoid"}, region="us")
    assert "A6" not in w(us) and us["funnel"][1] == {"step": "Region: US only", "left": 9}
    intl = builder.build({"gold": "want"}, region="intl")
    assert w(intl) == {"G1": 15.0, "CASH": 85.0}


def test_dont_care_adds_no_rule_but_is_listed():
    a = builder.build({"ai": "want", "oil": "avoid"})
    b = builder.build({"ai": "want", "oil": "avoid", "gold": "dont care"})
    assert w(a) == w(b)
    assert b["funnel"][-1]["step"] == "Don't care: Gold (no rule)"
    assert "Gold" not in b["holdings"][0]["tiers"]


def test_small_basket_warning_and_cash():
    out = builder.build({"ai": "want", "gold": "want"})
    assert w(out) == {"A7": 15.0, "CASH": 85.0}
    assert any("Only 1 holding" in x for x in out["warnings"])


def test_nothing_qualifies():
    out = builder.build({"oil": "want", "gold": "want"})
    assert out["holdings"] == [] and out["verification"] is None and out["cash_pct"] == 0.0


def test_prescreen_keeps_run_screen_shape_for_chain_publish():
    p = builder.prescreen()
    r = p["A1"]["ai"]
    assert r["tier"] == H and r["controls"] == ["SPY", "TLT"] and r["n_obs"] == 498
    assert r["groups"]["High"] == {"names": ["A1"], "beta_sum": 0.4, "se": 0.1, "p_one_sided": 0.001,
                                   "upper_95": 0.56, "eligible": True}
    assert p["G1"]["ai"]["groups"] == {}  # Not determined row without stats


def test_cap_and_rescale_math():
    weights, cash = builder.cap_and_rescale({"a": 10, "b": 1, "c": 1, "d": 1, "e": 1, "f": 1, "g": 1, "h": 1})
    assert weights["a"] == pytest.approx(15) and cash == 0
    assert all(weights[t] == pytest.approx(85 / 7) for t in "bcdefgh")
    assert builder.cap_and_rescale({}) == ({}, 100.0)
    with pytest.raises(ValueError):
        builder.cap_and_rescale({"a": 0})


@pytest.mark.parametrize("prefs, region, msg", [
    ({}, "all", "at least one"), ({"gold": "dont_care"}, "all", "at least one"),
    ({"nope": "want"}, "all", "No theme called"), ({"ai": "love"}, "all", "'want', 'avoid' or 'dont_care'"),
    ({"ai": "want"}, "mars", "Region must be"),
])
def test_bad_preferences(prefs, region, msg):
    with pytest.raises(builder.BuildError, match=msg):
        builder.build(prefs, region=region)


def test_cli(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    assert builder.main(["--want", "ai", "--avoid", "oil", "--dont-care", "gold"]) == 0
    out = capsys.readouterr().out
    assert "Funnel:" in out and "Basket (6 holdings)" in out and "All goals met." in out
    saved = json.loads((tmp_path / "results" / "build_latest.json").read_text())
    assert saved["preferences"] == {"gold": "dont_care", "ai": "want", "oil": "avoid"}
    assert builder.main(["--want", "gold", "--region", "intl", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["cash_pct"] == 85.0
    assert builder.main(["--want", "ai", "--avoid", "ai"]) == 2
    assert "listed twice" in capsys.readouterr().err
    assert builder.main([]) == 2
