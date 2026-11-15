"""Tests for the theme files and their loader."""

import copy

import pytest
import yaml

from engine import themes
from engine.themes import ThemeError

# ---- the real theme files ----

ALL = themes.load_all()


def test_all_ten_themes_load_in_order():
    assert list(ALL) == ["ai", "oil", "interest_rates", "gold", "defense", "healthcare",
                         "industrial_metals", "clean_energy", "consumer_discretionary",
                         "cybersecurity"]


def test_ai_matches_wes_reference_set_exactly():
    ai = ALL["ai"]
    high = {r.ticker: r.evidence_pct for r in ai.references["High"]}
    moderate = {r.ticker: r.evidence_pct for r in ai.references["Moderate"]}
    assert high == {"NVDA": 90, "MU": 55.5, "VRT": 50, "AVGO": 49}
    assert moderate == {"TSM": 18, "MSFT": 11.2, "VST": 8.6}
    assert ai.control.ticker == "ADM" and ai.control.evidence_pct == 0
    assert {d.ticker: d.tier for d in ai.direct} == {
        "CRWV": "High", "GOOGL": "High", "JPM": "Moderate", "META": "Moderate",
        "TSLA": "Moderate"}
    assert next(d for d in ai.direct if d.ticker == "CRWV").evidence_pct == 100


@pytest.mark.parametrize("key", [k for k in ALL if k != "ai"])
def test_other_themes_follow_the_selection_rules(key):
    theme = ALL[key]
    assert theme.rule_warnings() == []
    assert theme.ground_truth is not None
    for group in themes.REFERENCE_GROUPS:
        for ref in theme.references[group]:
            assert ref.fiscal_year is not None and "FMP" in ref.source


def test_no_ai_reference_reused_as_a_reference_elsewhere():
    ai_refs = set(ALL["ai"].reference_tickers)
    for key, theme in ALL.items():
        if key != "ai":
            assert not ai_refs & set(theme.reference_tickers), key


def test_interest_rates_setup():
    rates = ALL["interest_rates"]
    assert rates.ground_truth == "TLT" and rates.ground_truth_sign == -1
    assert rates.market_controls == ("SPY",)


def test_checkpoint_test_stocks_are_not_references():
    """SMH, XOM and JNJ are Checkpoint 3 test cases, so they must go through regression."""
    for theme in ALL.values():
        for ticker in ("SMH", "XOM", "JNJ"):
            assert theme.listed_tier(ticker) is None


def test_listed_tier():
    ai = ALL["ai"]
    assert ai.listed_tier("nvda") == "High"
    assert ai.listed_tier("TSM") == "Moderate"
    assert ai.listed_tier("META") == "Moderate"
    assert ai.listed_tier("ADM") is None  # the control is scored by regression like anyone
    assert ai.listed_tier("XOM") is None


def test_summary_tables_print(capsys):
    assert themes.main() == 0
    out = capsys.readouterr().out
    assert out.count("## ") == 10
    assert "ground truth: TLT, sign flipped" in out and "Market controls: SPY" in out


# ---- validation of malformed files ----

BASE = {
    "name": "Test",
    "order": 1,
    "ground_truth": "ETF",
    "references": {
        "High": [{"ticker": "AAA", "evidence_pct": 80, "measures": "m", "fiscal_year": 2025,
                  "source": "s", "reason": "r"}],
        "Moderate": [{"ticker": "BBB", "evidence_pct": 20, "measures": "m", "fiscal_year": 2025,
                      "source": "s", "reason": "r"}],
    },
    "control": {"ticker": "CCC", "evidence_pct": 0, "measures": "m", "fiscal_year": 2025,
                "source": "s", "reason": "r"},
    "direct_classification": [{"ticker": "DDD", "tier": "High", "source": "s", "reason": "r"}],
}


def write(tmp_path, doc, name="test.yaml"):
    path = tmp_path / name
    path.write_text(doc if isinstance(doc, str) else yaml.safe_dump(doc))
    return path


def mutate(**changes):
    doc = copy.deepcopy(BASE)
    for dotted, value in changes.items():
        target = doc
        *parents, last = dotted.split("__")
        for p in parents:
            target = target[int(p)] if isinstance(target, list) else target[p]
        if isinstance(target, list):
            last = int(last)
        if value is DELETE:
            del target[last]
        else:
            target[last] = value
    return doc


DELETE = object()


def test_valid_base_loads(tmp_path):
    theme = themes.load_theme(write(tmp_path, BASE))
    assert theme.key == "test" and theme.reference_tickers == ["AAA", "BBB"]
    assert theme.listed_tier("ddd") == "High"
    assert theme.rule_warnings() == ["High group has 1 names (rule: 3-5).",
                                     "Moderate group has 1 names (rule: 2-4)."]


def test_lowercase_tickers_normalized(tmp_path):
    doc = mutate(references__High__0__ticker=" aaa ")
    assert themes.load_theme(write(tmp_path, doc)).reference_tickers[0] == "AAA"


@pytest.mark.parametrize(
    "doc, message",
    [
        ("name: [unclosed", "not valid YAML"),
        ("- just\n- a list\n", "must be a YAML mapping"),
        (mutate(name=DELETE), "needs 'name'"),
        (mutate(references=DELETE), "needs a 'references' section"),
        (mutate(references__Moderate=[]), "references.Moderate needs at least one"),
        (mutate(references__Inverse=[]), "no Inverse tier"),
        (mutate(references__High__0__evidence_pct=0), "0% evidence"),
        (mutate(references__High__0__evidence_pct=150), "between 0 and 100"),
        (mutate(references__High__0__evidence_pct=True), "must be a number"),
        (mutate(references__High__0__evidence_pct="80"), "must be a number"),
        (mutate(references__High__0__ticker=""), "missing ticker"),
        (mutate(references__High__0__source=DELETE), "needs 'source'"),
        (mutate(references__High__0__fiscal_year=25), "fiscal_year"),
        (mutate(references__High__0="AAA"), "must be a mapping"),
        (mutate(control__evidence_pct=5), "control must have 0%"),
        (mutate(direct_classification="DDD"), "must be a list"),
        (mutate(direct_classification__0__tier="Limited"), "tier must be High or Moderate"),
        (mutate(direct_classification__0="DDD"), "must be a mapping"),
        (mutate(direct_classification__0__evidence_pct=-1), "between 0 and 100"),
        (mutate(direct_classification__0__ticker="AAA"), "listed more than once"),
        (mutate(control__ticker="BBB"), "listed more than once"),
        (mutate(ground_truth="AAA"), "validation only"),
        (mutate(references__High__0__ticker="SPY"), "market controls"),
        (mutate(ground_truth_sign=2), "ground_truth_sign"),
        (mutate(market_controls=["TLT"]), "must include SPY"),
        (mutate(market_controls=["SPY", "QQQ"]), "must include SPY"),
        (mutate(order="first"), "order must be a whole number"),
    ],
)
def test_malformed_theme_files_rejected(tmp_path, doc, message):
    with pytest.raises(ThemeError, match=message):
        themes.load_theme(write(tmp_path, doc))


def test_optional_fields(tmp_path):
    doc = mutate(ground_truth=DELETE, direct_classification=DELETE, order=DELETE)
    doc["description"] = "  A test theme.  "
    theme = themes.load_theme(write(tmp_path, doc))
    assert theme.ground_truth is None and theme.direct == [] and theme.order == 999
    assert theme.description == "A test theme."


def test_summary_table_shows_every_role(tmp_path):
    doc = mutate(ground_truth_sign=-1, market_controls=["SPY"])
    doc["direct_classification"][0]["evidence_pct"] = 100
    table = themes.summary_table(themes.load_theme(write(tmp_path, doc)))
    for text in ("ground truth: ETF, sign flipped", "Market controls: SPY", "High (Tier 1)",
                 "Moderate (Tier 1)", "Control", "Direct High (Tier 2)", "WARNING: High group"):
        assert text in table


def test_load_all_orders_by_order_field(tmp_path):
    write(tmp_path, mutate(name="Second", order=2), "b.yaml")
    write(tmp_path, mutate(name="First", order=1), "z.yaml")
    assert [t.name for t in themes.load_all(tmp_path).values()] == ["First", "Second"]


def test_main_reports_errors_and_empty_folder(tmp_path, monkeypatch, capsys):
    original = themes.load_all
    monkeypatch.setattr(themes, "load_all", lambda: original(tmp_path))
    assert themes.main() == 1
    assert "No theme files" in capsys.readouterr().out
    write(tmp_path, "name: [broken")
    assert themes.main() == 1
    assert "Error: test.yaml" in capsys.readouterr().err
