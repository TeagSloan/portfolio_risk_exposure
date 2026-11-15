"""Portfolio builder: turn theme preferences into a weighted basket, then prove it with a re-screen.

    build({"ai": "want", "oil": "avoid"})  -> dict (JSON-ready)

Command line:
    python -m engine.builder --want ai --avoid oil
    python -m engine.builder --want ai,cyber --avoid oil,gold --json
    python -m engine.builder --want ai --refresh        (re-run the universe pre-screen)

Rules:
- Universe: every theme reference company plus well-known stocks and sector ETFs (UNIVERSE below).
  The whole universe is screened against every theme once and cached in data/cache/universe_screen.json.
  The cache is rebuilt automatically if the themes, the method or the universe change.
- "want" a theme  -> keep only High or Moderate for that theme.
- "avoid" a theme -> keep only Limited or Limited (lower confidence). High, Moderate and Not determined are
  excluded ("the data can't tell" isn't proof of no exposure). Lower-confidence picks are labeled.
- A holding must pass EVERY chosen rule.
- Weights: points per "want" theme, High = 2, Moderate = 1, added up across want themes. With no want
  themes, equal weight. Then cap each holding at 15% and rescale to 100%.
  If there are too few holdings to reach 100% under the cap (6 or fewer), the cap is kept and the rest is
  held as cash.
- Fewer than 6 qualifying holdings -> return them with a clear warning.
- The final basket is screened again from scratch, and its fingerprint is checked against the goals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from engine import screen
from engine.data import DEFAULT_END, DEFAULT_START
from engine.regression import HIGH, LIMITED, LIMITED_LOW, MODERATE, NOT_DETERMINED
from engine.theme_loader import THEMES_DIR, load_all

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "cache" / "universe_screen.json"
CAP_PCT = 15.0
MIN_HOLDINGS = 6
POINTS = {HIGH: 2, MODERATE: 1}
WANT_OK = {HIGH, MODERATE}
AVOID_OK = {LIMITED, LIMITED_LOW}

# Well-known names added on top of the theme references.
EXTRAS = ["SMH", "AAPL", "KO", "PG", "WMT", "JNJ", "XOM",
          "XLK", "XLE", "XLF", "XLP", "XLU", "XLI"]


class BuildError(ValueError):
    """The preferences couldn't be understood."""


def universe(themes: dict[str, dict]) -> list[str]:
    refs = [r["ticker"] for t in themes.values() for g in ("High", "Moderate") for r in t["references"][g]]
    return sorted(set(refs) | set(EXTRAS))


def _cache_key(themes: dict[str, dict], tickers: list[str]) -> str:
    """Changes whenever the themes, the method code, the price window or the universe change."""
    h = hashlib.sha256()
    for p in sorted(THEMES_DIR.glob("*.yaml")):
        h.update(p.read_bytes())
    for mod in ("regression.py", "data.py", "screen.py"):
        h.update((Path(__file__).resolve().parent / mod).read_bytes())
    h.update(json.dumps([DEFAULT_START, DEFAULT_END, tickers, sorted(themes)]).encode())
    return h.hexdigest()[:16]


def prescreen(refresh: bool = False) -> dict[str, dict[str, dict]]:
    """{ticker: {theme_key: result}} for the whole universe, from cache when possible."""
    themes = load_all()
    tickers = universe(themes)
    key = _cache_key(themes, tickers)
    if not refresh and CACHE_PATH.exists():
        cached = json.loads(CACHE_PATH.read_text())
        if cached.get("key") == key:
            return cached["results"]
    results = {t: {k: screen._screen_one(t, th, DEFAULT_START, DEFAULT_END) for k, th in themes.items()}
               for t in tickers}
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps({"key": key, "results": results}))
    return results


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
    cash = max(remaining, 0.0)
    return weights, cash


def _validate(prefs: dict[str, str], themes: dict[str, dict]) -> dict[str, str]:
    if not prefs:
        raise BuildError("Choose at least one theme to want or avoid, e.g. --want ai --avoid oil")
    clean = {}
    for k, v in prefs.items():
        key, choice = k.strip().lower(), str(v).strip().lower()
        if key not in themes:
            raise BuildError(f"No theme called '{k}'. Available: {', '.join(sorted(themes))}")
        if choice not in ("want", "avoid"):
            raise BuildError(f"'{k}': choose 'want' or 'avoid', not '{v}'")
        clean[key] = choice
    return clean


def build(prefs: dict[str, str], refresh: bool = False) -> dict:
    themes = load_all()
    prefs = _validate(prefs, themes)
    table = prescreen(refresh)
    want = [k for k, v in prefs.items() if v == "want"]
    avoid = [k for k, v in prefs.items() if v == "avoid"]

    picks, points, labels = [], {}, {}
    for ticker, res in table.items():
        tiers = {k: res[k]["tier"] for k in prefs}
        if all(tiers[k] in WANT_OK for k in want) and all(tiers[k] in AVOID_OK for k in avoid):
            picks.append(ticker)
            points[ticker] = sum(POINTS[tiers[k]] for k in want) if want else 1
            labels[ticker] = [f"{themes[k]['name']}: lower confidence" for k in avoid if tiers[k] == LIMITED_LOW]

    weights, cash = cap_and_rescale(points)
    warnings = []
    if not picks:
        warnings.append("No stocks in the universe pass every rule. Try fewer or looser preferences.")
    elif len(picks) < MIN_HOLDINGS:
        warnings.append(f"Only {len(picks)} holding(s) pass every rule (target is at least {MIN_HOLDINGS}). "
                        "The basket is small and concentrated.")
    if picks and cash > 1e-9:
        warnings.append(f"With {len(picks)} holding(s) and a {CAP_PCT:g}% cap, only {100 - cash:.0f}% can be "
                        f"invested; {cash:.0f}% is held as cash.")
    lower = [t for t in picks if labels[t]]
    if lower:
        warnings.append(f"{len(lower)} pick(s) pass an 'avoid' rule only with lower confidence: {', '.join(lower)}.")

    basket = {t: round(w, 4) for t, w in sorted(weights.items(), key=lambda kv: -kv[1])}
    if picks and cash > 1e-9:  # no picks -> no basket at all, not 100% cash
        basket[screen.CASH] = round(cash, 4)

    verification = _verify(basket, prefs, themes) if picks else None
    return {
        "preferences": prefs,
        "universe_size": len(table),
        "holdings": [
            {"ticker": t, "weight_pct": round(w, 2), "points": points.get(t),
             "tiers": {themes[k]["name"]: table[t][k]["tier"] for k in prefs} if t in table else None,
             "labels": labels.get(t, [])}
            for t, w in basket.items()
        ],
        "cash_pct": round(cash, 2) if picks else 0.0,
        "warnings": warnings,
        "verification": verification,
    }


def _verify(basket: dict[str, float], prefs: dict[str, str], themes: dict[str, dict]) -> dict:
    """Re-screen the final basket from scratch and check each goal against its fingerprint."""
    report = screen.run_screen(basket, list(prefs))
    invested = 100.0 - report["cash_pct"]
    checks = {}
    for k, choice in prefs.items():
        f = report["fingerprint"][k]
        if choice == "want":
            ok = abs(f["high_moderate_pct"] - invested) < 0.01
            goal = f"all invested weight ({invested:.0f}%) High or Moderate"
        else:
            ok = f["high_moderate_pct"] < 0.01 and f["by_tier_pct"][NOT_DETERMINED] < 0.01
            goal = "0% High, Moderate or Not determined"
        checks[k] = {"theme": themes[k]["name"], "choice": choice, "goal": goal, "pass": ok,
                     "high_moderate_pct": f["high_moderate_pct"], "by_tier_pct": f["by_tier_pct"],
                     "sentence": f["sentence"]}
    return {"all_pass": all(c["pass"] for c in checks.values()), "checks": checks}


def summary_text(out: dict) -> str:
    prefs = ", ".join(f"{v} {k}" for k, v in out["preferences"].items())
    lines = [f"Preferences: {prefs}   (universe: {out['universe_size']} stocks/ETFs)", ""]
    if not out["holdings"]:
        lines.append("No basket: nothing passes every rule.")
    else:
        lines.append(f"Basket ({sum(1 for h in out['holdings'] if h['ticker'] != screen.CASH)} holdings):")
        for h in out["holdings"]:
            if h["ticker"] == screen.CASH:
                lines.append(f"  {'CASH':6} {h['weight_pct']:6.2f}%")
                continue
            tiers = ", ".join(f"{k}: {v}" for k, v in h["tiers"].items())
            label = f"  [{'; '.join(h['labels'])}]" if h["labels"] else ""
            lines.append(f"  {h['ticker']:6} {h['weight_pct']:6.2f}%   {tiers}{label}")
    for w in out["warnings"]:
        lines.append(f"WARNING: {w}")
    v = out["verification"]
    if v:
        lines += ["", "Re-screen of the final basket (fingerprint vs goals):"]
        for c in v["checks"].values():
            lines.append(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['choice']} {c['theme']}: goal {c['goal']}. {c['sentence']}")
        lines.append("All goals met." if v["all_pass"] else "Some goals NOT met; see above.")
    return "\n".join(lines)


def _split(values: list[str] | None) -> list[str]:
    return [x.strip() for v in values or [] for x in v.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine.builder", description="Build a theme basket.")
    ap.add_argument("--want", action="append", help="theme key(s) to want, e.g. ai or ai,cyber")
    ap.add_argument("--avoid", action="append", help="theme key(s) to avoid, e.g. oil")
    ap.add_argument("--json", action="store_true", help="print the full JSON")
    ap.add_argument("--refresh", action="store_true", help="re-run the universe pre-screen")
    args = ap.parse_args(argv)
    want, avoid = _split(args.want), _split(args.avoid)
    both = set(want) & set(avoid)
    try:
        if both:
            raise BuildError(f"Can't both want and avoid: {', '.join(sorted(both))}")
        out = build({**{k: "want" for k in want}, **{k: "avoid" for k in avoid}}, refresh=args.refresh)
    except BuildError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "build_latest.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1) if args.json else summary_text(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
