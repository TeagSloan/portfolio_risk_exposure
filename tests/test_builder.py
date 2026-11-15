"""Tests for engine/builder.py (Way 2). The exposure table and Way 1 re-check are faked."""

import json

import pandas as pd
import pytest

from engine import builder, screen

H, M, L, LL, ND = "High", "Moderate", "Limited", "Limited (lower confidence)", "Not determined"

THEMES = {k: {"key": k, "name": n, "references": {"High": [{"ticker": "A1"}], "Moderate": []}}
          for k, n in (("ai", "AI"), ("oil", "Oil"), ("gold", "Gold"))}

# ticker -> (country, market cap $bn, {theme: (tier, business_linked, strength)})
ROWS = {
    "A1": ("US", 900, {"ai": (H, True, 0.9), "oil": (L, False, 0.0), "gold": (L, False, 0.0)}),
    "A2": ("US", 800, {"ai": (M, True, 0.3), "oil": (LL, False, 0.0), "gold": (ND, False, 0.1)}),
    "A3": ("US", 700, {"ai": (H, False, 1.5), "oil": (L, False, 0.0), "gold": (L, False, 0.0)}),  # price link only
    "A4": ("US", 600, {"ai": (H, True, 0.5), "oil": (ND, False, 0.2), "gold": (L, False, 0.0)}),  # oil can't tell: passes
    "A5": ("US", 500, {"ai": (H, True, 0.8), "oil": (M, False, 0.4), "gold": (L, False, 0.0)}),   # flagged on oil: out
    "A6": ("TW", 400, {"ai": (H, True, 0.7), "oil": (L, False, 0.0), "gold": (L, False, 0.0)}),   # international
    "A7": ("US", 300, {"ai": (M, True, 0.2), "oil": (L, False, 0.0), "gold": (H, True, 0.9)}),
    "A8": ("US", 200, {"ai": (H, True, 0.6), "oil": (ND, True, 0.1), "gold": (L, False, 0.0)}),   # oil business: out
    "A9": ("US", 100, {"ai": (M, True, 0.4), "oil": (L, False, 0.0), "gold": (L, False, 0.0)}),
    "O1": ("US", 50, {"ai": (L, False, 0.0), "oil": (H, True, 1.0), "gold": (L, False, 0.0)}),
    "G1": ("CA", 40, {"ai": (ND, False, 0.0), "oil": (L, False, 0.0), "gold": (H, True, 1.2)}),
    "G2": ("US", 30, {"ai": (L, False, 0.0), "oil": (ND, False, 0.0), "gold": (M, True, 0.5)}),
}


REFS = {"ai": {"A9"}}  # A9 is a Tier 1 AI reference: it ranks first for want AI


def table():
    rows = []
    for t, (c, cap, d) in ROWS.items():
        for k, (tier, bl, st) in d.items():
            rows.append({"ticker": t, "theme": k, "tier": tier, "business_linked": bl, "country": c,
                         "name": f"{t} Inc", "industry": "Ind", "market_cap": cap * 1e9, "strength": st,
                         "strength_t": st * 10, "reference": t in REFS.get(k, ()),
                         "method": "regression", "sentence": "x", "n_obs": 498, "r_squared": 0.5, "p_threshold": 0.01,
                         "controls_used": "SPY,TLT", "High_sum": 0.4 if tier != ND else None, "High_se": 0.1,
                         "High_p": 0.001, "High_upper": 0.56, "High_eligible": True})
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(builder, "load_all", lambda: THEMES)
    monkeypatch.setattr(builder, "load_table", table)
    monkeypatch.setattr(screen, "industry_of", lambda t: None)
    monkeypatch.setattr(screen, "load_theme", lambda k: THEMES[k])
    monkeypatch.setattr(screen, "_screen_one", lambda t, th, s, e: {
        "ticker": t, "theme": th["name"], "tier": ROWS[t][2][th["key"]][0], "method": "fake", "sentence": "x"})


def tickers(out):
    return [h["ticker"] for h in out["holdings"]]


def test_avoid_rule_passes_not_determined_but_not_flagged_or_business_linked():
    out = builder.build({"ai": "want", "oil": "avoid"})
    # A3: no AI business. A5: flagged Moderate on oil. A8: in the oil business (safety net). A4 (oil ND) passes.
    assert set(tickers(out)) == {"A1", "A2", "A4", "A6", "A7", "A9", "CASH"}
    steps = [(f["step"], f["left"]) for f in out["funnel"]]
    assert steps == [("Universe (scored stocks)", 12), ("Want AI: High or Moderate", 9), ("Want AI: business-linked", 8),
                     ("Avoid Oil: not flagged High or Moderate", 7),
                     ("Avoid Oil: not in the Oil business (safety net)", 6)]
    a4 = next(h for h in out["holdings"] if h["ticker"] == "A4")
    assert a4["avoid_tiers"] == {"Oil": ND} and a4["want_tiers"] == {"AI": H} and a4["name"] == "A4 Inc"
    assert a4["tiers"] == {"AI": H, "Oil": ND} and a4["labels"] == ["Oil: the data can't tell"]  # for app.py
    assert out["verification"]["all_pass"]


def test_ranked_references_first_then_high_then_t_stat(monkeypatch):
    out = builder.build({"ai": "want", "oil": "avoid"})
    # A9 is a Tier 1 reference (first, even though Moderate); then High by t (A1 9, A6 7, A4 5); then Moderate (A2 3, A7 2)
    assert tickers(out)[:6] == ["A9", "A1", "A6", "A4", "A2", "A7"]
    monkeypatch.setattr(builder, "TOP_N", 3)
    out = builder.build({"ai": "want", "oil": "avoid"})
    assert tickers(out) == ["A9", "A1", "A6", "CASH"]
    assert out["funnel"][-1]["left"] == 3 and out["funnel"][-1]["step"].endswith("top 3")
    assert out["survivors"] == 6 and out["holdings"][1]["t_stat"] == {"AI": 9.0}
    assert out["holdings"][0]["reference"] == {"AI": True}


def test_several_want_themes_add_percentile_ranks():
    out = builder.build({"ai": "want", "gold": "want"})
    assert tickers(out) == ["A7", "CASH"]  # the only stock that's AI and Gold and business-linked to both
    out = builder.build({"gold": "want"})
    assert tickers(out)[:3] == ["G1", "A7", "G2"]


def test_avoid_only_ranks_by_market_cap():
    out = builder.build({"oil": "avoid"})
    assert out["ranked_by"] == "market cap (no want theme)"
    assert tickers(out)[:3] == ["A1", "A2", "A3"]


def test_region_filter():
    us = builder.build({"ai": "want", "oil": "avoid"}, region="us")
    assert "A6" not in tickers(us) and us["funnel"][1] == {"step": "Region: US only", "left": 10}
    intl = builder.build({"gold": "want"}, region="intl")
    assert {h["ticker"]: h["weight_pct"] for h in intl["holdings"]} == {"G1": 15.0, "CASH": 85.0}


def test_dont_care_adds_no_rule_but_is_listed():
    a = builder.build({"ai": "want", "oil": "avoid"})
    b = builder.build({"ai": "want", "oil": "avoid", "gold": "dont care"})
    assert tickers(a) == tickers(b)
    assert b["funnel"][-1]["step"] == "Don't care: Gold (no rule)"


def test_small_basket_warning_and_nothing_qualifies():
    out = builder.build({"ai": "want", "gold": "want"})
    assert any("Only 1 holding" in x for x in out["warnings"])
    none = builder.build({"oil": "want", "gold": "want"})
    assert none["holdings"] == [] and none["verification"] is None and none["cash_pct"] == 0.0


def test_prescreen_keeps_run_screen_shape_for_chain_publish():
    p = builder.prescreen()
    r = p["A1"]["ai"]
    assert r["tier"] == H and r["controls"] == ["SPY", "TLT"] and r["n_obs"] == 498
    assert r["groups"]["High"] == {"names": ["A1"], "beta_sum": 0.4, "se": 0.1, "p_one_sided": 0.001,
                                   "upper_95": 0.56, "eligible": True}
    assert p["G1"]["ai"]["groups"] == {}


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
    assert "Funnel:" in out and "Basket (6 holdings" in out and "All goals met." in out and "avoid: Oil Not determined" in out
    saved = json.loads((tmp_path / "results" / "build_latest.json").read_text())
    assert saved["preferences"] == {"gold": "dont_care", "ai": "want", "oil": "avoid"}
    assert "points" not in saved["holdings"][0] and "avoid_tiers" in saved["holdings"][0]
    assert builder.main(["--want", "gold", "--region", "intl", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["cash_pct"] == 85.0
    assert builder.main(["--want", "ai", "--avoid", "ai"]) == 2
    assert builder.main([]) == 2
