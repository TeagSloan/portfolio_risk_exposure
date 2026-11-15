"""Client for the Financial Modeling Prep (FMP) "stable" API.

Every response is saved to data/cache/fmp/ the first time it is fetched. After that the
saved copy is used, so the engine stays fast, works offline once data is cached, and
doesn't burn API calls. Pass refresh=True to force a fresh download.

The API key comes from the project's .env file (FMP_API_KEY) and is sent in a request
header, so it never appears in a URL, a log line or a cache file.

Quick check from the command line (tests every endpoint on the given tickers):

    python -m engine.fmp NVDA XOM
"""

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://financialmodelingprep.com/stable/"
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "fmp"
REQUEST_TIMEOUT_SECONDS = 30
# On a rate limit or server hiccup, wait this many seconds and try again.
RETRY_WAITS_SECONDS = (1, 3)

load_dotenv(PROJECT_ROOT / ".env")


class FMPError(Exception):
    """FMP data could not be fetched. The message is safe to show to a user."""


# ---------------------------------------------------------------------------
# Core request + cache
# ---------------------------------------------------------------------------

def _api_key():
    key = os.environ.get("FMP_API_KEY", "").strip()
    if not key:
        raise FMPError("No FMP API key found. Add FMP_API_KEY to the .env file.")
    return key


def _cache_path(path, params):
    """One file per endpoint + parameters, e.g. profile__3f2a9c1b0d4e5f67.json."""
    params_text = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{path}?{params_text}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"{path.replace('/', '_')}__{digest}.json"


def _fetch(path, params):
    """Call FMP, retrying briefly on rate limits and server errors."""
    for attempt in range(len(RETRY_WAITS_SECONDS) + 1):
        try:
            response = requests.get(
                BASE_URL + path,
                params=params,
                headers={"apikey": _api_key()},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise FMPError(f"Could not reach FMP ({exc.__class__.__name__}).") from exc

        retryable = response.status_code == 429 or response.status_code >= 500
        if retryable and attempt < len(RETRY_WAITS_SECONDS):
            time.sleep(RETRY_WAITS_SECONDS[attempt])
            continue
        break

    if response.status_code in (401, 403):
        raise FMPError("FMP rejected the API key.")
    if response.status_code == 402:
        raise FMPError(f"'{path}' is not included in your FMP plan.")
    if response.status_code == 429:
        raise FMPError("FMP rate limit reached. Wait a minute and try again.")
    if response.status_code != 200:
        raise FMPError(f"FMP returned an error for '{path}' (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise FMPError(f"FMP sent back unreadable data for '{path}'.") from exc
    if isinstance(data, dict) and ("Error Message" in data or "error" in data):
        message = data.get("Error Message") or data.get("error")
        raise FMPError(f"FMP error for '{path}': {message}")
    return data


def get(path, params=None, refresh=False):
    """Return FMP's JSON for an endpoint, using the cache when possible.

    path:    endpoint after /stable/, e.g. "profile" or "historical-price-eod/dividend-adjusted"
    params:  query parameters (never the API key)
    refresh: True to ignore the cache and download again
    """
    params = dict(params or {})
    cache_file = _cache_path(path, params)
    if not refresh and cache_file.exists():
        return json.loads(cache_file.read_text())["data"]

    data = _fetch(path, params)
    # Empty answers are not cached: they may be a temporary gap rather than "no data".
    if data:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "path": path,
            "params": params,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "data": data,
        }
        cache_file.write_text(json.dumps(record))
    return data


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------

def _symbol(symbol):
    if not isinstance(symbol, str) or not symbol.strip():
        raise FMPError(f"'{symbol}' is not a valid ticker.")
    return symbol.strip().upper()


def profile(symbol, refresh=False):
    """Company profile: name, sector, industry, market cap, whether it's an ETF, etc."""
    symbol = _symbol(symbol)
    rows = get("profile", {"symbol": symbol}, refresh)
    if not rows:
        raise FMPError(f"No company profile found for '{symbol}'. Check the ticker.")
    return rows[0]


def revenue_product_segmentation(symbol, period="annual", refresh=False):
    """Revenue by product/business segment, newest fiscal year first."""
    symbol = _symbol(symbol)
    rows = get("revenue-product-segmentation", {"symbol": symbol, "period": period}, refresh)
    return sorted(rows or [], key=lambda r: r.get("date", ""), reverse=True)


def latest_segment_shares(symbol, refresh=False):
    """Each segment's share of revenue in the latest fiscal year.

    Returns {"fiscal_year": 2026, "date": "...", "total": ..., "shares": {"Data Center": 0.88}}.
    Shares are of the sum of reported segments.
    """
    rows = revenue_product_segmentation(symbol, refresh=refresh)
    if not rows:
        raise FMPError(f"FMP has no segment revenue for '{_symbol(symbol)}'.")
    latest = rows[0]
    segments = {k: v for k, v in (latest.get("data") or {}).items() if isinstance(v, (int, float))}
    total = sum(segments.values())
    if total <= 0:
        raise FMPError(f"Segment revenue for '{_symbol(symbol)}' adds up to zero.")
    return {
        "fiscal_year": latest.get("fiscalYear"),
        "date": latest.get("date"),
        "total": total,
        "shares": {k: v / total for k, v in sorted(segments.items(), key=lambda kv: -kv[1])},
    }


def income_statement(symbol, period="annual", limit=5, refresh=False):
    """Income statements, newest first."""
    symbol = _symbol(symbol)
    params = {"symbol": symbol, "period": period, "limit": limit}
    return get("income-statement", params, refresh) or []


def company_screener(refresh=False, **filters):
    """Stock screener, e.g. company_screener(sector="Energy", marketCapMoreThan=5e10, limit=20)."""
    return get("company-screener", filters, refresh) or []


def adjusted_prices(symbol, start, end, refresh=False):
    """Daily dividend-adjusted closing prices as a Series indexed by date (oldest first)."""
    symbol = _symbol(symbol)
    params = {"symbol": symbol, "from": str(start), "to": str(end)}
    rows = get("historical-price-eod/dividend-adjusted", params, refresh)
    if not rows:
        raise FMPError(f"No price history found for '{symbol}'. Check the ticker.")
    try:
        prices = pd.Series(
            {pd.Timestamp(r["date"]): float(r["adjClose"]) for r in rows}, name=symbol
        ).sort_index()
    except (KeyError, TypeError, ValueError) as exc:
        raise FMPError(f"Price data for '{symbol}' was missing dates or prices.") from exc
    if (prices <= 0).any():
        raise FMPError(f"Price data for '{symbol}' contains zero or negative prices.")
    return prices


# ---------------------------------------------------------------------------
# Command-line check: which endpoints work on this plan?
# ---------------------------------------------------------------------------

def check_endpoints(symbols, today=None):
    """Try every endpoint the project uses. Returns one result row per (endpoint, ticker)."""
    today = today or datetime.now(UTC).date()
    start = today.replace(year=today.year - 2)
    checks = {
        "profile": lambda s: _describe_profile(profile(s)),
        "revenue-product-segmentation": lambda s: _describe_segments(latest_segment_shares(s)),
        "income-statement": lambda s: _describe_income(income_statement(s, limit=1)),
        "historical-price-eod/dividend-adjusted": lambda s: _describe_prices(
            adjusted_prices(s, start, today)),
    }
    results = []
    for endpoint, run in checks.items():
        for symbol in symbols:
            results.append(_run_check(endpoint, symbol, run))
    # One screener call per distinct sector among the tickers (skips unknown tickers).
    sectors = []
    for symbol in symbols:
        try:
            sector = profile(symbol).get("sector")
        except FMPError:
            continue
        if sector and sector not in sectors:
            sectors.append(sector)
    for sector in sectors:
        results.append(_run_check(
            "company-screener", f"sector={sector}",
            lambda _s, sector=sector: _describe_screener(
                company_screener(sector=sector, marketCapMoreThan=10_000_000_000, limit=10))))
    return results


def _run_check(endpoint, label, run):
    try:
        return {"endpoint": endpoint, "ticker": label, "ok": True, "detail": run(label)}
    except FMPError as exc:
        return {"endpoint": endpoint, "ticker": label, "ok": False, "detail": str(exc)}


def _describe_profile(p):
    return f"{p.get('companyName')} | {p.get('sector')} / {p.get('industry')}"


def _describe_segments(s):
    top = ", ".join(f"{k} {v:.0%}" for k, v in list(s["shares"].items())[:3])
    return f"FY{s['fiscal_year']}: {top}"


def _describe_income(rows):
    if not rows:
        return "no statements returned"
    r = rows[0]
    return f"FY{r.get('fiscalYear')}: revenue ${r.get('revenue', 0) / 1e9:,.1f}B"


def _describe_prices(prices):
    return f"{len(prices)} days, {prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}"


def _describe_screener(rows):
    return f"{len(rows)} companies, e.g. {', '.join(r.get('symbol', '?') for r in rows[:4])}"


def main(argv=None):
    symbols = [s.upper() for s in (argv if argv is not None else sys.argv[1:])] or ["NVDA", "XOM"]
    try:
        results = check_endpoints(symbols)
    except FMPError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for r in results:
        mark = "OK  " if r["ok"] else "FAIL"
        print(f"{mark} {r['endpoint']:<40} {r['ticker']:<22} {r['detail']}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
