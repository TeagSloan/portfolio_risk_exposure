"""Loads and checks the theme files in themes/.

A theme file (YAML) lists:
- references: High and Moderate groups of companies with a DISCLOSED exposure number
  (Tier 1). Their daily returns are the regression inputs.
- control: one company with zero exposure and no indirect link. Also a regression input,
  but never part of a group's sum; its beta should come out near zero.
- direct_classification: companies that are clearly exposed but have no disclosed number
  (Tier 2). They get their listed tier directly and are never regression inputs.
- ground_truth: optional ETF used ONLY to validate the references, never as one.

Print a summary table of every theme:

    python -m engine.themes
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
THEMES_DIR = PROJECT_ROOT / "themes"

TIERS = ("High", "Moderate", "Limited", "Limited (lower confidence)", "Not determined")
REFERENCE_GROUPS = ("High", "Moderate")
MARKET_CONTROLS = ("SPY", "TLT")
# Selection rules for themes (checked, reported as warnings).
GROUP_SIZE_RULES = {"High": (3, 5), "Moderate": (2, 4)}


class ThemeError(ValueError):
    """A theme file is malformed. The message names the file and the problem."""


@dataclass(frozen=True)
class Reference:
    ticker: str
    evidence_pct: float
    measures: str
    fiscal_year: int | None
    source: str
    reason: str


@dataclass(frozen=True)
class DirectEntry:
    ticker: str
    tier: str
    measures: str
    source: str
    reason: str
    evidence_pct: float | None = None


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    description: str
    order: int
    references: dict  # group name -> list[Reference]
    control: Reference
    direct: list = field(default_factory=list)  # list[DirectEntry]
    ground_truth: str | None = None
    ground_truth_sign: int = 1
    market_controls: tuple = MARKET_CONTROLS

    @property
    def reference_tickers(self):
        return [r.ticker for group in REFERENCE_GROUPS for r in self.references[group]]

    def listed_tier(self, ticker):
        """The tier a reference or direct-list company gets without regression, else None."""
        ticker = ticker.upper()
        for group in REFERENCE_GROUPS:
            if any(r.ticker == ticker for r in self.references[group]):
                return group
        for entry in self.direct:
            if entry.ticker == ticker:
                return entry.tier
        return None

    def rule_warnings(self):
        """Selection rules from the project brief that this theme does not meet."""
        warnings = []
        for group, (low, high) in GROUP_SIZE_RULES.items():
            n = len(self.references[group])
            if not low <= n <= high:
                warnings.append(f"{group} group has {n} names (rule: {low}-{high}).")
        return warnings


# ---------------------------------------------------------------------------
# Loading and validation
# ---------------------------------------------------------------------------

def _require(condition, path, message):
    if not condition:
        raise ThemeError(f"{path.name}: {message}")


def _ticker(value, path, where):
    _require(isinstance(value, str) and value.strip(), path, f"{where} has a missing ticker.")
    return value.strip().upper()


def _text(entry, key, path, where, required=True):
    value = entry.get(key)
    if value is None and not required:
        return ""
    _require(isinstance(value, str) and value.strip(), path, f"{where} needs '{key}'.")
    return value.strip()


def _pct(value, path, where):
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), path,
             f"{where} evidence_pct must be a number.")
    _require(0 <= value <= 100, path, f"{where} evidence_pct must be between 0 and 100.")
    return float(value)


def _reference(entry, path, where):
    _require(isinstance(entry, dict), path, f"{where} must be a mapping.")
    ticker = _ticker(entry.get("ticker"), path, where)
    where = f"{where} ({ticker})"
    year = entry.get("fiscal_year")
    _require(year is None or (isinstance(year, int) and 1990 <= year <= 2100), path,
             f"{where} fiscal_year must be a year or blank.")
    return Reference(
        ticker=ticker,
        evidence_pct=_pct(entry.get("evidence_pct"), path, where),  # control checked later
        measures=_text(entry, "measures", path, where),
        fiscal_year=year,
        source=_text(entry, "source", path, where),
        reason=_text(entry, "reason", path, where),
    )


def _direct(entry, path, where):
    _require(isinstance(entry, dict), path, f"{where} must be a mapping.")
    ticker = _ticker(entry.get("ticker"), path, where)
    where = f"{where} ({ticker})"
    tier = entry.get("tier")
    _require(tier in REFERENCE_GROUPS, path,
             f"{where} tier must be High or Moderate (direct entries are exposed).")
    pct = entry.get("evidence_pct")
    return DirectEntry(
        ticker=ticker,
        tier=tier,
        measures=_text(entry, "measures", path, where, required=False),
        source=_text(entry, "source", path, where),
        reason=_text(entry, "reason", path, where),
        evidence_pct=None if pct is None else _pct(pct, path, where),
    )


def load_theme(path):
    """Read and check one theme file."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ThemeError(f"{path.name}: not valid YAML ({exc.__class__.__name__}).") from exc
    _require(isinstance(raw, dict), path, "the file must be a YAML mapping.")

    name = _text(raw, "name", path, "theme")
    refs_raw = raw.get("references")
    _require(isinstance(refs_raw, dict), path, "needs a 'references' section.")
    references = {}
    for group in REFERENCE_GROUPS:
        entries = refs_raw.get(group)
        _require(isinstance(entries, list) and entries, path,
                 f"references.{group} needs at least one company.")
        references[group] = [_reference(e, path, f"references.{group}[{i}]")
                             for i, e in enumerate(entries)]
        empty = [r.ticker for r in references[group] if r.evidence_pct <= 0]
        _require(not empty, path,
                 f"references.{group} {empty} have 0% evidence; a reference needs a disclosed, "
                 "positive exposure number.")
    extra = set(refs_raw) - set(REFERENCE_GROUPS)
    _require(not extra, path, f"unknown reference group(s): {sorted(extra)}. "
             "Only High and Moderate (there is no Inverse tier).")

    control = _reference(raw.get("control"), path, "control")
    _require(control.evidence_pct == 0, path, "the control must have 0% exposure.")

    direct_raw = raw.get("direct_classification") or []
    _require(isinstance(direct_raw, list), path, "direct_classification must be a list.")
    direct = [_direct(e, path, f"direct_classification[{i}]") for i, e in enumerate(direct_raw)]

    truth = raw.get("ground_truth")
    truth = None if truth is None else _ticker(truth, path, "ground_truth")
    sign = raw.get("ground_truth_sign", 1)
    _require(sign in (1, -1), path, "ground_truth_sign must be 1 or -1.")

    controls = tuple(raw.get("market_controls", MARKET_CONTROLS))
    _require(set(controls) <= set(MARKET_CONTROLS) and "SPY" in controls, path,
             "market_controls must include SPY and may only contain SPY and TLT.")

    all_tickers = ([r.ticker for g in REFERENCE_GROUPS for r in references[g]]
                   + [control.ticker] + [d.ticker for d in direct])
    duplicates = sorted({t for t in all_tickers if all_tickers.count(t) > 1})
    _require(not duplicates, path, f"tickers listed more than once: {duplicates}.")
    _require(truth not in all_tickers, path,
             "the ground truth is for validation only and cannot also be a reference.")
    _require(not set(all_tickers) & set(controls), path,
             "SPY/TLT are market controls and cannot be references.")

    order = raw.get("order", 999)
    _require(isinstance(order, int), path, "order must be a whole number.")
    return Theme(
        key=path.stem,
        name=name,
        description=_text(raw, "description", path, "theme", required=False),
        order=order,
        references=references,
        control=control,
        direct=direct,
        ground_truth=truth,
        ground_truth_sign=sign,
        market_controls=controls,
    )


def load_all(themes_dir=THEMES_DIR):
    """Every theme in the folder, keyed by file name (e.g. 'ai', 'oil'), in display order."""
    themes = [load_theme(p) for p in sorted(Path(themes_dir).glob("*.yaml"))]
    return {t.key: t for t in sorted(themes, key=lambda t: (t.order, t.key))}


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def summary_table(theme):
    """Plain-text table of one theme: who is in it, the evidence, and why."""
    lines = [f"## {theme.name}" + (f"  (ground truth: {theme.ground_truth}"
                                   + (", sign flipped" if theme.ground_truth_sign < 0 else "")
                                   + ")" if theme.ground_truth else "")]
    if theme.market_controls != MARKET_CONTROLS:
        lines.append(f"Market controls: {', '.join(theme.market_controls)}")
    header = f"{'Role':<26}{'Ticker':<7}{'Evid.':>7}  {'FY':<5}{'Measures':<44}Reason"
    lines += [header, "-" * len(header)]

    def row(role, ticker, pct, fy, measures, reason):
        pct_text = "" if pct is None else f"{pct:g}%"
        fy_text = "" if fy is None else str(fy)
        lines.append(f"{role:<26}{ticker:<7}{pct_text:>7}  {fy_text:<5}{measures[:43]:<44}{reason}")

    for group in REFERENCE_GROUPS:
        for r in theme.references[group]:
            row(f"{group} (Tier 1)", r.ticker, r.evidence_pct, r.fiscal_year, r.measures, r.reason)
    c = theme.control
    row("Control", c.ticker, c.evidence_pct, c.fiscal_year, c.measures, c.reason)
    for d in theme.direct:
        row(f"Direct {d.tier} (Tier 2)", d.ticker, d.evidence_pct, None, d.measures, d.reason)
    for warning in theme.rule_warnings():
        lines.append(f"WARNING: {warning}")
    return "\n".join(lines)


def main(argv=None):
    try:
        themes = load_all()
    except ThemeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if not themes:
        print("No theme files found in themes/.")
        return 1
    print("\n\n".join(summary_table(t) for t in themes.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
