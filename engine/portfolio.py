"""Run a whole portfolio across every theme."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from .baseline import BASELINES, snapshot_to_theme
from .data import get_returns
from .regression import analyze_holding, direct_beta

ROOT = Path(__file__).resolve().parents[1]
THEMES_DIR = ROOT / "themes"
CASH = {"CASH", "USD", "MMF"}
FLAGGED = {"High", "Moderate"}
LIVE_SOURCES = ("sec_live", "fmp_segments", "fmp_rules")

# Plain-language wording for people who aren't finance-heavy. A theme YAML can override any tier
# with its own `plain` text (e.g. "Tends to rise when oil prices rise").
DEFAULT_PLAIN = {
    "High": "Strongly tied to {theme}",
    "Moderate": "Partly tied to {theme}",
    "Inverse": "Tends to move the opposite way from {theme}",
    "Limited": "Little or no link to {theme}",
    "Limited (lower confidence)": "Probably little link to {theme}, but the evidence isn't conclusive",
    "Not determined": "Not enough evidence either way",
}


def load_themes() -> dict[str, dict]:
    themes = {}
    for path in sorted(THEMES_DIR.glob("*.yaml")):
        t = yaml.safe_load(path.read_text())
        if t.get("enabled", True) is False:
            continue
        if t.get("baseline_source") in LIVE_SOURCES:
            snap_path = BASELINES / f"{t['name'].lower().replace(' ', '_')}.json"
            if not snap_path.exists():
                t["error"] = f"No baseline yet. Run: python build_baseline.py {path.stem}"
                themes[t["name"]] = t
                continue
            t = snapshot_to_theme(t, json.loads(snap_path.read_text()))
        themes[t["name"]] = t
    return themes


def ground_truth(theme: dict) -> dict:
    gt = theme.get("ground_truth") or {}
    if not gt and theme.get("ground_truth_ticker"):
        gt = {"ticker": theme["ground_truth_ticker"], "sign": 1}
    return gt


def theme_controls(theme: dict, available: pd.DataFrame, style_control: bool) -> list[str]:
    """SPY + TLT (+ growth/value), minus anything the theme measures itself (rates drops TLT)."""
    controls = ["SPY", "TLT"] + (["GV"] if style_control and "GV" in available else [])
    return [c for c in controls if c not in theme.get("drop_controls", [])]


def plain_text(theme: dict, tier: str) -> str:
    spec = theme.get("tiers", {}).get(tier, {})
    label = theme.get("plain_name", theme["name"])
    return spec.get("plain") or DEFAULT_PLAIN.get(tier, tier).format(theme=label)


def classify_holding(ticker: str, returns: pd.DataFrame, theme: dict, controls: list[str]):
    """Same rules as the AI Exposure Screen:
      1. A reference company held in the portfolio is classified directly as its own tier.
      2. A Tier 2 name (direct_classification) is classified directly from its qualitative evidence.
      3. Everything else goes through the pooled regression.
    The regression still runs in cases 1-2 so its statistics are available for information."""
    r = analyze_holding(ticker, returns, theme, controls)
    r.classified_by = "pooled regression"
    for cat in theme.get("categories", []):
        for m in cat["members"]:
            if m["ticker"] == ticker:
                ev = f"{m.get('evidence_pct')}% · {m.get('evidence_type', '')}".strip(" ·")
                r.tier, r.classified_by = cat["name"], "reference company (Tier 1)"
                r.explanation = (f"{ticker} is itself a {cat['name']} reference company for {theme['name']} "
                                 f"({ev}), so it is classified directly. Regression statistics are shown "
                                 f"for information only.")
                return r
    for c in theme.get("control", []):
        if c["ticker"] == ticker:
            r.tier, r.classified_by = "Limited", "zero-exposure control"
            r.explanation = f"{ticker} is the zero-exposure control for {theme['name']}: {c.get('note', '')}"
            return r
    for d in theme.get("direct_classification", []):
        if d["ticker"] == ticker:
            r.tier, r.classified_by = d["tier"], "direct classification (Tier 2)"
            r.explanation = (f"{ticker} is classified directly as {d['tier']} {theme['name']} exposure "
                             f"({d.get('evidence_type', '')}; {d.get('note', '')}). Tier 2 evidence is not "
                             f"used as a regression reference; regression statistics are shown for information only.")
            return r
    return r


def reference_tickers(theme: dict) -> list[str]:
    out = [m["ticker"] for c in theme.get("categories", []) for m in c["members"]]
    return out + [c["ticker"] for c in theme.get("control", [])]


def analyze_portfolio(holdings: pd.DataFrame, themes: dict[str, dict], mode: str = "live",
                      style_control: bool = True, refresh: bool = False) -> dict:
    holdings = holdings.copy()
    holdings["ticker"] = holdings["ticker"].astype(str).str.upper().str.strip()
    holdings = holdings[holdings["ticker"] != ""]
    total = holdings["weight"].sum()
    holdings["weight"] = holdings["weight"] / total * 100 if total else holdings["weight"]

    usable = {k: v for k, v in themes.items() if "error" not in v}
    tickers = set(holdings["ticker"]) - CASH | {"SPY", "TLT"}
    for th in usable.values():
        tickers |= set(reference_tickers(th))
        if ground_truth(th):
            tickers.add(ground_truth(th)["ticker"])
    returns = get_returns(sorted(tickers), mode=mode, refresh=refresh)

    results, validation, controls_used = {}, {}, {}
    for name, th in usable.items():
        controls = theme_controls(th, returns, style_control)
        controls_used[name] = controls
        results[name] = {}
        for _, row in holdings.iterrows():
            t = row["ticker"]
            if t in CASH:
                results[name][t] = None
                continue
            r = classify_holding(t, returns, th, controls)
            r.plain = plain_text(th, r.tier)
            results[name][t] = r
        gt = ground_truth(th)
        if gt:
            validation[name] = _validate(th, results[name], returns, gt, controls)

    def weight_where(res, tiers):
        return float(holdings.loc[holdings["ticker"].map(
            lambda t: res.get(t) is not None and res[t].tier in tiers), "weight"].sum())

    return {"holdings": holdings, "results": results,
            "fingerprint": {n: weight_where(res, FLAGGED) for n, res in results.items()},
            "inverse": {n: weight_where(res, {"Inverse"}) for n, res in results.items()},
            "validation": validation, "controls": controls_used,
            "skipped_themes": {k: v["error"] for k, v in themes.items() if "error" in v}}


def _validate(theme, holding_results, returns, gt, controls) -> pd.DataFrame:
    """Compare the method's signed score with a direct beta on the observable price."""
    rows = []
    universe = dict(holding_results)
    for t in reference_tickers(theme):
        if t not in universe:
            universe[t] = analyze_holding(t, returns, theme, controls)
    base = [c for c in ["SPY", "TLT"] if c != gt["ticker"] and c not in theme.get("drop_controls", [])]
    for t, r in universe.items():
        if r is None or not r.categories:
            continue
        score = sum(c.beta_sum for c in r.categories if c.direction == "positive") - \
            sum(c.beta_sum for c in r.categories if c.direction == "inverse")
        d = direct_beta(t, returns, gt["ticker"], base)
        rows.append({"ticker": t, "method_score": score, "direct_beta": d["beta"] * gt.get("sign", 1),
                     "tier": r.tier, "is_holding": t in holding_results})
    return pd.DataFrame(rows)
