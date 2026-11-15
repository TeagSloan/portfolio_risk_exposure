"""Price data: FMP (mode="fmp"), Yahoo Finance via yfinance (mode="live"), or simulated (mode="demo").

Live mode caches every download in data/cache/prices.csv, so the hackathon demo can run
from the cache with no internet ("freeze a snapshot before you present").

Demo mode generates SIMULATED returns with a known factor structure. Use it to build and test
the dashboard; never present its numbers as real results. The app labels it on every screen.
"""
from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "prices.csv"
LOOKBACK_YEARS = 2


def get_returns(tickers: list[str], mode: str = "live", refresh: bool = False) -> pd.DataFrame:
    """Daily simple returns, one column per ticker. 'GV' = IWF minus IWD (growth minus value)."""
    want = sorted(set(tickers) | {"IWF", "IWD"})
    if mode == "demo":
        prices = simulated_prices(want)
    elif mode == "fmp":
        from . import fmp
        end = pd.Timestamp.today().normalize()
        start = end - pd.DateOffset(years=LOOKBACK_YEARS, days=10)
        prices = fmp.prices(want, str(start.date()), str(end.date()))
    else:
        prices = _live_prices(want, refresh)
    rets = prices.pct_change(fill_method=None).iloc[1:]
    if {"IWF", "IWD"} <= set(rets.columns):
        rets["GV"] = rets["IWF"] - rets["IWD"]
    return rets


def _live_prices(tickers: list[str], refresh: bool) -> pd.DataFrame:
    cached = pd.read_csv(CACHE, index_col=0, parse_dates=True) if CACHE.exists() else pd.DataFrame()
    need = [t for t in tickers if refresh or t not in cached.columns]
    if need:
        import yfinance as yf  # imported lazily so demo mode works without it

        end = pd.Timestamp.today().normalize()
        start = end - pd.DateOffset(years=LOOKBACK_YEARS, days=10)
        raw = yf.download(need, start=start, end=end, auto_adjust=True, progress=False)
        fresh = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": need[0]})
        fresh = fresh.dropna(how="all", axis=1)
        if fresh.empty and cached.empty:
            raise RuntimeError("Could not download prices. Check your internet connection, or use Demo mode.")
        cached = fresh if cached.empty else cached.drop(columns=[c for c in fresh.columns if c in cached]).join(fresh, how="outer")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        cached.sort_index().to_csv(CACHE)
    return cached[[t for t in tickers if t in cached.columns]].sort_index()


# ---------------------------------------------------------------------------------------------
# Simulated data. Loadings on latent factors: market, rates, style (growth), ai, oil, disrupt.
# ---------------------------------------------------------------------------------------------
_LOADINGS = {
    #        mkt   rate  style  ai    oil   disrupt
    "SPY":  (1.00, 0.00, 0.00, 0.00, 0.00, 0.00),
    "TLT":  (0.00, 1.00, 0.00, 0.00, 0.00, 0.00),
    "IWF":  (1.05, 0.10, 0.60, 0.10, 0.00, 0.00),
    "IWD":  (0.95, 0.10, -0.40, 0.00, 0.05, 0.00),
    "NVDA": (1.30, 0.00, 0.60, 1.20, 0.00, 0.00),
    "AVGO": (1.20, 0.00, 0.50, 1.00, 0.00, 0.00),
    "MU":   (1.30, 0.00, 0.30, 0.90, 0.00, 0.00),
    "VRT":  (1.20, 0.00, 0.40, 0.90, 0.10, 0.00),
    "TSM":  (1.10, 0.00, 0.40, 0.70, 0.00, 0.00),
    "MSFT": (1.00, 0.10, 0.50, 0.40, 0.00, 0.00),
    "VST":  (0.90, 0.20, 0.20, 0.50, 0.20, 0.00),
    "CHGG": (1.00, 0.00, 0.30, -0.30, 0.00, 1.20),
    "ADM":  (0.70, 0.20, -0.40, 0.00, 0.10, 0.00),
    "SMH":  (1.20, 0.00, 0.50, 0.95, 0.00, 0.00),
    "DELL": (1.10, 0.00, 0.20, 0.60, 0.00, 0.00),
    "ORCL": (1.00, 0.30, 0.60, 0.55, 0.00, 0.00),
    "AAPL": (1.00, 0.00, 0.50, 0.15, 0.00, 0.00),
    "JNJ":  (0.60, 0.20, -0.70, -0.05, 0.00, 0.00),
    "KO":   (0.60, 0.20, -0.60, -0.05, 0.00, 0.00),
    "DUK":  (0.50, 0.40, -0.60, 0.05, 0.00, 0.00),
    "AGG":  (0.05, 0.35, 0.00, 0.00, 0.00, 0.00),
    "JPM":  (1.10, -0.20, -0.30, 0.10, 0.10, 0.00),
    "XOM":  (0.80, 0.00, -0.40, 0.00, 0.90, 0.00),
    "CVX":  (0.80, 0.00, -0.40, 0.00, 0.85, 0.00),
    "XLE":  (0.85, 0.00, -0.40, 0.00, 0.95, 0.00),
    "USO":  (0.30, 0.00, 0.00, 0.00, 1.40, 0.00),
    "EOG":  (0.90, 0.00, -0.30, 0.00, 1.10, 0.00),
    "OXY":  (0.90, 0.00, -0.30, 0.00, 1.20, 0.00),
    "DVN":  (0.95, 0.00, -0.30, 0.00, 1.20, 0.00),
    "COP":  (0.90, 0.00, -0.30, 0.00, 1.10, 0.00),
    "FANG": (0.95, 0.00, -0.30, 0.00, 1.20, 0.00),
    "APA":  (1.00, 0.00, -0.30, 0.00, 1.30, 0.00),
    "SLB":  (1.00, 0.00, -0.20, 0.00, 0.80, 0.00),
    "HAL":  (1.10, 0.00, -0.20, 0.00, 0.85, 0.00),
    "BKR":  (1.00, 0.00, -0.20, 0.00, 0.70, 0.00),
    "DAL":  (1.20, 0.00, 0.00, 0.00, -0.70, 0.00),
    "UAL":  (1.30, 0.00, 0.00, 0.00, -0.75, 0.00),
    "AAL":  (1.30, 0.00, 0.00, 0.00, -0.70, 0.00),
    "LUV":  (1.00, 0.00, 0.00, 0.00, -0.60, 0.00),
    "ADBE": (1.00, 0.00, 0.50, 0.10, 0.00, 0.20),
}
_FACTOR_VOL = (0.010, 0.008, 0.006, 0.012, 0.015, 0.010)

# Extra simulated factors for the newer themes: (metals, health, credit) loadings,
# plus rate loadings (TLT moves with the rate factor, so rising rates = negative loading).
_EXTRA_VOL = (0.012, 0.008, 0.010)
_EXTRA = {
    "DBB": (1.3, 0, 0), "FCX": (1.2, 0, 0), "SCCO": (1.1, 0, 0), "AA": (1.2, 0, 0), "TECK": (1.0, 0, 0),
    "CENX": (1.1, 0, 0), "NUE": (0.7, 0, 0), "STLD": (0.7, 0, 0), "CLF": (0.8, 0, 0), "RS": (0.5, 0, 0),
    "CMC": (0.6, 0, 0), "BALL": (-0.6, 0, 0), "CCK": (-0.5, 0, 0), "AMCR": (-0.5, 0, 0),
    "XLV": (0, 1.0, 0), "LLY": (0, 1.0, 0), "JNJ": (0, 0.9, 0), "MRK": (0, 1.0, 0), "ABBV": (0, 0.9, 0),
    "PFE": (0, 0.9, 0), "UNH": (0, 0.8, 0), "ELV": (0, 0.8, 0), "ABT": (0, 0.7, 0), "TMO": (0, 0.6, 0),
    "MDT": (0, 0.7, 0), "ISRG": (0, 0.6, 0), "AMGN": (0, 0.8, 0), "DHR": (0, 0.6, 0),
    "COF": (0, 0, 1.1), "SYF": (0, 0, 1.2), "AXP": (0, 0, 0.8), "ALLY": (0, 0, 1.0), "BFH": (0, 0, 1.1),
    "OMF": (0, 0, 1.0), "KMX": (0, 0, 0.6), "CVNA": (0, 0, 0.7), "AN": (0, 0, 0.5), "LAD": (0, 0, 0.6),
    "PRAA": (0, 0, -0.6), "ECPG": (0, 0, -0.6),
}
_CHINA = {"FXI": 1.3, "QCOM": 0.6, "AAPL": 0.35, "LVS": 0.9, "WYNN": 0.7, "YUMC": 1.0, "NKE": 0.3}
_LOADINGS.update({
    "AMD":   (1.30, 0.00, 0.50, 1.00, 0.00, 0.00), "MRVL": (1.30, 0.00, 0.40, 0.90, 0.00, 0.00),
    "ANET":  (1.10, 0.00, 0.40, 0.80, 0.00, 0.00), "GOOGL": (1.00, 0.00, 0.50, 0.35, 0.00, 0.00),
    "AMZN":  (1.10, 0.00, 0.50, 0.35, 0.00, 0.00),
})
_RATE = {"JPM": -0.5, "BAC": -0.6, "WFC": -0.5, "USB": -0.5, "PNC": -0.5, "TFC": -0.5, "MET": -0.3,
         "PRU": -0.3, "AFL": -0.25, "O": 0.7, "PLD": 0.6, "AMT": 0.7, "SO": 0.5, "NEE": 0.6, "DHI": 0.6,
         "LEN": 0.6}


_INDUSTRY = {"airlines": ["DAL", "UAL", "AAL", "LUV"],
             "producers": ["XOM", "CVX", "EOG", "OXY", "DVN", "COP", "FANG", "APA"],
             "services": ["SLB", "HAL", "BKR"]}


def simulated_prices(tickers: list[str], n_days: int = 500, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp("2026-09-25"), periods=n_days + 1)
    factors = rng.normal(0, 1, (n_days, 6)) * np.array(_FACTOR_VOL)
    extra = rng.normal(0, 1, (n_days, 3)) * np.array(_EXTRA_VOL)
    china = rng.normal(0, 0.012, n_days)
    industry = {k: rng.normal(0, 0.010, n_days) for k in _INDUSTRY}  # same-industry co-movement
    out = {}
    for t in tickers:
        load = _LOADINGS.get(t)
        if load is None:  # unknown ticker: market-like with a random style tilt, no theme exposure
            r = np.random.default_rng(zlib.crc32(t.encode()))
            load = (r.uniform(0.7, 1.2), 0, r.uniform(-0.3, 0.3), 0, 0, 0)
        load = list(load)
        if t in _RATE:
            load[1] = _RATE[t]
        idio_vol = 0.0005 if t in {"SPY", "TLT", "IWF", "IWD"} else \
            0.004 if t in {"AGG", "SMH", "XLE", "USO", "XLV", "DBB", "FXI"} else 0.014
        rets = factors @ np.array(load) + extra @ np.array(_EXTRA.get(t, (0, 0, 0))) \
            + _CHINA.get(t, 0) * china + rng.normal(0, idio_vol, n_days)
        for k, members in _INDUSTRY.items():
            if t in members:
                rets = rets + industry[k]
        out[t] = 100 * np.concatenate([[1.0], np.cumprod(1 + rets)])
    return pd.DataFrame(out, index=dates)
