"""Rebuilds themes 2-9 (everything except AI and Oil) from FMP data.

Every evidence % is computed here from FMP segment revenue or income statements, never
typed in by hand, so each number can be re-derived. WARNING: this OVERWRITES the eight
YAML files in themes/; hand edits to them will be lost.

    python -m scripts.build_theme_evidence
"""

from pathlib import Path

import yaml

from engine import fmp

THEMES_DIR = Path(__file__).resolve().parents[1] / "themes"


def seg(ticker, include=None, exclude=None, measures="", reason=""):
    r = fmp.revenue_product_segmentation(ticker)[0]
    data = {k: v for k, v in r["data"].items() if isinstance(v, (int, float))}
    total = sum(data.values())
    keys = [
        k
        for k in data
        if (include is None or any(s.lower() in k.lower() for s in include))
        and not (exclude and any(s.lower() in k.lower() for s in exclude))
    ]
    part = sum(data[k] for k in keys)
    named = "all reported segments" if include is None and not exclude else ", ".join(keys)
    return {
        "ticker": ticker,
        "evidence_pct": round(100 * part / total, 1),
        "measures": measures,
        "fiscal_year": int(r["fiscalYear"]),
        "source": f"FMP revenue-product-segmentation FY{r['fiscalYear']}: {named} "
        f"(${part / 1e9:,.2f}B of ${total / 1e9:,.2f}B)",
        "reason": reason,
    }


def nii(ticker, reason):
    r = fmp.income_statement(ticker, limit=1)[0]
    return {
        "ticker": ticker,
        "evidence_pct": round(100 * r["netInterestIncome"] / r["revenue"], 1),
        "measures": "Net interest income share of revenue",
        "fiscal_year": int(r["fiscalYear"]),
        "source": f"FMP income-statement FY{r['fiscalYear']}: net interest income "
        f"${r['netInterestIncome'] / 1e9:,.2f}B of revenue ${r['revenue'] / 1e9:,.2f}B",
        "reason": reason,
    }


def control(ticker, measures, reason, fy=2025):
    return {
        "ticker": ticker,
        "evidence_pct": 0,
        "measures": measures,
        "fiscal_year": fy,
        "source": f"FMP profile: {fmp.profile(ticker)['industry']}",
        "reason": reason,
    }


def direct(ticker, tier, reason, measures=None):
    d = {
        "ticker": ticker,
        "tier": tier,
        "source": f"FMP profile: {fmp.profile(ticker)['industry']}",
        "reason": reason,
    }
    if measures:
        d["measures"] = measures
    return d


def build_specs():
    """Theme definitions, with evidence pulled from FMP (cached)."""
    return {
        "interest_rates": dict(
            order=2,
            name="Interest rates",
            ground_truth="TLT",
            ground_truth_sign=-1,
            market_controls=["SPY"],
            description=(
                "Banks that earn more when interest rates rise "
                "(lending income is a large share of revenue)."
            ),
            High=[
                nii("MTB", "Regional bank; lending income dominates and loans reprice with rates."),
                nii("EWBC", "Commercial lender with mostly floating-rate loans."),
                nii("WAL", "Business-focused bank whose loan yields track rates."),
                nii("ZION", "Western regional bank known for asset-sensitive balance sheet."),
            ],
            Moderate=[
                nii("PNC", "Large regional bank with bigger fee businesses."),
                nii("USB", "Big diversified bank; payments and fees dilute rate sensitivity."),
            ],
            control=control(
                "ADM",
                "Net interest income share of revenue",
                "Crop processor with no lending business.",
            ),
            direct=[],
        ),
        "gold": dict(
            order=3,
            name="Gold & precious metals",
            ground_truth="GLD",
            description="Miners whose revenue comes from selling gold and other precious metals.",
            High=[
                seg(
                    "SSRM",
                    ["gold"],
                    measures="Gold share of revenue",
                    reason="Mid-tier gold miner; silver is most of the rest.",
                ),
                seg(
                    "CDE",
                    ["gold"],
                    measures="Gold share of revenue",
                    reason="US gold and silver producer, gold-weighted.",
                ),
                seg(
                    "NEM",
                    ["dore"],
                    measures=(
                        "Gold dore share of revenue "
                        "(lower bound; concentrate also holds gold)"
                    ),
                    reason="World's largest gold miner.",
                ),
            ],
            Moderate=[
                seg(
                    "HL",
                    ["gold"],
                    measures="Gold share of revenue",
                    reason="Silver-first miner with a meaningful gold stream.",
                ),
                seg(
                    "FCX",
                    ["gold"],
                    measures="Gold share of revenue",
                    reason="Copper miner whose Grasberg mine also produces lots of gold.",
                ),
            ],
            control=control(
                "CTAS",
                "Precious-metals share of revenue",
                "Uniform rental; no metals revenue or input link.",
            ),
            direct=[
                direct("AEM", "High", "Large gold miner; FMP segment data is outdated (2013)."),
                direct("KGC", "High", "Gold miner; no segment revenue in FMP."),
                direct(
                    "WPM", "High", "Precious-metals streaming company; no segment revenue in FMP."
                ),
                direct(
                    "RGLD",
                    "High",
                    "Gold-focused royalty company; FMP shows one royalty segment, no metal split.",
                ),
            ],
        ),
        "defense": dict(
            order=4,
            name="Defense & aerospace",
            ground_truth="ITA",
            description="Contractors whose revenue comes from military and space programs.",
            High=[
                seg(
                    "LMT",
                    measures="Defense/space segments share of revenue",
                    reason="Largest US defense contractor (F-35, missiles, space).",
                ),
                seg(
                    "NOC",
                    measures="Defense/space segments share of revenue",
                    reason="Bombers, space systems and missile defense.",
                ),
                seg(
                    "LHX",
                    measures="Defense/space segments share of revenue",
                    reason="Defense electronics, tactical radios and rocket motors.",
                ),
                seg(
                    "GD",
                    exclude=["aerospace"],
                    measures="Defense segments share of revenue (excludes Gulfstream jets)",
                    reason="Submarines, combat vehicles and defense IT.",
                ),
            ],
            Moderate=[
                seg(
                    "RTX",
                    ["raytheon"],
                    measures="Raytheon (defense) segment share of revenue",
                    reason="Missiles inside a mostly commercial-aerospace group.",
                ),
                seg(
                    "BA",
                    ["defense"],
                    measures="Defense, Space & Security segment share of revenue",
                    reason="Defense unit inside a mainly commercial-jet maker.",
                ),
            ],
            control=control(
                "KO", "Defense share of revenue", "Beverages; no defense customers or suppliers."
            ),
            direct=[],
        ),
        "healthcare": dict(
            order=5,
            name="Healthcare",
            ground_truth="XLV",
            description="Companies selling medicines, medical devices and diagnostics.",
            High=[
                seg(
                    "PFE",
                    ["biopharma"],
                    measures="Biopharma segment share of revenue",
                    reason="Large diversified drug maker.",
                ),
                seg(
                    "MRK",
                    ["pharmaceutical"],
                    measures="Human pharmaceutical segment share of revenue",
                    reason="Large drug maker; animal health is the rest.",
                ),
                seg(
                    "MDT",
                    measures="Medical device segments share of revenue",
                    reason="Largest pure medical-device company.",
                ),
                seg(
                    "ABT",
                    exclude=["nutrition"],
                    measures=(
                        "Devices, diagnostics and pharma share of revenue "
                        "(excludes nutrition)"
                    ),
                    reason="Diversified devices and diagnostics maker.",
                ),
            ],
            Moderate=[
                seg(
                    "ECL",
                    ["life sciences"],
                    measures="Global Life Sciences segment share of revenue",
                    reason="Hygiene company with a unit serving pharma and biotech plants.",
                ),
                seg(
                    "PG",
                    ["health care"],
                    measures="Health Care segment share of revenue",
                    reason="Consumer giant with an oral-care and OTC health unit.",
                ),
            ],
            control=control(
                "CAT",
                "Healthcare share of revenue",
                "Heavy machinery; no healthcare revenue.",
                2025,
            ),
            direct=[],
        ),
        "industrial_metals": dict(
            order=6,
            name="Industrial / EV metals",
            ground_truth="COPX",
            description=(
                "Miners and producers of copper and lithium, "
                "the metals behind electrification and EV batteries."
            ),
            High=[
                seg(
                    "SCCO",
                    ["copper"],
                    measures="Copper share of revenue",
                    reason="Low-cost copper pure-play in Peru and Mexico.",
                ),
                seg(
                    "FCX",
                    ["copper"],
                    measures="Copper share of revenue",
                    reason="Largest US-listed copper miner.",
                ),
                seg(
                    "ALB",
                    ["energy storage"],
                    measures="Energy Storage (lithium) segment share of revenue",
                    reason="Largest lithium producer.",
                ),
                seg(
                    "SQM",
                    ["lithium"],
                    measures="Lithium share of revenue",
                    reason="Chilean lithium producer; iodine and fertilizer are the rest.",
                ),
            ],
            Moderate=[
                seg(
                    "BHP",
                    ["copper"],
                    measures="Copper share of revenue",
                    reason="Diversified miner; iron ore is the other half.",
                ),
                seg(
                    "VALE",
                    ["copper"],
                    measures="Copper share of revenue",
                    reason="Iron-ore giant with a growing copper business.",
                ),
                seg(
                    "RIO",
                    ["copper"],
                    measures="Copper share of revenue",
                    reason="Diversified miner; copper is a small but growing slice.",
                ),
            ],
            control=control(
                "ORLY", "Copper/lithium share of revenue", "Auto-parts retailer; no metals revenue."
            ),
            direct=[
                direct("TECK", "High", "Copper miner; no segment revenue in FMP."),
                direct("HBM", "High", "Copper miner; no segment revenue in FMP."),
            ],
        ),
        "clean_energy": dict(
            order=7,
            name="Clean energy & uranium",
            ground_truth="ICLN",
            description="Solar, renewable power and nuclear fuel companies.",
            High=[
                seg(
                    "FSLR",
                    measures="Solar share of revenue (single solar segment)",
                    reason="Largest US solar-panel maker.",
                ),
                seg(
                    "ENPH",
                    measures="Solar share of revenue (single segment)",
                    reason="Solar microinverters and home batteries.",
                ),
                seg(
                    "NXT",
                    measures="Solar share of revenue (single segment)",
                    reason="Solar tracker pure-play.",
                ),
                seg(
                    "LEU",
                    measures="Nuclear fuel share of revenue (uranium, enrichment, LEU)",
                    reason="US uranium enrichment pure-play.",
                ),
            ],
            Moderate=[
                seg(
                    "NEE",
                    ["neer"],
                    measures="NextEra Energy Resources (renewables) share of revenue",
                    reason="Largest renewable developer inside a regulated utility.",
                ),
                seg(
                    "BWXT",
                    ["commercial"],
                    measures="Commercial (nuclear power) operations share of revenue",
                    reason="Nuclear components; most revenue is naval reactors.",
                ),
            ],
            control=control(
                "HSY", "Clean-energy share of revenue", "Chocolate maker; no energy business."
            ),
            direct=[
                direct("CCJ", "High", "Uranium miner; no segment revenue in FMP."),
                direct(
                    "CEG",
                    "Moderate",
                    "Largest US nuclear fleet; FMP splits revenue by region, not by fuel.",
                ),
            ],
        ),
        "consumer_discretionary": dict(
            order=8,
            name="Consumer discretionary",
            ground_truth="XLY",
            description=(
                "Companies selling things people buy when they feel flush: "
                "homes, apparel, travel."
            ),
            High=[
                seg(
                    "HD",
                    measures="Home-improvement share of revenue (all product categories)",
                    reason="Largest home-improvement retailer.",
                ),
                seg(
                    "LOW",
                    measures="Home-improvement share of revenue (all product categories)",
                    reason="Second-largest home-improvement retailer.",
                ),
                seg(
                    "NKE",
                    ["footwear", "apparel"],
                    measures="Footwear and apparel share of revenue",
                    reason="Largest sportswear brand.",
                ),
                seg(
                    "BKNG",
                    measures="Travel booking share of revenue (all segments)",
                    reason="Largest online travel agency.",
                ),
            ],
            Moderate=[
                seg(
                    "TGT",
                    ["apparel", "hardlines", "home furnishings"],
                    measures="Apparel, hardlines and home share of revenue",
                    reason="Mass retailer; groceries and essentials are the rest.",
                ),
                seg(
                    "COST",
                    ["non-foods"],
                    measures="Non-foods share of revenue",
                    reason="Warehouse club; mostly food and sundries.",
                ),
            ],
            control=control(
                "DUK",
                "Discretionary share of revenue",
                "Regulated electric utility; demand doesn't depend on consumer mood.",
            ),
            direct=[],
        ),
        "cybersecurity": dict(
            order=9,
            name="Cybersecurity",
            ground_truth="CIBR",
            description="Companies selling security software and services.",
            High=[
                seg(
                    "CRWD",
                    measures="Security share of revenue (security-only business)",
                    reason="Endpoint security leader.",
                ),
                seg(
                    "PANW",
                    measures="Security share of revenue (security-only business)",
                    reason="Largest security vendor; firewalls and platforms.",
                ),
                seg(
                    "ZS",
                    measures="Security share of revenue (single segment)",
                    reason="Cloud security pure-play.",
                ),
                seg(
                    "FTNT",
                    measures="Security share of revenue (security-only business)",
                    reason="Firewalls and security subscriptions.",
                ),
            ],
            Moderate=[
                seg(
                    "BB",
                    ["secure communication"],
                    measures="Secure Communications segment share of revenue",
                    reason="BlackBerry's cybersecurity unit beside its QNX car software.",
                ),
                seg(
                    "CSCO",
                    ["security"],
                    measures="Security segment share of revenue",
                    reason="Networking giant with a security segment.",
                ),
            ],
            control=control(
                "WM", "Security share of revenue", "Waste collection; no security business."
            ),
            direct=[
                direct(
                    "AKAM",
                    "Moderate",
                    "Security is roughly half its business, but FMP shows one segment.",
                ),
                direct(
                    "NET",
                    "Moderate",
                    "Security is built into its network; no separate figure in FMP.",
                ),
            ],
        ),
    }


def write_theme(key, t):
    doc = {
        "name": t["name"],
        "order": t["order"],
        "description": t["description"],
        "ground_truth": t["ground_truth"],
    }
    if t.get("ground_truth_sign"):
        doc["ground_truth_sign"] = t["ground_truth_sign"]
    if t.get("market_controls"):
        doc["market_controls"] = t["market_controls"]
    doc["references"] = {"High": t["High"], "Moderate": t["Moderate"]}
    doc["control"] = t["control"]
    doc["direct_classification"] = t["direct"]
    header = (
        f"# {t['name']} theme. Evidence numbers are computed from FMP data "
        "(see each source);\n"
        "# none are estimated. Generated by scripts/build_theme_evidence.py.\n"
    )
    body = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
    (THEMES_DIR / f"{key}.yaml").write_text(header + body)


def main():
    for key, spec in build_specs().items():
        write_theme(key, spec)
        print("wrote", key)


if __name__ == "__main__":
    main()
