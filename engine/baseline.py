"""Live baseline: build a theme's reference set from SEC EDGAR filings instead of hardcoding it.

Pipeline (for a theme whose YAML has baseline_source: sec_live):
  1. Candidates   - the tickers listed in the theme YAML.
  2. Disclosure   - for each candidate, pull its SIC industry code (EDGAR submissions API) and,
                    where a rule needs it, XBRL facts from its latest 10-K (EDGAR companyfacts API).
  3. Tier by rule - the YAML `rules` map SIC codes / disclosed shares to High, Moderate, Inverse,
                    Control. No tier is assigned by hand.
  4. Audit trail  - every member records the filing (form, date, accession, URL) that put it there,
                    and the snapshot records what changed since the previous build.

SEC asks every client to identify itself: set the SEC_USER_AGENT environment variable to
"Your Name your@email.com" before running a live build.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "data" / "baselines"
SEC = "https://data.sec.gov"
FUEL_TAGS = ["AircraftFuelAndRelatedTaxes", "FuelCosts", "AircraftFuel"]
REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "OperatingRevenue"]

# Used only by --offline builds (no internet). Clearly marked as NOT live in the snapshot.
OFFLINE_SIC = {"EOG": 1311, "OXY": 1311, "DVN": 1311, "COP": 1311, "FANG": 1311, "APA": 1311,
               "SLB": 1389, "HAL": 1389, "BKR": 3533, "DAL": 4512, "UAL": 4512, "AAL": 4512,
               "LUV": 4512, "ADBE": 7372, "ORCL": 7372}


def _get(url: str) -> dict:
    from .fmp import _load_dotenv
    _load_dotenv()
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError('Set SEC_USER_AGENT, e.g. export SEC_USER_AGENT="Your Name you@email.com"')
    time.sleep(0.15)  # stay well under SEC's 10 requests/second limit
    r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
    r.raise_for_status()
    return r.json()


def _cik_map() -> dict[str, int]:
    data = _get("https://www.sec.gov/files/company_tickers.json")
    return {v["ticker"].upper(): int(v["cik_str"]) for v in data.values()}


def _latest_annual(facts: dict, tags: list[str]) -> dict | None:
    """Most recent full-year 10-K value for the first tag the company reports."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = gaap.get(tag, {}).get("units", {}).get("USD", [])
        annual = [u for u in units if u.get("form") == "10-K" and u.get("fp") == "FY"
                  and u.get("start") and u.get("end")
                  and (datetime.fromisoformat(u["end"]) - datetime.fromisoformat(u["start"])).days > 300]
        if annual:
            best = max(annual, key=lambda u: (u["end"], u.get("filed", "")))
            return {"tag": tag, **best}
    return None


def _apply_rules(sic: int | None, fuel_share: float | None, rules: dict,
                 offline: bool = False) -> tuple[str | None, str]:
    for tier in ["High", "Moderate", "Inverse", "Control"]:
        rule = rules.get(tier)
        if not rule or sic not in rule.get("sic", []):
            continue
        need = rule.get("min_fuel_cost_share")
        if need is not None and offline:
            return tier, f"SIC {sic} is in the {tier} rule (fuel-cost share check pending a live SEC build)"
        if need is not None:
            if fuel_share is None:
                return None, f"SIC {sic} matches {tier}, but no fuel-cost disclosure was found"
            if fuel_share < need:
                return None, f"fuel cost {fuel_share:.0%} of revenue is below the {need:.0%} rule"
            return tier, f"SIC {sic} and fuel cost {fuel_share:.0%} of revenue (rule: >= {need:.0%})"
        return tier, f"SIC {sic} is in the {tier} rule"
    return None, f"SIC {sic} matches no rule"


def build_baseline(theme: dict, offline: bool = False) -> dict:
    rules, members, excluded = theme["rules"], [], []
    cik = {} if offline else _cik_map()
    for t in theme["candidates"]:
        rec = {"ticker": t}
        try:
            if offline:
                sic, sic_desc, filing, fuel_share = OFFLINE_SIC.get(t), "", {}, None
            else:
                sub = _get(f"{SEC}/submissions/CIK{cik[t]:010d}.json")
                sic, sic_desc = int(sub.get("sic") or 0) or None, sub.get("sicDescription", "")
                recent = sub["filings"]["recent"]
                i = next((k for k, f in enumerate(recent["form"]) if f == "10-K"), None)
                filing = {} if i is None else {
                    "form": "10-K", "filing_date": recent["filingDate"][i],
                    "accession": recent["accessionNumber"][i],
                    "url": (f"https://www.sec.gov/Archives/edgar/data/{cik[t]}/"
                            f"{recent['accessionNumber'][i].replace('-', '')}/{recent['primaryDocument'][i]}")}
                fuel_share = None
                if any("min_fuel_cost_share" in (r or {}) for r in rules.values()) and sic == 4512:
                    facts = _get(f"{SEC}/api/xbrl/companyfacts/CIK{cik[t]:010d}.json")
                    fuel, rev = _latest_annual(facts, FUEL_TAGS), _latest_annual(facts, REVENUE_TAGS)
                    if fuel and rev and rev["val"]:
                        fuel_share = fuel["val"] / rev["val"]
                        rec["fuel_fact"] = {"fuel_tag": fuel["tag"], "fuel_usd": fuel["val"],
                                            "revenue_tag": rev["tag"], "revenue_usd": rev["val"],
                                            "fiscal_year_end": fuel["end"]}
            tier, why = _apply_rules(sic, fuel_share, rules, offline)
            rec.update({"sic": sic, "sic_description": sic_desc, "rule": why, **filing})
            if fuel_share is not None:
                rec["evidence_pct"] = round(100 * fuel_share, 1)
            (members if tier else excluded).append({**rec, "tier": tier})
        except Exception as e:  # one bad candidate shouldn't kill the build
            excluded.append({**rec, "tier": None, "rule": f"error: {e}"})

    snapshot = {
        "theme": theme["name"],
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "OFFLINE FALLBACK - not live SEC data" if offline else "SEC EDGAR (live)",
        "members": members, "excluded": excluded,
    }
    snapshot["changes"] = _diff(theme["name"], members)
    return snapshot


def _diff(theme_name: str, members: list[dict]) -> list[str]:
    prev_path = BASELINES / f"{theme_name.lower().replace(' ', '_')}.json"
    if not prev_path.exists():
        return ["First build - no previous snapshot to compare."]
    prev = {m["ticker"]: m["tier"] for m in json.loads(prev_path.read_text())["members"]}
    now = {m["ticker"]: m["tier"] for m in members}
    out = [f"{t}: added as {now[t]}" for t in now.keys() - prev.keys()]
    out += [f"{t}: removed (was {prev[t]})" for t in prev.keys() - now.keys()]
    out += [f"{t}: {prev[t]} -> {now[t]}" for t in now.keys() & prev.keys() if prev[t] != now[t]]
    return out or ["No membership changes since the last build."]


def save_snapshot(snapshot: dict) -> Path:
    BASELINES.mkdir(parents=True, exist_ok=True)
    path = BASELINES / f"{snapshot['theme'].lower().replace(' ', '_')}.json"
    path.write_text(json.dumps(snapshot, indent=2))
    return path


def snapshot_to_theme(theme: dict, snapshot: dict) -> dict:
    """Turn a built snapshot into the categories format the regression engine expects."""
    cats = []
    tier_specs = theme.get("tiers", {})
    for tier, default_dir in [("High", "positive"), ("Moderate", "positive"), ("Inverse", "inverse")]:
        direction = tier_specs.get(tier, {}).get("direction", default_dir)
        mem = [{"ticker": m["ticker"], "evidence_pct": m.get("evidence_pct"),
                "evidence_type": m.get("evidence_type") or ("cost" if tier == "Inverse" else "industry (SIC)"),
                "note": m.get("rule", ""), "source": m.get("url") or m.get("source", "")}
               for m in snapshot["members"] if m["tier"] == tier]
        if mem:
            cats.append({"name": tier, "direction": direction, "members": mem})
    control = [{"ticker": m["ticker"], "note": m.get("rule", "")}
               for m in snapshot["members"] if m["tier"] == "Control"]
    return {**theme, "categories": cats, "control": control, "snapshot": snapshot}
