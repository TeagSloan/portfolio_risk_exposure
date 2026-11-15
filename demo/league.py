"""Turn the dashboard's fund into a Fantasy Fund League entry: the pre-filled League link and its QR code.

Nothing here touches the chain. The League page (league/index.html) reads ?etf=TICKER:PCT,...&name=... and fills in
the player's ETF; the player still reviews it and confirms the entry in their own wallet.

League rules (checked again by the FundLeague contract): 3-8 stocks, whole-number weights adding up to 100%, each at
least 5%, and only stocks in the League's pool.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from urllib.parse import quote

import segno

LEAGUE_URL = "https://shannon-maccallum.github.io/portfolio_risk_exposure/league/"  # defaults to Monad testnet
POOL_FILE = Path(__file__).resolve().parent.parent / "league" / "pool.json"
MIN_STOCKS, MAX_STOCKS, MIN_PCT = 3, 8, 5


@cache
def pool_tickers() -> frozenset[str]:
    """Every stock the League accepts (the full universe with enough price history)."""
    return frozenset(s["ticker"] for s in json.loads(POOL_FILE.read_text())["stocks"])


def whole_percents(weights: dict[str, float]) -> dict[str, int]:
    """Rescale to whole percents that add up to exactly 100, each at least MIN_PCT (largest remainders first)."""
    total = sum(weights.values())
    raw = {t: 100 * w / total for t, w in weights.items()}
    out = {t: max(MIN_PCT, int(v)) for t, v in raw.items()}
    rank = {t: i for i, t in enumerate(weights)}  # the fund's own order (the builder's ranking) breaks ties
    order = sorted(raw, key=lambda t: (-(raw[t] - int(raw[t])), -raw[t], rank[t]))
    i = 0
    while sum(out.values()) < 100:  # hand out the missing points to the biggest remainders
        out[order[i % len(order)]] += 1
        i += 1
    while sum(out.values()) > 100:  # taking 5% floors can overshoot: trim the largest weights
        t = max(out, key=lambda x: (out[x], -rank[x]))
        out[t] -= 1
    return out


def league_fund(weights: dict[str, float], pool: frozenset[str] | None = None) -> tuple[dict[str, int], list[str]]:
    """The fund as a League ETF: ({ticker: whole %}, plain-English notes). Empty dict if it can't enter."""
    pool = pool_tickers() if pool is None else pool
    stocks = {t: w for t, w in weights.items() if t != "CASH" and w > 0}
    notes = []
    outside = sorted(t for t in stocks if t not in pool)
    if outside:
        one = len(outside) == 1
        notes.append(f"{', '.join(outside)} {'is' if one else 'are'} not in the League's stock pool, so "
                     f"{'it is' if one else 'they are'} left out of the League entry.")
    stocks = {t: w for t, w in stocks.items() if t in pool}
    if len(stocks) > MAX_STOCKS:
        rank = {t: i for i, t in enumerate(stocks)}  # ties (equal weights) keep the fund's ranking order
        keep = sorted(stocks, key=lambda t: (-stocks[t], rank[t]))[:MAX_STOCKS]
        notes.append(f"The League allows at most {MAX_STOCKS} stocks, so your entry uses your {MAX_STOCKS} largest "
                     "(top-ranked) holdings, rescaled to add up to 100%.")
        stocks = {t: stocks[t] for t in keep}
    if len(stocks) < MIN_STOCKS:
        notes.append(f"A League entry needs at least {MIN_STOCKS} pool stocks; this fund has {len(stocks)}.")
        return {}, notes
    return whole_percents(stocks), notes


def fund_name(prefs: dict[str, str], theme_names: dict[str, str]) -> str:
    """A short entry name from the choices, e.g. "AI ex-Oil" (the League allows 32 characters)."""
    wants = [theme_names[k] for k, v in prefs.items() if v == "want"]
    avoids = [theme_names[k] for k, v in prefs.items() if v == "avoid"]
    name = " + ".join(wants) or "My fund"
    if avoids:
        name += " ex-" + ", ".join(avoids)
    if len(name.encode()) <= 32:
        return name
    return name.encode()[:29].decode(errors="ignore").rstrip(" ,+-") + "…"  # "…" is 3 bytes: 32 in all


def prefill_url(etf: dict[str, int], name: str) -> str:
    """The League page with this ETF filled in."""
    spec = ",".join(f"{t}:{w}" for t, w in etf.items())  # in the fund's order
    return f"{LEAGUE_URL}?etf={quote(spec, safe=':,')}&name={quote(name)}"


def qr_svg(url: str) -> str:
    """A QR code for the link, drawn locally (no outside service). Dark on light so phone cameras read it."""
    return segno.make(url, error="m").svg_inline(scale=5, border=3, dark="#0B0A0B", light="#F5EEF1")
