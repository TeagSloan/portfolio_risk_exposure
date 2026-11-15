"""Financial Modeling Prep (FMP) client.

Key: put   FMP_API_KEY=your_key_here   in a file named .env in the project folder
(or export it in your shell). The key is never written anywhere else.

Every raw response is saved under data/cache/fmp/ with the time it was retrieved. That doubles as
the audit trail: a baseline built from FMP can point to the exact response it used.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://financialmodelingprep.com/stable"
RAW_CACHE = ROOT / "data" / "cache" / "fmp"


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api_key() -> str:
    _load_dotenv()
    key = os.environ.get("FMP_API_KEY", "")
    if not key or key == "your_key_here":
        raise RuntimeError("No FMP key. Copy .env.example to .env and paste your key after FMP_API_KEY=")
    return key


def get(endpoint: str, use_cache: bool = True, max_age_hours: float = 24, **params):
    """GET an FMP stable endpoint. Cached on disk; retries on rate limits (429) and server errors."""
    RAW_CACHE.mkdir(parents=True, exist_ok=True)
    tag = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    path = RAW_CACHE / f"{endpoint.replace('/', '__')}__{tag}.json"
    if use_cache and path.exists():
        saved = json.loads(path.read_text())
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(saved["retrieved_at"])).total_seconds()
        if age < max_age_hours * 3600:
            return saved["data"]

    url = f"{BASE}/{endpoint}"
    for attempt in range(4):
        r = requests.get(url, params={**params, "apikey": api_key()}, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (401, 403):
            raise RuntimeError(f"FMP refused {endpoint} ({r.status_code}): check your key, or this "
                               f"endpoint may not be included in your FMP plan. {r.text[:200]}")
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "Error Message" in data:
            raise RuntimeError(f"FMP error on {endpoint}: {data['Error Message']}")
        path.write_text(json.dumps({"retrieved_at": datetime.now(timezone.utc).isoformat(),
                                    "endpoint": endpoint, "params": params, "data": data}))
        return data
    raise RuntimeError(f"FMP kept rate-limiting {endpoint}; try again in a minute.")


# ---------------------------------------------------------------- prices
def prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Dividend-adjusted daily closes, one column per ticker."""
    cols = {}
    for t in tickers:
        rows = get("historical-price-eod/dividend-adjusted", symbol=t, **{"from": start, "to": end})
        if isinstance(rows, dict):  # some FMP responses wrap rows as {"historical": [...]}
            rows = rows.get("historical", [])
        if not rows:
            continue
        df = pd.DataFrame(rows)
        close = next((c for c in ["adjClose", "adjclose", "close"] if c in df.columns), None)
        if close is None:
            raise RuntimeError(f"Unexpected FMP price fields for {t}: {list(df.columns)}. Run probe_fmp.py.")
        cols[t] = df.set_index(pd.to_datetime(df["date"]))[close].astype(float)
    return pd.DataFrame(cols).sort_index()


# ---------------------------------------------------------------- segments
def segments(ticker: str, kind: str = "geographic") -> list[dict]:
    """Annual revenue segments, newest first, normalized to
    [{"fiscal_year", "date", "segments": {name: revenue}}].
    kind = "geographic" (regions) or "product" (business lines)."""
    endpoint = {"geographic": "revenue-geographic-segmentation",
                "product": "revenue-product-segmentation"}[kind]
    raw = get(endpoint, symbol=ticker, period="annual", structure="flat")
    out = []
    for item in raw or []:
        if isinstance(item.get("data"), dict):            # stable format
            seg, date = item["data"], item.get("date", "")
            fy = item.get("fiscalYear") or date[:4]
        else:                                              # older format: {"2024-09-28": {...}}
            (date, seg), = item.items()
            fy = date[:4]
        seg = {k: float(v) for k, v in seg.items() if isinstance(v, (int, float))}
        if seg:
            out.append({"fiscal_year": str(fy), "date": date, "segments": seg})
    return sorted(out, key=lambda x: x["date"], reverse=True)


def segment_share(ticker: str, kind: str, match: list[str]) -> dict | None:
    """Share of the latest year's segment revenue in segments whose name contains any `match` word."""
    years = segments(ticker, kind)
    if not years:
        return None
    latest = years[0]
    total = sum(v for v in latest["segments"].values() if v > 0)
    words = [m.lower() for m in match]
    hits = {k: v for k, v in latest["segments"].items() if any(w in k.lower() for w in words)}
    if not total:
        return None
    return {"share": sum(hits.values()) / total, "matched": hits, "total": total,
            "fiscal_year": latest["fiscal_year"], "date": latest["date"],
            "all_segments": latest["segments"]}


def profile(ticker: str) -> dict:
    rows = get("profile", symbol=ticker)
    return rows[0] if rows else {}


def screener(sector: str | None = None, industry: str | None = None,
             min_market_cap: float = 2e9, limit: int = 200) -> list[dict]:
    """US-listed, actively trading common stocks (no ETFs/funds) for a sector or industry.
    May require a paid FMP plan; themes can list tickers explicitly instead."""
    params = {"marketCapMoreThan": int(min_market_cap), "limit": limit, "country": "US",
              "isEtf": "false", "isFund": "false", "isActivelyTrading": "true"}
    if sector:
        params["sector"] = sector
    if industry:
        params["industry"] = industry
    return get("company-screener", **params) or []


def income_statement(ticker: str) -> dict:
    """Latest annual income statement (fields like revenue, costOfRevenue, netInterestIncome)."""
    rows = get("income-statement", symbol=ticker, period="annual", limit=1)
    return rows[0] if rows else {}
