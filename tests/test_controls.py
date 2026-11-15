"""Tests for engine/controls.py (FMP ETF holdings and profiles faked)."""

import pytest

from engine import controls, fmp

HOLDINGS = {
    "IWF": {"NVDA": 12.0, "MSFT": 6.0, "AAPL": 9.0},
    "IWD": {"XOM": 2.0, "JPM": 3.0},
    "MTUM": {"NVDA": 4.0, "JNJ": 4.0},
    "RSP": {"NVDA": 0.2}, "USMV": {"MSFT": 1.5},
    "XLK": {"NVDA": 13.0, "MSFT": 12.0}, "XLE": {"XOM": 23.0},
}
PROFILES = {"NVDA": {"sector": "Technology"}, "XOM": {"sector": "Energy"}, "SMH": {"sector": "Technology", "isEtf": True},
            "ODD": {"sector": "Shipping"}}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(fmp, "get", lambda ep, p: [{"asset": a, "weightPercentage": w}
                                                   for a, w in HOLDINGS.get(p["symbol"], {}).items()])
    monkeypatch.setattr(fmp, "profile", lambda t: [PROFILES[t]] if t in PROFILES else [])


def theme(refs, **kw):
    return {"references": {"High": [{"ticker": t} for t in refs], "Moderate": []}, **kw}


def test_style_skip_rule_checks_every_non_spy_leg():
    kept, skipped = controls.style_controls(theme(["NVDA", "MSFT"]))
    assert skipped == {"VALUE": {"IWD": 0.0, "IWF": 18.0}}  # IWF 18% > 15% -> skip VALUE
    assert kept == ["SIZE", "MOM", "LOWVOL"]  # MTUM 4%, RSP 0.2%, USMV 1.5%: under 15%


def test_exactly_15_percent_is_not_skipped():
    HOLDINGS["MTUM"]["XOM"] = 15.0
    try:
        assert "MOM" not in controls.style_controls(theme(["XOM"]))[1]
    finally:
        del HOLDINGS["MTUM"]["XOM"]


def test_sector_skips_and_sector_control():
    th = theme(["XOM"], use_sector_control=True, sector_skips=controls.sector_skips(theme(["XOM"])))
    assert th["sector_skips"] == {"XLE": 23.0}
    assert controls.sector_control("XOM", th) is None          # Energy -> XLE, skipped for this theme
    assert controls.sector_control("NVDA", th) == "SEC_XLK"    # Technology -> XLK
    assert controls.sector_control("SMH", th) is None          # ETFs get no sector control
    assert controls.sector_control("ODD", th) is None          # unknown sector
    assert controls.sector_control("NOPE", th) is None         # no profile
    assert controls.sector_control("NVDA", {**th, "use_sector_control": False}) is None


def test_spreads_cover_styles_and_all_sectors():
    assert controls.SPREADS["SIZE"] == ("RSP", "SPY") and controls.SPREADS["SEC_XLRE"] == ("XLRE", "SPY")
    assert len(controls.SECTOR_SPREADS) == 11
