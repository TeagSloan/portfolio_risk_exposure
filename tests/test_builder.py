"""Tests for engine/builder.py. Themes and every ticker's tier are faked, so the right basket is known."""

import json

import pytest

from engine import builder, screen

H, M, L, LL, ND = "High", "Moderate", "Limited", "Limited (lower confidence)", "Not determined"


def theme(key, name, refs):
    return {"key": key, "name": name, "plain": name, "controls": ["SPY", "TLT", "VALUE"],
            "references": {"High": [{"ticker": refs[0]}], "Moderate": [{"ticker": refs[1]}]},
            "control": {"ticker": "CTRL"}, "direct_classification": []}


THEMES = {"ai": theme("ai", "AI", ["A1", "A2"]), "oil": theme("oil", "Oil", ["O1", "O2"]),
          "cyber": theme("cyber", "Cyber", ["C1", "C2"])}

# ticker -> (ai, oil, cyber)
TABLE = {
    "A1": (H, L, L), "A2": (M, L, LL), "A3": (H, LL, H), "A4": (M, ND, L), "A5": (H, M, L),
    "A6": (M, L, M), "A7": (H, L, L), "A8": (M, L, ND), "O1": (L, H, L), "O2": (LL, M, L),
    "C1": (L, L, H), "C2": (ND, L, M), "SMH": (H, L, L), "KO": (L, L, L), "XOM": (LL, M, ND),
}


@pytest.fixture(autouse=True)
def fakes(monkeypatch, tmp_path):
    def screen_one(ticker, th, start, end):
        tier = TABLE[ticker][list(THEMES).index(th["key"])] if ticker in TABLE else ND
        return {"ticker": ticker, "theme": th["name"], "tier": tier, "method": "fake", "sentence": f"{ticker} {tier}"}

    monkeypatch.setattr(screen, "_screen_one", screen_one)
    monkeypatch.setattr(screen, "load_theme", lambda k: THEMES[k])
    monkeypatch.setattr(screen, "load_all", lambda: THEMES)
    monkeypatch.setattr(builder, "load_all", lambda: THEMES)
    monkeypatch.setattr(builder, "universe", lambda themes: sorted(TABLE))
    monkeypatch.setattr(builder, "CACHE_PATH", tmp_path / "universe_screen.json")


def weights(out):
    return {h["ticker"]: h["weight_pct"] for h in out["holdings"]}


def test_want_ai_avoid_oil_picks_and_weights():
    out = builder.build({"ai": "want", "oil": "avoid"})
    w = weights(out)
    # Pass: AI High/Moderate AND Oil Limited/Limited-low. A4 (oil ND), A5 (oil M), XOM, O*, C*, KO fail.
    assert set(w) == {"A1", "A2", "A3", "A6", "A7", "A8", "SMH"}
    # Equal weight: 7 picks -> 100/7 = 14.29% each, under the 15% cap.
    for t in w:
        assert w[t] == pytest.approx(100 / 7, abs=0.01)
    assert sum(w.values()) == pytest.approx(100, abs=0.05)  # display rounding to 2 decimals
    assert out["cash_pct"] == 0
    a3 = next(h for h in out["holdings"] if h["ticker"] == "A3")
    assert a3["labels"] == ["Oil: lower confidence"]
    assert any("lower confidence: A3" in x for x in out["warnings"])
    v = out["verification"]
    assert v["all_pass"] and v["checks"]["ai"]["high_moderate_pct"] == pytest.approx(100)
    assert v["checks"]["oil"]["high_moderate_pct"] == 0


def test_multiple_want_themes_equal_weight():
    out = builder.build({"ai": "want", "cyber": "want"})
    pts = {h["ticker"]: h["points"] for h in out["holdings"] if h["ticker"] != "CASH"}
    assert pts == {"A3": 1, "A6": 1}  # equal weight
    assert any("Only 2 holding" in x for x in out["warnings"])
    # Two names can hold at most 30% under the 15% cap; the rest is cash.
    assert weights(out) == {"A3": 15.0, "A6": 15.0, "CASH": 70.0}
    assert out["verification"]["all_pass"]


def test_avoid_only_is_equal_weight_and_excludes_not_determined():
    out = builder.build({"oil": "avoid", "cyber": "avoid"})
    w = weights(out)
    assert "A8" not in w and "C2" not in w and "XOM" not in w  # cyber ND / oil M are excluded
    assert set(w) == {"A1", "A2", "A7", "SMH", "KO"} | {"CASH"}
    assert all(w[t] == 15.0 for t in w if t != "CASH") and w["CASH"] == 25.0


def test_nothing_qualifies():
    out = builder.build({"ai": "want", "oil": "want", "cyber": "want"})
    assert out["holdings"] == [] and out["verification"] is None
    assert "No stocks" in out["warnings"][0]


def test_cap_and_rescale_math():
    w, cash = builder.cap_and_rescale({"a": 10, "b": 1, "c": 1, "d": 1, "e": 1, "f": 1, "g": 1, "h": 1})
    assert w["a"] == pytest.approx(15) and cash == 0
    assert all(w[t] == pytest.approx(85 / 7) for t in "bcdefgh")
    assert builder.cap_and_rescale({}) == ({}, 100.0)
    w, cash = builder.cap_and_rescale({"a": 1})
    assert w == {"a": 15.0} and cash == pytest.approx(85)
    with pytest.raises(ValueError):
        builder.cap_and_rescale({"a": 0})


def test_prescreen_is_cached(monkeypatch):
    builder.prescreen()
    calls = []
    monkeypatch.setattr(screen, "_screen_one", lambda *a: calls.append(a))
    builder.prescreen()
    assert calls == []  # second run read the cache
    monkeypatch.setattr(builder, "_cache_key", lambda themes, tickers: "different")
    builder.prescreen()
    assert len(calls) == len(TABLE) * len(THEMES)  # key changed -> the whole universe is re-screened


@pytest.mark.parametrize("prefs, msg", [
    ({}, "at least one"), ({"nope": "want"}, "No theme called"), ({"ai": "love"}, "'want' or 'avoid'"),
])
def test_bad_preferences(prefs, msg):
    with pytest.raises(builder.BuildError, match=msg):
        builder.build(prefs)


def test_cli(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    assert builder.main(["--want", "ai", "--avoid", "oil"]) == 0
    out = capsys.readouterr().out
    assert "Basket (7 holdings)" in out and "All goals met." in out and "[Oil: lower confidence]" in out
    assert json.loads((tmp_path / "results" / "build_latest.json").read_text())["preferences"] == {"ai": "want", "oil": "avoid"}
    assert builder.main(["--want", "ai,cyber", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["cash_pct"] == 70
    assert builder.main(["--want", "ai", "--avoid", "ai"]) == 2
    assert "both want and avoid" in capsys.readouterr().err
    assert builder.main([]) == 2
    assert builder.main(["--want", "ai", "--avoid", "oil", "--refresh"]) == 0


def test_two_key_rule_rejects_picks_without_etf_confirmation(monkeypatch):
    themes = {**THEMES, "ai": {**THEMES["ai"], "ground_truth": "AIETF"}}
    monkeypatch.setattr(builder, "load_all", lambda: themes)
    monkeypatch.setattr(screen, "load_theme", lambda k: themes[k])
    monkeypatch.setattr(builder, "etf_check", lambda t, th: {"etf": "AIETF", "pass": t != "A1"})
    out = builder.build({"ai": "want", "oil": "avoid"}, refresh=True)
    assert "A1" not in weights(out) and out["rejected_by_etf_check"] == ["A1"]
    assert any("failed the theme-ETF confirmation: A1" in x for x in out["warnings"])
    # avoid-only builds and themes without an ETF are unaffected
    assert "A1" in weights(builder.build({"oil": "avoid"}))
