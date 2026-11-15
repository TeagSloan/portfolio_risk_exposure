"""Click-through tests for the Streamlit dashboard (app.py) with fake engine results (no internet)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from engine import assistant, builder, monte_carlo, risk, screen, shocks
from engine.regression import HIGH, LIMITED, LIMITED_LOW, MODERATE
from engine.theme_loader import load_all

THEMES = load_all()
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def fake_build(prefs):
    return {
        "preferences": prefs, "universe_size": 3,
        "holdings": [{"ticker": "AAA", "weight_pct": 60.0, "points": 1, "tiers": {"AI": HIGH}, "labels": []},
                     {"ticker": "BBB", "weight_pct": 40.0, "points": 1, "tiers": {"AI": MODERATE},
                      "labels": ["Oil: lower confidence"]}],
        "cash_pct": 0.0, "rejected_by_etf_check": ["ZZZ"], "warnings": ["Only 2 holdings."],
        "verification": {"all_pass": True, "checks": {
            "ai": {"theme": "AI", "choice": "want", "goal": "g", "pass": True, "sentence": "100% is AI."},
            "oil": {"theme": "Oil", "choice": "avoid", "goal": "g", "pass": False, "sentence": "Some oil."}}},
    }


def fake_table():
    result = {"tier": LIMITED, "sentence": "Doesn't rise with it.", "method": "regression", "n_obs": 499,
              "r_squared": 0.4, "controls": ["SPY"], "p_threshold": 0.01,
              "groups": {"High": {"names": ["R1"], "beta_sum": 0.01, "se": 0.02, "p_one_sided": 0.3,
                                  "upper_95": 0.04, "eligible": False}}}
    table = {t: {k: dict(result) for k in THEMES} for t in ("AAA", "BBB")}
    table["AAA"]["ai"]["tier"] = HIGH
    table["BBB"]["ai"]["tier"] = MODERATE
    return table


def fake_risk(holdings):
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2024-11-15", periods=300)
    r = pd.DataFrame({"SPY": rng.normal(0.0004, 0.01, 300), "AAA": rng.normal(0.0006, 0.02, 300),
                      "BBB": rng.normal(0.0002, 0.015, 300)}, index=idx)
    mc = monte_carlo.simulate_from_returns(monte_carlo.to_weights(holdings), r, n_paths=200)
    weights = monte_carlo.to_weights(holdings)
    sens = {t: {"beta": 0.4 if t == "AAA" else -0.1, "se": 0.1, "note": ""} for t in weights}
    shock_list = [shocks.apply_shock(weights, sens, k, th, 0.30).to_dict() for k, th in THEMES.items()]
    report = {"holdings_pct": holdings, "monte_carlo": mc.to_dict(), "shocks": shock_list,
              "frontier": {"available": True, "sentences": ["Mean-variance sentence."]}, "summary": ["Short."]}
    return report, {"fan_chart": monte_carlo.fan_chart(mc), "frontier": None}


@pytest.fixture
def app(monkeypatch):
    st.cache_data.clear()
    st.cache_resource.clear()
    monkeypatch.setattr(builder, "build", fake_build)
    monkeypatch.setattr(builder, "prescreen", fake_table)
    monkeypatch.setattr(risk, "run_risk", fake_risk)
    monkeypatch.setattr(screen, "_screen_one", lambda t, th, s, e: {"tier": MODERATE if th["key"] == "oil"
                                                                    else LIMITED_LOW})
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def build_ai_oil(at):
    at.radio(key="choice_ai").set_value("Want")
    at.radio(key="choice_oil").set_value("Avoid")
    at.sidebar.button[0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_start_page(app):
    assert not app.exception
    assert app.title[0].value == "Theme Funds"
    assert len(app.radio) == len(THEMES)
    assert any("How it works" in m.value for m in app.markdown)


def test_build_needs_at_least_one_choice(app):
    app.sidebar.button[0].click()
    app.run()
    assert "Pick at least one theme" in app.sidebar.warning[0].value


def test_full_fund_view(app):
    build_ai_oil(app)
    assert [t.label for t in app.tabs] == ["Your fund", "Risk", "Ask about your fund", "Launch on Monad"]
    assert any("Want AI" in s.value for s in app.success)
    assert any("Avoid Oil" in e.value for e in app.error)          # the failing re-screen check shows red
    assert any("Only 2 holdings" in w.value for w in app.warning)
    assert any("ZZZ" in c.value for c in app.caption)
    labels = [m.label for m in app.metric]
    assert "Chance of losing >10%" in labels and "Beat SPY" in labels
    assert any("not a forecast" in m.value for m in app.markdown)
    assert any("Mean-variance sentence." in m.value for m in app.markdown)
    assert any("Phase 7" in i.value for i in app.info)


def test_shock_slider_changes_the_answer(app):
    build_ai_oil(app)
    app.selectbox(key="shock_theme").set_value("AI")
    app.select_slider(key="shock_size").set_value(30)
    app.run()
    up = next(m for m in app.metric if m.label.startswith("Estimated portfolio move"))
    app.select_slider(key="shock_size").set_value(-30)
    app.run()
    down = next(m for m in app.metric if m.label.startswith("Estimated portfolio move"))
    assert up.value.startswith("+") and down.value.startswith("-")
    assert up.value[1:] == down.value[1:]


def test_audit_trail_for_any_cell(app):
    build_ai_oil(app)
    app.selectbox(key="audit_ticker").set_value("BBB")
    app.selectbox(key="audit_theme").set_value("AI")
    app.run()
    assert not app.exception
    assert any("Eligible" in str(df.value.columns.tolist()) for df in app.dataframe)


def test_try_adding_xom_is_rejected_in_red(app):
    build_ai_oil(app)
    app.text_input(key="try_ticker").set_value("XOM")
    app.button(key="try_add").click()
    app.run()
    rejection = next(e.value for e in app.error if e.value.startswith("Rejected"))
    assert "Mandate: Oil exposure too high (XOM is Moderate for Oil)." in rejection


def test_chat_streams_an_answer(app, monkeypatch):
    seen = {}

    def fake_ask(question, facts, history):
        seen.update(question=question, facts=facts)
        yield "Your fund holds "
        yield "AAA and BBB."

    monkeypatch.setattr(assistant, "ask", fake_ask)
    build_ai_oil(app)
    app.chat_input[0].set_value("What do I hold?").run()
    assert not app.exception
    assert seen["question"] == "What do I hold?"
    assert seen["facts"]["holdings"][0]["ticker"] == "AAA" and "monte_carlo" in seen["facts"]
    texts = [m.value for msg in app.chat_message for m in msg.markdown]
    assert "What do I hold?" in texts and "Your fund holds AAA and BBB." in texts


def test_chat_error_is_a_message(app, monkeypatch):
    def failing_ask(question, facts, history):
        raise assistant.AssistantError("The Claude helper needs ANTHROPIC_API_KEY in the project's .env file.")
        yield  # pragma: no cover

    monkeypatch.setattr(assistant, "ask", failing_ask)
    build_ai_oil(app)
    app.button(key="example_How bad could a bad year be?").click()
    app.run()
    assert any("ANTHROPIC_API_KEY" in e.value for e in app.error)


def test_builder_error_and_empty_basket(app, monkeypatch):
    def fail(prefs):
        raise builder.BuildError("No theme called 'x'")

    monkeypatch.setattr(builder, "build", fail)
    build_ai_oil(app)
    assert "No theme called" in app.sidebar.error[0].value

    st.cache_data.clear()
    monkeypatch.setattr(builder, "build", lambda prefs: {**fake_build(prefs), "holdings": [],
                                                          "warnings": ["Nothing passes."]})
    build_ai_oil(app)
    assert any("No stock passes" in e.value for e in app.error)
    assert any("Build a fund to see its risk" in i.value for i in app.info)


def test_risk_failure_is_a_message(app, monkeypatch):
    def fail(holdings):
        raise monte_carlo.SimulationError("Need at least 5 days of history; got 3.")

    monkeypatch.setattr(risk, "run_risk", fail)
    build_ai_oil(app)
    assert any("risk report couldn't run" in e.value for e in app.error)
