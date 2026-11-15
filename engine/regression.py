"""Pooled-category exposure regression - the core of the screen.

For one holding and one theme:

    r_holding = a + b_spy*SPY + b_tlt*TLT [+ b_gv*(IWF-IWD)] + sum_j b_j * r_ref_j + e

Then, for each reference category (High / Moderate / Inverse ...), add up the betas of its
members and test the SUM (pooled test). Individual betas do not need to be significant.

Rules (same as the AI Exposure Screen, generalized to any theme):
  * A category is ELIGIBLE if its signed beta sum > MATERIALITY (0.05) and its one-sided
    p-value < ALPHA / n_reference_factors (Bonferroni over the reference names).
  * If several categories are eligible, the largest beta sum wins - EXCEPT that a positive category
    and an inverse category both eligible is contradictory -> "Not determined" (new conflict rule).
  * If none is eligible, the holding is LIMITED only when every positive category's one-sided
    95% upper bound (sum + 1.645*SE) is below MATERIALITY. That is proven, not assumed.
  * Otherwise, if every positive point estimate is below MATERIALITY and at least one is
    negative -> "Limited (lower confidence)", a directional read.
  * Otherwise -> "Not determined".

Diagnostics (rate sensitivity, growth/value tilt) are single hypotheses: plain p < 0.05.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

MATERIALITY = 0.05
ALPHA = 0.05
Z_95_ONE_SIDED = 1.645
MIN_OBS = 120


@dataclass
class CategoryResult:
    name: str
    direction: str
    members: list[str]
    beta_sum: float
    se: float
    p_one_sided: float
    upper_95: float
    eligible: bool


@dataclass
class HoldingResult:
    ticker: str
    theme: str
    tier: str
    explanation: str
    n_obs: int = 0
    r2: float = float("nan")
    categories: list[CategoryResult] = field(default_factory=list)
    member_betas: pd.DataFrame | None = None   # ticker, category, beta, se, t, p
    diagnostics: dict = field(default_factory=dict)
    start: str = ""
    end: str = ""
    plain: str = ""   # plain-language summary for non-finance users (set by portfolio.py)
    classified_by: str = "pooled regression"


def _ols(y: np.ndarray, X: np.ndarray):
    """OLS with classical covariance. X must already include the intercept column."""
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    dof = n - k
    s2 = float(resid @ resid) / dof
    cov = s2 * xtx_inv
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(resid @ resid) / tss if tss > 0 else float("nan")
    return beta, cov, dof, r2


def _analyze_holding_impl(
    ticker: str,
    returns: pd.DataFrame,
    theme: dict,
    controls: list[str],
) -> HoldingResult:
    """Core holding analysis without any theme-level split logic."""
    categories = theme["categories"]
    ref_tickers: list[str] = []
    for cat in categories:
        ref_tickers += [m["ticker"] for m in cat["members"]]
    ref_tickers += [c["ticker"] for c in theme.get("control", [])]
    ref_tickers = [t for t in dict.fromkeys(ref_tickers) if t != ticker and t in returns]

    cols = [ticker] + controls + ref_tickers
    missing = [c for c in cols if c not in returns]
    if missing:
        return HoldingResult(ticker, theme["name"], "Not determined",
                             f"No price data for: {', '.join(missing)}.")
    df = returns[cols].dropna()
    if len(df) < MIN_OBS:
        return HoldingResult(ticker, theme["name"], "Not determined",
                             f"Only {len(df)} overlapping trading days (need {MIN_OBS}).")
    y = df[ticker].to_numpy()
    X = np.column_stack([np.ones(len(df))] + [df[c].to_numpy() for c in controls + ref_tickers])
    names = ["const"] + controls + ref_tickers
    beta, cov, dof, r2 = _ols(y, X)
    idx = {n: i for i, n in enumerate(names)}

    n_factors = max(len(ref_tickers), 1)
    threshold = ALPHA / n_factors

    # Individual member betas (for the drill-down; not required to be significant).
    rows = []
    for cat in categories:
        for m in cat["members"]:
            t = m["ticker"]
            if t not in idx:
                continue
            b, se = beta[idx[t]], np.sqrt(cov[idx[t], idx[t]])
            tstat = b / se if se > 0 else np.nan
            rows.append({"ticker": t, "category": cat["name"], "beta": b, "se": se, "t": tstat,
                         "p_two_sided": 2 * stats.t.sf(abs(tstat), dof),
                         "evidence_pct": m.get("evidence_pct"),
                         "evidence_type": m.get("evidence_type", ""),
                         "note": m.get("note", ""), "source": m.get("source", "")})
    member_betas = pd.DataFrame(rows)

    # Pooled category tests.
    cat_results: list[CategoryResult] = []
    for cat in categories:
        mem = [m["ticker"] for m in cat["members"] if m["ticker"] in idx]
        if not mem:
            continue
        c = np.zeros(len(names))
        for t in mem:
            c[idx[t]] = 1.0
        s = float(c @ beta)
        se = float(np.sqrt(c @ cov @ c))
        p = float(stats.t.sf(s / se, dof)) if se > 0 else 1.0
        cat_results.append(CategoryResult(
            name=cat["name"], direction=cat.get("direction", "positive"), members=mem,
            beta_sum=s, se=se, p_one_sided=p, upper_95=s + Z_95_ONE_SIDED * se,
            eligible=(s > MATERIALITY and p < threshold)))

    # Diagnostics: single hypotheses -> plain p < 0.05 (fixes the old Bonferroni label bug).
    diagnostics = {}
    for label, col in [("Rate sensitivity (TLT)", "TLT"), ("Growth/value tilt", "GV")]:
        if col in idx:
            b, se = beta[idx[col]], np.sqrt(cov[idx[col], idx[col]])
            p = 2 * stats.t.sf(abs(b / se), dof)
            diagnostics[label] = {"beta": b, "p": p, "significant": p < 0.05}

    tier, explanation = _classify(ticker, theme["name"], cat_results, threshold, r2)
    return HoldingResult(ticker, theme["name"], tier, explanation, len(df), r2, cat_results,
                         member_betas, diagnostics,
                         str(df.index.min().date()), str(df.index.max().date()))


def _analyze_holding_split(
    ticker: str,
    returns: pd.DataFrame,
    theme: dict,
    controls: list[str],
) -> HoldingResult:
    """Run one regression per direction group for themes whose opposite groups are not comparable."""
    group_rows: list[CategoryResult] = []
    for cat in theme["categories"]:
        part_theme = {**theme, "categories": [cat], "control": theme.get("control", [])}
        res = _analyze_holding_impl(ticker, returns, part_theme, controls)
        if res.categories:
            group_rows.extend(res.categories)

    if not group_rows:
        return _analyze_holding_impl(ticker, returns, theme, controls)

    threshold = ALPHA / max(len([m for cat in theme["categories"] for m in cat["members"]]), 1)
    r2 = _analyze_holding_impl(ticker, returns, {**theme, "categories": theme["categories"]}, controls).r2
    tier, explanation = _classify(ticker, theme["name"], group_rows, threshold, r2)
    return HoldingResult(
        ticker=ticker,
        theme=theme["name"],
        tier=tier,
        explanation=explanation,
        n_obs=_analyze_holding_impl(ticker, returns, {**theme, "categories": theme["categories"]}, controls).n_obs,
        r2=r2,
        categories=group_rows,
        member_betas=None,
        diagnostics={
            **_analyze_holding_impl(ticker, returns, {**theme, "categories": theme["categories"]}, controls).diagnostics,
        },
        start="",
        end="",
        plain="",
        classified_by="pooled regression",
    )


def analyze_holding(
    ticker: str,
    returns: pd.DataFrame,
    theme: dict,
    controls: list[str],
) -> HoldingResult:
    """Classify one holding against one theme. `returns` holds daily returns by ticker."""
    if theme.get("split_reference_groups"):
        return _analyze_holding_split(ticker, returns, theme, controls)
    return _analyze_holding_impl(ticker, returns, theme, controls)


def _classify(ticker, theme_name, cats: list[CategoryResult], threshold, r2):
    eligible = [c for c in cats if c.eligible]
    fit_note = (" The full model explains only a modest share of overall price movement."
                if r2 < 0.30 else "")
    pos_ok = [c for c in eligible if c.direction == "positive"]
    inv_ok = [c for c in eligible if c.direction == "inverse"]
    if pos_ok and inv_ok:
        both = ", ".join(f"{c.name} {c.beta_sum:.3f}" for c in pos_ok + inv_ok)
        return "Not determined", (
            f"{ticker}: conflicting {theme_name} evidence. It co-moves significantly with BOTH a positive "
            f"group and the inverse group ({both}). Since those groups move in opposite directions on "
            f"{theme_name}, this most likely reflects a shared non-{theme_name} driver, so no flag is assigned.")
    if eligible:
        win = max(eligible, key=lambda c: c.beta_sum)
        if win.direction == "inverse":
            msg = (f"{ticker} is flagged Inverse {theme_name} exposure: it co-moves with companies whose "
                   f"filings disclose being hurt by {theme_name} (pooled beta sum {win.beta_sum:.3f}, "
                   f"one-sided p {win.p_one_sided:.2g} < {threshold:.4f}).")
        else:
            msg = (f"{ticker} is flagged {win.name} {theme_name} exposure through the pooled {win.name} "
                   f"category test after controlling for the market and rates. The signed group sum "
                   f"({win.beta_sum:.3f}) clears the {MATERIALITY} effect floor and its one-sided p-value "
                   f"({win.p_one_sided:.2g}) passes the Bonferroni threshold ({threshold:.4f}); "
                   f"individual matches need not be significant.")
        return win.name, msg + fit_note

    positive = [c for c in cats if c.direction == "positive"]
    if positive and all(c.upper_95 < MATERIALITY for c in positive):
        bounds = ", ".join(f"{c.name} {c.upper_95:.3f}" for c in positive)
        return "Limited", (f"{ticker} is flagged Limited {theme_name} exposure: co-movement with every "
                           f"positive reference group is statistically bounded below {MATERIALITY} "
                           f"(one-sided 95% upper bounds: {bounds})." + fit_note)
    if positive and all(c.beta_sum < MATERIALITY for c in positive) and any(c.beta_sum < 0 for c in positive):
        return "Limited (lower confidence)", (
            f"{ticker} shows no eligible {theme_name} evidence and its point estimates lean negative, "
            f"but the confidence bounds are too wide to prove Limited. Directional read only." + fit_note)
    return "Not determined", (f"{ticker}: the evidence is neither strong enough to flag exposure nor "
                              f"tight enough to rule it out. This is an honest 'we can't tell', not an error.")


def direct_beta(ticker: str, returns: pd.DataFrame, factor: str, controls: list[str]) -> dict:
    """Ground-truth check: beta of a holding directly on an observable price (e.g., crude via USO)."""
    cols = [ticker, factor] + [c for c in controls if c != factor]
    if any(c not in returns for c in cols):
        return {"beta": np.nan, "t": np.nan}
    df = returns[cols].dropna()
    if len(df) < MIN_OBS:
        return {"beta": np.nan, "t": np.nan}
    X = np.column_stack([np.ones(len(df))] + [df[c].to_numpy() for c in cols[1:]])
    beta, cov, dof, _ = _ols(df[ticker].to_numpy(), X)
    return {"beta": float(beta[1]), "t": float(beta[1] / np.sqrt(cov[1, 1]))}
