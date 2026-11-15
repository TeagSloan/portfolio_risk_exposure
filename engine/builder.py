"""Way 2, "Build my ETF": theme preferences -> a basket of individual stocks, re-checked with Way 1.

    build({"ai": "want", "oil": "avoid", "gold": "dont_care"}, region="all")  -> dict (JSON-ready)

Command line:
    python -m engine.builder --want ai --avoid oil
    python -m engine.builder --want ai,cyber --avoid oil --dont-care gold --region us --json

Rules:
- Universe: data/exposure_table.parquet (every stock in data/universe.csv, already scored on every theme by
  python -m engine.build_table). Individual NYSE + NASDAQ stocks only.
- Region: all, us (country = US) or intl (everything else, e.g. ADRs).
- "want"       -> High or Moderate for that theme AND business_linked (the stock's industry is in the theme's
                  allowed list, or it's a named reference / Tier 2 company). A price link alone isn't enough.
- "avoid"      -> passes unless the regression flags it High or Moderate on that theme (Not determined,
                  Limited and Limited (lower confidence) all pass). Safety net: stocks that are business_linked
                  to the avoided theme (e.g. oil companies for avoid Oil) are excluded whatever their tier.
                  Each pick's tier on the avoided theme is shown.
- "dont_care"  -> no rule for that theme.
- A stock must pass EVERY rule. Survivors are ranked, for each want theme: (a) the theme's Tier 1 reference
  companies first, (b) then High before Moderate, (c) then by the t-statistic of the theme's largest group sum
  (signed, so moving against the references ranks low). References use a leave-one-out regression; Tier 2
  names keep their listed tier but rank by an ordinary regression like any other stock (ranking only). With several want themes, each theme's percentile rank in that
  ordering is added up. With no want theme, the largest companies by market cap come first. The top TOP_N are held at equal weight, capped at 15% each;
  if there are too few names to reach 100% under the cap, the rest is held as cash.
- The funnel shows how many stocks are left after each rule.
- Fewer than 6 holdings -> the basket is returned with a clear warning.
- The final basket is re-checked from scratch with Way 1 (run_screen), and its fingerprint is compared with
  the goals.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from engine import screen
from engine.build_table import load_table
from engine.regression import HIGH, MODERATE
from engine.theme_loader import load_all

ROOT = Path(__file__).resolve().parent.parent
CAP_PCT = 15.0
TOP_N = 15  # how many ranked stocks go into the basket
MIN_HOLDINGS = 6
WANT_OK = {HIGH, MODERATE}
AVOID_FAIL = {HIGH, MODERATE}
CHOICES = {"want": "want", "avoid": "avoid", "dont_care": "dont_care", "don't care": "dont_care",
           "dont care": "dont_care", "dontcare": "dont_care"}
REGIONS = {"all": "All regions", "us": "US only", "intl": "International only"}


class BuildError(ValueError):
    """The preferences couldn't be understood."""


def prescreen() -> dict[str, dict[str, dict]]:
    """{ticker: {theme_key: result}} for the whole universe, in run_screen's result shape, from the exposure
    table. (chain/publish.py reads its results from here.)"""
    themes = load_all()
    out: dict[str, dict[str, dict]] = {}
    for r in load_table().to_dict("records"):
        th = themes[r["theme"]]
        groups = {}
        for g in ("High", "Moderate"):
            if r.get(f"{g}_sum") is not None and not pd.isna(r.get(f"{g}_sum")):
                groups[g] = {"names": [x["ticker"] for x in th["references"].get(g, [])],
                             "beta_sum": r[f"{g}_sum"], "se": r[f"{g}_se"], "p_one_sided": r[f"{g}_p"],
                             "upper_95": r[f"{g}_upper"], "eligible": bool(r[f"{g}_eligible"])}
        nan = lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else v
        out.setdefault(r["ticker"], {})[r["theme"]] = {
            "ticker": r["ticker"], "theme": th["name"], "tier": r["tier"], "method": r["method"],
            "sentence": r["sentence"], "groups": groups, "n_obs": nan(r.get("n_obs")),
            "r_squared": nan(r.get("r_squared")), "p_threshold": nan(r.get("p_threshold")),
            "controls": (r.get("controls_used") or "").split(",") if r["method"] == "regression" else [],
        }
    return out


def cap_and_rescale(points: dict[str, float], cap: float = CAP_PCT) -> tuple[dict[str, float], float]:
    """Weights proportional to points, none above `cap`, summing to 100. Returns (weights, cash %).

    Repeatedly pins anything over the cap at the cap and spreads the remainder over the rest in
    proportion to their points. If every holding ends up at the cap, the leftover is cash.
    """
    if not points:
        return {}, 100.0
    if any(p <= 0 for p in points.values()):
        raise ValueError("Points must be positive.")
    weights: dict[str, float] = {}
    free = dict(points)
    remaining = 100.0
    while free:
        total = sum(free.values())
        trial = {t: remaining * p / total for t, p in free.items()}
        over = {t for t, w in trial.items() if w > cap + 1e-12}
        if not over:
            weights.update(trial)
            remaining = 0.0
            break
        for t in over:
            weights[t] = cap
            remaining -= cap
            del free[t]
    return weights, max(remaining, 0.0)


def _validate(prefs: dict[str, str], themes: dict[str, dict], region: str) -> dict[str, str]:
    if region not in REGIONS:
        raise BuildError(f"Region must be one of: {', '.join(REGIONS)}")
    clean = {}
    for k, v in prefs.items():
        key, choice = k.strip().lower(), CHOICES.get(str(v).strip().lower())
        if key not in themes:
            raise BuildError(f"No theme called '{k}'. Available: {', '.join(sorted(themes))}")
        if choice is None:
            raise BuildError(f"'{k}': choose 'want', 'avoid' or 'dont_care', not '{v}'")
        clean[key] = choice
    if not any(v in ("want", "avoid") for v in clean.values()):
        raise BuildError("Choose at least one theme to want or avoid, e.g. --want ai --avoid oil")
    return clean


def build(prefs: dict[str, str], region: str = "all", table: pd.DataFrame | None = None) -> dict:
    themes = load_all()
    prefs = _validate(prefs, themes, region)
    t = load_table() if table is None else table
    want = [k for k, v in prefs.items() if v == "want"]
    avoid = [k for k, v in prefs.items() if v == "avoid"]
    dont_care = [k for k, v in prefs.items() if v == "dont_care"]

    tiers = t.pivot(index="ticker", columns="theme", values="tier")
    linked = t.pivot(index="ticker", columns="theme", values="business_linked")
    strength = t.pivot(index="ticker", columns="theme", values="strength")
    tstat = t.pivot(index="ticker", columns="theme", values="strength_t")
    is_ref = t.pivot(index="ticker", columns="theme", values="reference")
    info = t.groupby("ticker")[["name", "industry", "country", "market_cap"]].first().reindex(tiers.index)
    country = info["country"].fillna("")
    alive = pd.Series(True, index=tiers.index)
    funnel = [{"step": "Universe (scored stocks)", "left": int(alive.sum())}]

    if region == "us":
        alive &= country.eq("US")
    elif region == "intl":
        alive &= ~country.isin(["US", ""])
    if region != "all":
        funnel.append({"step": f"Region: {REGIONS[region]}", "left": int(alive.sum())})
    for k in want:
        name = themes[k]["name"]
        alive &= tiers[k].isin(WANT_OK)
        funnel.append({"step": f"Want {name}: High or Moderate", "left": int(alive.sum())})
        alive &= linked[k].astype(bool)
        funnel.append({"step": f"Want {name}: business-linked", "left": int(alive.sum())})
    for k in avoid:
        name = themes[k]["name"]
        alive &= ~tiers[k].isin(AVOID_FAIL)
        funnel.append({"step": f"Avoid {name}: not flagged High or Moderate", "left": int(alive.sum())})
        alive &= ~linked[k].astype(bool)
        funnel.append({"step": f"Avoid {name}: not in the {name} business (safety net)", "left": int(alive.sum())})
    if dont_care:
        funnel.append({"step": "Don't care: " + ", ".join(themes[k]["name"] for k in dont_care) + " (no rule)",
                       "left": int(alive.sum())})

    survivors = list(alive[alive].index)
    def theme_order(k):
        """Survivors in ranking order for one want theme: Tier 1 references first, then High, then t-statistic."""
        return sorted(survivors, key=lambda x: (not bool(is_ref.loc[x, k]), tiers.loc[x, k] != HIGH,
                                                -float(0 if pd.isna(tstat.loc[x, k]) else tstat.loc[x, k]), x))

    if want:
        n = len(survivors)
        pct = {k: {x: 1 - i / n for i, x in enumerate(theme_order(k))} for k in want}  # 1 = best
        score = pd.Series({x: sum(pct[k][x] for k in want) for x in survivors}, dtype=float)
        order = theme_order(want[0]) if len(want) == 1 else sorted(survivors, key=lambda x: (-score[x], x))
        basis = ("Tier 1 references first, then High before Moderate, then t-statistic" if len(want) == 1
                 else "sum of percentile ranks (references first, High before Moderate, then t-statistic)")
    else:
        score = info["market_cap"].astype(float)
        order = sorted(survivors, key=lambda x: (-score[x], x))
        basis = "market cap (no want theme)"
    picks = order[:TOP_N]
    if len(survivors) > TOP_N:
        funnel.append({"step": f"Ranked by {basis}: top {TOP_N}", "left": len(picks)})

    weights, cash = cap_and_rescale(dict.fromkeys(picks, 1.0))  # equal weight
    warnings = []
    if not picks:
        warnings.append("No stocks pass every rule. Try fewer or looser preferences, or another region.")
    elif len(picks) < MIN_HOLDINGS:
        warnings.append(f"Only {len(picks)} holding(s) pass every rule (target is at least {MIN_HOLDINGS}). "
                        "The basket is small and concentrated.")
    if picks and cash > 1e-9:
        warnings.append(f"With {len(picks)} holding(s) and a {CAP_PCT:g}% cap, only {100 - cash:.0f}% can be "
                        f"invested; {cash:.0f}% is held as cash.")

    basket = {p: round(w, 4) for p, w in sorted(weights.items(), key=lambda kv: (-kv[1], order.index(kv[0])))}
    if picks and cash > 1e-9:  # no picks -> no basket at all, not 100% cash
        basket[screen.CASH] = round(cash, 4)

    def holding(p, wt):
        if p == screen.CASH:
            return {"ticker": p, "weight_pct": round(wt, 2)}
        nan = lambda v: None if pd.isna(v) else v
        return {"ticker": p, "weight_pct": round(wt, 2), "name": info.loc[p, "name"], "industry": info.loc[p, "industry"],
                "want_tiers": {themes[k]["name"]: tiers.loc[p, k] for k in want},
                "avoid_tiers": {themes[k]["name"]: tiers.loc[p, k] for k in avoid},
                "strength": {themes[k]["name"]: nan(strength.loc[p, k]) for k in want},
                "t_stat": {themes[k]["name"]: nan(tstat.loc[p, k]) for k in want},
                "reference": {themes[k]["name"]: bool(is_ref.loc[p, k]) for k in want},
                "rank_score": float(score[p])}

    return {
        "preferences": prefs, "region": region, "universe_size": len(tiers), "funnel": funnel,
        "ranked_by": basis, "survivors": len(survivors),
        "holdings": [holding(p, wt) for p, wt in basket.items()],
        "cash_pct": round(cash, 2) if picks else 0.0,
        "warnings": warnings,
        "verification": _verify(basket, prefs, themes) if picks else None,
    }


def _verify(basket: dict[str, float], prefs: dict[str, str], themes: dict[str, dict]) -> dict:
    """Re-check the final basket from scratch with Way 1 and compare its fingerprint with the goals."""
    keys = [k for k, v in prefs.items() if v != "dont_care"]
    report = screen.run_screen(basket, keys)
    invested = 100.0 - report["cash_pct"]
    checks = {}
    for k in keys:
        f = report["fingerprint"][k]
        if prefs[k] == "want":
            ok = abs(f["high_moderate_pct"] - invested) < 0.01
            goal = f"all invested weight ({invested:.0f}%) High or Moderate"
        else:
            ok = f["high_moderate_pct"] < 0.01
            goal = "0% High or Moderate"
        checks[k] = {"theme": themes[k]["name"], "choice": prefs[k], "goal": goal, "pass": ok,
                     "high_moderate_pct": f["high_moderate_pct"], "by_tier_pct": f["by_tier_pct"],
                     "sentence": f["sentence"]}
    return {"all_pass": all(c["pass"] for c in checks.values()), "checks": checks}


def summary_text(out: dict) -> str:
    prefs = ", ".join(f"{'dont care' if v == 'dont_care' else v} {k}" for k, v in out["preferences"].items())
    lines = [f"Preferences: {prefs}   Region: {REGIONS[out['region']]}", "", "Funnel:"]
    lines += [f"  {f['left']:5}  {f['step']}" for f in out["funnel"]]
    lines.append("")
    if not out["holdings"]:
        lines.append("No basket: nothing passes every rule.")
    else:
        lines.append(f"Basket ({sum(1 for h in out['holdings'] if h['ticker'] != screen.CASH)} holdings, "
                     f"ranked by {out['ranked_by']}):")
        for h in out["holdings"]:
            if h["ticker"] == screen.CASH:
                lines.append(f"  {'CASH':6} {h['weight_pct']:6.2f}%")
                continue
            want = ", ".join(f"{k} {v}" for k, v in h["want_tiers"].items())
            avoid = ", ".join(f"{k} {v}" for k, v in h["avoid_tiers"].items())
            strength = ", ".join(f"{v:.2f}" if v is not None else "-" for v in h["strength"].values())
            tst = ", ".join(f"{v:.1f}" if v is not None else "-" for v in h["t_stat"].values())
            tag = "ref " if any(h["reference"].values()) else ""
            lines.append(f"  {h['ticker']:6} {h['weight_pct']:6.2f}%  {str(h['name'])[:28]:28} {str(h['industry'])[:30]:30} "
                         f"want: {tag}{want or '-'} | avoid: {avoid or '-'} | t {tst or '-'} | strength {strength or '-'}")
    lines += [f"WARNING: {w}" for w in out["warnings"]]
    v = out["verification"]
    if v:
        lines += ["", "Re-check with Way 1 (fingerprint vs goals):"]
        for c in v["checks"].values():
            lines.append(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['choice']} {c['theme']}: goal {c['goal']}. {c['sentence']}")
        lines.append("All goals met." if v["all_pass"] else "Some goals NOT met; see above.")
    return "\n".join(lines)


def _split(values: list[str] | None) -> list[str]:
    return [x.strip() for v in values or [] for x in v.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine.builder", description="Build a theme basket (Way 2).")
    ap.add_argument("--want", action="append", help="theme key(s) to want, e.g. ai or ai,cyber")
    ap.add_argument("--avoid", action="append", help="theme key(s) to avoid, e.g. oil")
    ap.add_argument("--dont-care", action="append", help="theme key(s) with no rule (optional, for the record)")
    ap.add_argument("--region", default="all", choices=list(REGIONS), help="all (default), us or intl")
    ap.add_argument("--json", action="store_true", help="print the full JSON")
    args = ap.parse_args(argv)
    want, avoid, dc = _split(args.want), _split(args.avoid), _split(args.dont_care)
    try:
        clash = (set(want) & set(avoid)) | (set(dc) & (set(want) | set(avoid)))
        if clash:
            raise BuildError(f"Each theme gets one choice; listed twice: {', '.join(sorted(clash))}")
        prefs = {**dict.fromkeys(dc, "dont_care"), **dict.fromkeys(want, "want"), **dict.fromkeys(avoid, "avoid")}
        out = build(prefs, region=args.region)
    except (BuildError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "build_latest.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str) if args.json else summary_text(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
