"""One baseline builder for every theme (baseline_source: fmp_rules).

For each tier in the theme YAML (High / Moderate / Inverse / Control):

  1. CANDIDATES   FMP stock screener (sector/industry, min market cap) plus any listed tickers.
                  If the screener isn't in your FMP plan, the listed tickers are used alone.
  2. FUNDAMENTALS Each candidate must pass the tier's filing-based tests:
                    industry_contains  - FMP industry text contains a keyword
                    require            - segment_share (geographic/product revenue share) or
                                         ratio (any two income-statement fields, e.g. netInterestIncome/revenue)
  3. PRICE CHECK  The stock numbers must agree with the fundamentals:
                    - theme has a ground-truth price (USO, DBB, XLV, TLT...): the reference must move with
                      it in the expected direction (t >= 2, after controlling for SPY); controls must NOT (|t| < 2)
                    - no ground truth: it must move with the rest of its tier (residual correlation >= 0.25)
  4. CAP          Keep the top `max_per_tier` by evidence strength, then market cap. Small, clean
                  reference groups keep the regression stable and the Bonferroni threshold reasonable.

manual_members in the YAML add names the rules can't capture (e.g. CHGG for AI disruption). They are
labeled "manual" in the audit trail. Every decision - kept or excluded - is recorded with its reason.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import fmp
from .baseline import _diff
from .data import get_returns

TIER_ORDER = ["High", "Moderate", "Inverse", "Control"]


def _num(d: dict, *keys) -> float | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _candidates(spec: dict, min_cap: float, notes: list[str]) -> dict[str, dict]:
    """ticker -> screener row (or {} if it came from the explicit list)."""
    out: dict[str, dict] = {}
    screen = spec.get("candidates", {}).get("screen")
    if screen:
        try:
            for row in fmp.screener(sector=screen.get("sector"), industry=screen.get("industry"),
                                    min_market_cap=screen.get("min_market_cap", min_cap)):
                if row.get("symbol"):
                    out[row["symbol"]] = row
        except Exception as e:
            notes.append(f"screener unavailable ({str(e)[:80]}); used listed tickers only")
    for t in spec.get("candidates", {}).get("tickers", []):
        out.setdefault(t, {})
    for t in spec.get("exclude", []):
        out.pop(t, None)
    return out


def _evidence(ticker: str, row: dict, spec: dict) -> tuple[bool, dict]:
    """Run the tier's fundamental tests. Returns (passed, evidence record)."""
    info = row if row.get("industry") else fmp.profile(ticker)
    industry = info.get("industry") or ""
    rec = {"ticker": ticker, "company": info.get("companyName", ""), "industry": industry,
           "sector": info.get("sector", ""), "market_cap": _num(info, "marketCap", "mktCap")}

    words = [w.lower() for w in spec.get("industry_contains", [])]
    if words and not any(w in industry.lower() for w in words):
        return False, {**rec, "rule": f"industry '{industry}' doesn't match {words}"}

    reasons = [f"industry: {industry}"] if words else []
    for req in spec.get("require", []):
        if req["metric"] == "segment_share":
            res = fmp.segment_share(ticker, req["kind"], req["match"])
            if res is None:
                return False, {**rec, "rule": f"no {req['kind']} segment data"}
            hidden = [k for k in res["all_segments"]
                      if any(a.lower() in k.lower() for a in req.get("ambiguous", []))]
            if res["share"] == 0 and hidden:
                return False, {**rec, "rule": f"exposure not broken out: reports only {', '.join(hidden)}"}
            val, label = res["share"], f"{req['kind']} revenue matching {req['match']}"
            rec.update({"fiscal_year": res["fiscal_year"], "matched_segments": res["matched"]})
        elif req["metric"] == "ratio":
            inc = fmp.income_statement(ticker)
            num, den = _num(inc, req["numerator"]), _num(inc, req["denominator"])
            if num is None or not den:
                return False, {**rec, "rule": f"income statement lacks {req['numerator']}/{req['denominator']}"}
            val, label = num / den, f"{req['numerator']} / {req['denominator']}"
            rec.update({"fiscal_year": inc.get("fiscalYear") or str(inc.get("date", ""))[:4],
                        "filing_date": inc.get("filingDate", "")})
        else:
            raise ValueError(f"unknown metric {req['metric']}")
        lo, hi = req.get("min"), req.get("max")
        if (lo is not None and val < lo) or (hi is not None and val > hi):
            bound = f">= {lo:.0%}" if lo is not None else f"<= {hi:.0%}"
            return False, {**rec, "evidence_pct": round(100 * val, 1), "rule": f"{label} = {val:.0%} (needs {bound})"}
        rec["evidence_pct"] = round(100 * val, 1)
        rec["evidence_type"] = label
        reasons.append(f"{label} = {val:.0%}")
    rec["rule"] = "; ".join(reasons) or "listed candidate"
    rec["evidence_type"] = rec.get("evidence_type") or ("industry" if words else "listed")
    return True, rec


def _ols_t(y: np.ndarray, X: np.ndarray) -> tuple[float, float]:
    X = np.column_stack([np.ones(len(y)), X])
    xtx_inv = np.linalg.pinv(X.T @ X)
    b = xtx_inv @ X.T @ y
    resid = y - X @ b
    s2 = resid @ resid / (len(y) - X.shape[1])
    return float(b[1]), float(b[1] / np.sqrt(s2 * xtx_inv[1, 1]))


def _price_check(theme: dict, passed: dict[str, list[dict]], price_mode: str) -> None:
    """Annotate each passed record with price_check = (ok, reason)."""
    gt = theme.get("ground_truth") or {}
    # Hand-validated members anchor the group check, so one weak candidate can't sink a strong one.
    anchors = {}
    for m in theme.get("manual_members", []):
        anchors.setdefault(m["tier"], []).append(m["ticker"])
    tickers = sorted({r["ticker"] for recs in passed.values() for r in recs} | {"SPY"} |
                     {a for v in anchors.values() for a in v} | ({gt["ticker"]} if gt else set()))
    rets = get_returns(tickers, mode=price_mode)
    sign = gt.get("sign", 1)

    for tier, recs in passed.items():
        direction = theme["tiers"][tier].get("direction", "positive")
        for r in recs:
            t = r["ticker"]
            if t not in rets:
                r["price_check"] = (False, "no price data")
                continue
            if gt:
                df = rets[[t, gt["ticker"], "SPY"]].dropna()
                if gt["ticker"] == "SPY" or len(df) < 120:
                    r["price_check"] = (False, "not enough price history")
                    continue
                b, tstat = _ols_t(df[t].to_numpy(), df[[gt["ticker"], "SPY"]].to_numpy())
                tstat *= sign
                if tier == "Control":
                    ok = abs(tstat) < 2
                    why = f"no link to {gt['ticker']} (t {tstat:+.1f})" if ok else f"moves with {gt['ticker']} (t {tstat:+.1f}), not a clean control"
                else:
                    want = 1 if direction == "positive" else -1
                    ok = tstat * want >= 2
                    why = (f"price confirms: {'moves with' if want > 0 else 'moves against'} "
                           f"{gt.get('plain', gt['ticker'])} (t {tstat:+.1f})") if ok else \
                          f"price doesn't confirm the {tier} direction (t {tstat:+.1f})"
                r["price_check"] = (ok, why)
            else:
                same = [x for x in [y["ticker"] for y in recs] + anchors.get(tier, [])
                        if x != t and x in rets]
                if tier == "Control" or not same:
                    r["price_check"] = (True, "no group check for this tier")
                    continue
                df = rets[[t, "SPY"] + same].dropna()
                resid = {}
                for c in [t] + same:  # remove the market from each stock
                    beta = np.polyfit(df["SPY"], df[c], 1)[0]
                    resid[c] = df[c] - beta * df["SPY"]
                rho = float(np.corrcoef(resid[t], pd.DataFrame({c: resid[c] for c in same}).mean(axis=1))[0, 1])
                ok = rho >= 0.25
                r["price_check"] = (ok, f"{'moves' if ok else 'does not move'} with the rest of its group "
                                        f"beyond the market (correlation {rho:.2f})")


def build_rules_baseline(theme: dict, price_mode: str = "fmp") -> dict:
    min_cap = float(theme.get("min_market_cap", 2e9))
    cap = int(theme.get("max_per_tier", 4))
    notes: list[str] = []
    passed: dict[str, list[dict]] = {}
    excluded: list[dict] = []
    taken: set[str] = set()

    for tier in [t for t in TIER_ORDER if t in theme["tiers"]]:
        spec = theme["tiers"][tier]
        passed[tier] = []
        for t, row in _candidates(spec, min_cap, notes).items():
            if t in taken:
                continue
            try:
                ok, rec = _evidence(t, row, spec)
            except Exception as e:
                ok, rec = False, {"ticker": t, "rule": f"error: {str(e)[:120]}"}
            rec["tier_tested"] = tier
            if ok:
                passed[tier].append(rec)
                taken.add(t)
            else:
                excluded.append({**rec, "tier": None})

    # A ticker that failed one tier but passed a later one isn't "excluded".
    excluded = [e for e in excluded if e["ticker"] not in taken]
    _price_check(theme, passed, price_mode)

    members = []
    for tier, recs in passed.items():
        good = [r for r in recs if r["price_check"][0]]
        for r in recs:
            if not r["price_check"][0]:
                excluded.append({**r, "tier": None, "rule": f"{r['rule']}; REJECTED: {r['price_check'][1]}"})
        good.sort(key=lambda r: (r.get("evidence_pct") or 0, r.get("market_cap") or 0), reverse=True)
        for i, r in enumerate(good):
            r = {**r, "price_check": r["price_check"][1]}
            if i < cap:
                members.append({**r, "tier": tier, "source": f"FMP ({r.get('evidence_type', '')})"})
            else:
                excluded.append({**r, "tier": None, "rule": f"{r['rule']}; passed but over the {cap}-per-tier cap"})

    for m in theme.get("manual_members", []):
        members.append({**m, "rule": f"manual: {m.get('note', '')}", "evidence_type": m.get("evidence_type", "manual"),
                        "price_check": "not checked (manual)", "source": "hand-validated disclosure"})

    return {
        "theme": theme["name"],
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": f"FMP rules (live){'; ' + '; '.join(dict.fromkeys(notes)) if notes else ''}",
        "members": members, "excluded": excluded,
        "changes": _diff(theme["name"], members),
    }
