"""One-call backend API. Everything returned is plain JSON (dicts, lists, numbers, strings),
so any frontend - Streamlit, React, a ChatGPT-built app - can use it.

    from engine.api import run_screen, list_baselines
    result = run_screen([{"ticker": "XOM", "weight": 20}, {"ticker": "NVDA", "weight": 30},
                         {"ticker": "CASH", "weight": 50}])

Or from the terminal:
    python -m engine.api XOM:20 NVDA:30 CASH:50 --mode fmp > result.json
"""
from __future__ import annotations

import json
import math
import sys

import pandas as pd

from .portfolio import analyze_portfolio, ground_truth, load_themes


def _clean(x):
    """Make numpy / NaN values JSON-safe."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if hasattr(x, "item"):
        x = x.item()
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def run_screen(holdings: list[dict], themes: list[str] | None = None, mode: str = "fmp",
               style_control: bool = True) -> dict:
    """holdings: [{"ticker": "XOM", "weight": 20}, ...]  (weights are rescaled to 100).
    themes: theme names to run (default: every theme with a built baseline).
    mode: "fmp" | "live" (Yahoo) | "demo" (simulated)."""
    all_themes = load_themes()
    chosen = {k: v for k, v in all_themes.items() if themes is None or k in themes}
    out = analyze_portfolio(pd.DataFrame(holdings), chosen, mode=mode, style_control=style_control)
    h = out["holdings"]

    rows = []
    for _, row in h.iterrows():
        t, entry = row["ticker"], {"ticker": row["ticker"], "weight": round(float(row["weight"]), 2), "themes": {}}
        for name, res in out["results"].items():
            r = res.get(t)
            if r is None:
                entry["themes"][name] = {"tier": "Cash", "plain": "Cash is not analyzed"}
                continue
            entry["themes"][name] = {
                "tier": r.tier,
                "plain": r.plain,                      # one line for non-finance users
                "explanation": r.explanation,          # full statistical reasoning
                "categories": [{"name": c.name, "direction": c.direction, "members": c.members,
                                "beta_sum": c.beta_sum, "se": c.se, "p_one_sided": c.p_one_sided,
                                "upper_95": c.upper_95, "eligible": c.eligible} for c in r.categories],
                "references": [] if r.member_betas is None else r.member_betas.to_dict("records"),
                "diagnostics": r.diagnostics, "r2": r.r2, "n_obs": r.n_obs,
                "period": [r.start, r.end], "controls": out["controls"][name],
            }
        rows.append(entry)

    summary = []
    for name in out["results"]:
        label = chosen[name].get("plain_name", name)
        line = f"{out['fingerprint'][name]:.0f}% of this portfolio is clearly tied to {label}"
        if out["inverse"][name]:
            line += f", and {out['inverse'][name]:.0f}% tends to move the opposite way"
        summary.append({"theme": name, "flagged_pct": out["fingerprint"][name],
                        "inverse_pct": out["inverse"][name], "plain": line + "."})

    validation = {}
    for name, v in out["validation"].items():
        if not v.empty:
            validation[name] = {"ground_truth": ground_truth(chosen[name])["ticker"],
                                "rank_correlation": v[["method_score", "direct_beta"]].corr(method="spearman").iloc[0, 1],
                                "points": v.to_dict("records")}

    return _clean({"mode": mode, "simulated": mode == "demo", "summary": summary, "holdings": rows,
                   "validation": validation, "skipped_themes": out["skipped_themes"]})


def list_baselines() -> dict:
    """Every theme's reference companies, with the evidence and audit trail behind each one."""
    out = {}
    for name, th in load_themes().items():
        if "error" in th:
            out[name] = {"status": "not built", "how_to_build": th["error"]}
            continue
        snap = th.get("snapshot", {})
        out[name] = {"status": "built", "plain_name": th.get("plain_name", name),
                     "built_at": snap.get("built_at"), "source": snap.get("source", "manual"),
                     "members": snap.get("members") or [
                         {"tier": c["name"], **m} for c in th["categories"] for m in c["members"]],
                     "excluded": snap.get("excluded", []), "changes": snap.get("changes", [])}
    return _clean(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "fmp"
    args = [a for a in args if a != mode]
    holdings = [{"ticker": a.split(":")[0], "weight": float(a.split(":")[1])} for a in args]
    print(json.dumps(run_screen(holdings, mode=mode), indent=2, default=str))
