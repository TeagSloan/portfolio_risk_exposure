"""Batch scoring: every stock in the universe on every theme, matching run_screen exactly.

How it stays exact:
- For one stock, run_screen joins the stock's prices with every regressor's prices (only dates they ALL
  have), then computes returns. So any stock that has a price on every date the regressors share gets
  exactly the same sample: those stocks are scored together in one matrix regression ("batch").
- Stocks with gaps or a short history, and the theme's own control company (which must be left off the
  right-hand side), are scored one at a time with run_screen's own code ("single").
- Theme references and Tier 2 names keep their listed tier ("listed"), as in run_screen.
- Non-US stocks get the extra INTL control (VXUS minus SPY) in both paths; they form their own batch.

The batch math is ordinary least squares done for many stocks at once with the same X: betas = pinv(X) Y,
residual variance per stock, group sums w'b with SE sqrt(s2 * w' (X'X)^-1 w), one-sided t p-values.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy import stats

from engine import data, screen
from engine.business import business_linked
from engine.controls import SPREADS
from engine.regression import (
    ALPHA,
    GROUPS,
    MIN_SUM,
    Z_ONE_SIDED_95,
    GroupStats,
    classify,
    decide_tier,
    reference_names,
    sentence,
)

START, END = data.DEFAULT_START, data.DEFAULT_END


class PriceStore:
    """Each ticker's adjusted price series, loaded once from the cache (same sources as get_prices)."""

    def __init__(self):
        self._s: dict[str, pd.Series | None] = {}

    def get(self, t: str) -> pd.Series | None:
        if t not in self._s:
            s = data._from_fmp(t, START, END)
            if s is None or s.empty:
                s = data._from_yfinance(t, START, END)
            self._s[t] = None if s is None or s.empty else s
        return self._s[t]


def _legs(cols: list[str]) -> list[str]:
    out = []
    for c in cols:
        out += list(SPREADS[c]) if c in SPREADS else [c]
    return list(dict.fromkeys(out))


def regressor_frame(store: PriceStore, regressors: list[str]) -> tuple[pd.DatetimeIndex, pd.DataFrame]:
    """(shared price dates of all regressor legs, regressor price table on those dates)."""
    legs = _legs(regressors)
    series = [store.get(t) for t in legs]
    if any(s is None for s in series):
        missing = [t for t, s in zip(legs, series, strict=True) if s is None]
        raise data.DataError(f"No price data for regressor(s): {', '.join(missing)}")
    prices = pd.concat(series, axis=1, join="inner").sort_index()
    prices.columns = legs
    return prices.index, prices


def _returns_with_spreads(prices: pd.DataFrame, regressors: list[str]) -> pd.DataFrame:
    r = prices.pct_change(fill_method=None).iloc[1:]
    for name, (a, b) in SPREADS.items():
        if name in regressors:
            r[name] = r[a] - r[b]
    return r


def batch_ols(Y: pd.DataFrame, X: pd.DataFrame, groups: dict[str, list[str]], n_names: int) -> pd.DataFrame:
    """OLS of every column of Y on X (+ constant). One row of group stats per stock."""
    Xc = np.column_stack([np.ones(len(X)), X.values])
    cols = ["const"] + list(X.columns)
    pinv = np.linalg.pinv(Xc)
    B = pinv @ Y.values                                  # (k, N) betas for every stock
    resid = Y.values - Xc @ B
    n, rank = Xc.shape[0], np.linalg.matrix_rank(Xc)
    df = n - rank
    s2 = (resid ** 2).sum(axis=0) / df                   # residual variance per stock
    xtx_inv = pinv @ pinv.T                              # = (X'X)^-1, as statsmodels computes it
    yc = Y.values - Y.values.mean(axis=0)
    r2 = 1 - (resid ** 2).sum(axis=0) / (yc ** 2).sum(axis=0)
    out = pd.DataFrame(index=Y.columns)
    out["r_squared"], out["n_obs"] = r2, n
    for g, names in groups.items():
        w = np.array([1.0 if c in names else 0.0 for c in cols])
        s = w @ B
        se = np.sqrt(s2 * (w @ xtx_inv @ w))
        t = np.where(se > 0, s / np.where(se > 0, se, 1), np.inf)
        p = stats.t.sf(t, df)
        out[f"{g}_sum"], out[f"{g}_se"], out[f"{g}_p"] = s, se, p
        out[f"{g}_upper"] = s + Z_ONE_SIDED_95 * se
        out[f"{g}_eligible"] = (s > MIN_SUM) & (p < ALPHA / n_names)
    return out


def _tier_from_row(row: pd.Series, groups: list[str]) -> str:
    gs = {g: GroupStats(names=[], beta_sum=row[f"{g}_sum"], se=row[f"{g}_se"], p_one_sided=row[f"{g}_p"],
                        upper_95=row[f"{g}_upper"], eligible=bool(row[f"{g}_eligible"])) for g in groups}
    return decide_tier(gs)


def _row_from_result(res: dict, path: str) -> dict:
    row = {"tier": res["tier"], "method": res["method"], "path": path, "sentence": res["sentence"],
           "r_squared": res.get("r_squared"), "n_obs": res.get("n_obs"), "error": res.get("error"),
           "p_threshold": res.get("p_threshold")}
    for g, st in (res.get("groups") or {}).items():
        row.update({f"{g}_sum": st["beta_sum"], f"{g}_se": st["se"], f"{g}_p": st["p_one_sided"],
                    f"{g}_upper": st["upper_95"], f"{g}_eligible": bool(st["eligible"])})
    return row


def score_theme(theme: dict, tickers: list[str], meta: dict[str, dict], store: PriceStore) -> list[dict]:
    """Rows for every ticker on one theme."""
    refs = reference_names(theme)
    groups = [g for g in GROUPS if refs[g]]
    control_co = theme["control"]["ticker"]
    listed = {r["ticker"] for g in GROUPS for r in theme["references"].get(g, [])}
    listed |= {d["ticker"] for d in theme.get("direct_classification", [])}
    rows: dict[str, dict] = {}

    for t in tickers:
        if t in listed:
            res = classify(t, theme, None).to_dict()
            rows[t] = _row_from_result(res, "listed")

    for intl in (False, True):
        extra = ["INTL"] if intl else []
        regressors = list(theme["controls"]) + extra + refs["High"] + refs["Moderate"] + [control_co]
        dates, reg_prices = regressor_frame(store, regressors)
        batch, single = [], []
        for t in tickers:
            if t in rows or (meta.get(t, {}).get("country", "US") not in ("US", "")) != intl:
                continue
            s = store.get(t)
            if t == control_co or t in regressors or s is None or not dates.isin(s.index).all():
                single.append(t)
            else:
                batch.append(t)
        if batch:
            prices = pd.concat([reg_prices] + [store.get(t).reindex(dates).rename(t) for t in batch], axis=1)
            r = _returns_with_spreads(prices, regressors)
            n_names = len(refs["High"]) + len(refs["Moderate"]) + 1
            st = batch_ols(r[batch], r[regressors], {g: refs[g] for g in groups}, n_names)
            for t in batch:
                tier = _tier_from_row(st.loc[t], groups)
                row = {"tier": tier, "method": "regression", "path": "batch",
                       "sentence": sentence(t, theme["name"], tier, "regression", plain=theme.get("plain")),
                       "error": None, "p_threshold": ALPHA / n_names,
                       **{c: (bool(st.loc[t, c]) if c.endswith("_eligible") else st.loc[t, c]) for c in st.columns}}
                row["n_obs"] = int(row["n_obs"])
                row["data_start"], row["data_end"] = r.index[0].date().isoformat(), r.index[-1].date().isoformat()
                rows[t] = row
        for t in single:  # exactly run_screen's own code path
            res = screen._screen_one(t, theme, START, END)
            rows[t] = _row_from_result(res, "single")
            s = store.get(t)
            idx = dates.intersection(s.index) if s is not None else dates[:0]
            rows[t]["data_start"] = idx[1].date().isoformat() if len(idx) > 1 else None
            rows[t]["data_end"] = idx[-1].date().isoformat() if len(idx) > 1 else None

    out = []
    refs_used = ",".join(refs["High"] + refs["Moderate"])
    for t in tickers:
        m = meta.get(t, {})
        row = {"ticker": t, "theme": theme["key"], **rows[t],
               "business_linked": business_linked(t, m.get("industry"), theme),
               "country": m.get("country"), "sector": m.get("sector"), "industry": m.get("industry"),
               "market_cap": float(m.get("market_cap") or 0), "references_used": refs_used,
               "controls_used": ",".join(list(theme["controls"]) + (["INTL"] if m.get("country") not in ("US", "", None) else [])),
               "as_of": date.today().isoformat()}
        out.append(row)
    return out
