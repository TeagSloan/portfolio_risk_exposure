"""Market, style and sector controls, and the objective rule for skipping them.

Every regression controls for the overall market (SPY) and bonds (TLT). On top of that:

Style controls (daily return spreads):
    VALUE  = IWD  - IWF   value minus growth
    SIZE   = RSP  - SPY   equal-weight minus cap-weight (small vs mega-cap)
    MOM    = MTUM - SPY   momentum minus market
    LOWVOL = USMV - SPY   low-volatility/defensive minus market

Sector control: each holding gets the spread of its own SPDR sector ETF minus SPY (from its FMP
profile sector). ETFs get no sector control: a sector ETF minus SPY would explain a sector ETF
perfectly, and other ETFs (e.g. SMH) don't belong to one sector.

Skip rule (objective, the same for every theme): a control is skipped for a theme if the theme's
Tier 1 reference companies make up more than 15% of that control ETF's holdings (FMP ETF holdings).
For a spread, each non-SPY leg is checked (VALUE checks both IWD and IWF). Controls are never part of
a High/Moderate group and never count in the Bonferroni denominator.
"""

from __future__ import annotations

from engine import fmp

SKIP_THRESHOLD_PCT = 15.0

STYLE = {"VALUE": ("IWD", "IWF"), "SIZE": ("RSP", "SPY"), "MOM": ("MTUM", "SPY"), "LOWVOL": ("USMV", "SPY")}

SECTOR_ETF = {
    "Technology": "XLK", "Healthcare": "XLV", "Energy": "XLE", "Financial Services": "XLF",
    "Industrials": "XLI", "Consumer Defensive": "XLP", "Consumer Cyclical": "XLY", "Basic Materials": "XLB",
    "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC",
}
SECTOR_SPREADS = {f"SEC_{etf}": (etf, "SPY") for etf in SECTOR_ETF.values()}

# Every built-in spread series engine/data.py knows how to make.
SPREADS = {**STYLE, **SECTOR_SPREADS}


def etf_holdings(etf: str) -> dict[str, float]:
    """{ticker: weight %} for an ETF, from FMP."""
    rows = fmp.get("etf/holdings", {"symbol": etf}) or []
    out: dict[str, float] = {}
    for r in rows:
        if r.get("asset") and isinstance(r.get("weightPercentage"), (int, float)):
            out[r["asset"].upper()] = out.get(r["asset"].upper(), 0.0) + float(r["weightPercentage"])
    return out


def tier1_refs(theme: dict) -> list[str]:
    return [r["ticker"] for g in ("High", "Moderate") for r in theme["references"].get(g, [])]


def ref_share(theme: dict, etf: str) -> float:
    """% of `etf` held in the theme's Tier 1 reference companies."""
    h = etf_holdings(etf)
    return round(sum(h.get(t, 0.0) for t in tier1_refs(theme)), 2)


def style_controls(theme: dict) -> tuple[list[str], dict[str, dict[str, float]]]:
    """(style controls kept, {skipped control: {leg: share %}}) for a theme, using the 15% rule."""
    kept, skipped = [], {}
    for name, legs in STYLE.items():
        shares = {leg: ref_share(theme, leg) for leg in legs if leg != "SPY"}
        if any(s > SKIP_THRESHOLD_PCT for s in shares.values()):
            skipped[name] = shares
        else:
            kept.append(name)
    return kept, skipped


def sector_skips(theme: dict) -> dict[str, float]:
    """{sector ETF: share %} for sector ETFs where the theme's references are > 15% of holdings."""
    out = {}
    for etf in SECTOR_ETF.values():
        s = ref_share(theme, etf)
        if s > SKIP_THRESHOLD_PCT:
            out[etf] = s
    return out


def sector_shares(theme: dict) -> dict[str, float]:
    """Reference share of every sector ETF (for reporting)."""
    return {etf: ref_share(theme, etf) for etf in SECTOR_ETF.values()}


def sector_of(ticker: str) -> str | None:
    """The holding's SPDR sector ETF, or None for ETFs / unknown sectors."""
    try:
        rows = fmp.profile(ticker)
    except fmp.FMPError:
        return None
    if not rows:
        return None
    p = rows[0]
    if p.get("isEtf") or p.get("isFund"):
        return None
    return SECTOR_ETF.get(p.get("sector") or "")


def sector_control(ticker: str, theme: dict) -> str | None:
    """Name of the sector spread column to use for this holding and theme, or None."""
    if not theme.get("use_sector_control"):
        return None
    etf = sector_of(ticker)
    if etf is None or etf in theme.get("sector_skips", {}):
        return None
    return f"SEC_{etf}"
