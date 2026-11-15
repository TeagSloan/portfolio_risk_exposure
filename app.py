"""Theme Funds dashboard (Phase 8).

    streamlit run app.py

Flow: choose Want / Don't care / Avoid per theme -> Build -> see the basket, the theme heatmap and
the audit trail behind every tier -> risk (Monte Carlo, theme shocks, mean-variance check) -> ask
Claude about the fund -> launch on Monad (arrives with Phase 7; the mandate check is previewed
off-chain until then).

All the logic lives in engine/; this file only lays it out.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from engine import assistant, builder, dashboard, risk, screen
from engine.data import DEFAULT_END, DEFAULT_START, DataError
from engine.monte_carlo import SimulationError
from engine.shocks import LABEL as SHOCK_LABEL
from engine.shocks import ShockError
from engine.theme_loader import load_all

st.set_page_config(page_title="Theme Funds", page_icon="📈", layout="wide")

EXAMPLE_QUESTIONS = [
    "In plain English, what does this fund hold and why?",
    "How bad could a bad year be?",
    "What happens to my fund if oil prices jump?",
]
SHOCK_SIZES = [-50, -30, -20, -10, 10, 20, 30, 50]


# ---------------------------------------------------------------------------------------------
# Cached engine calls (the engine also caches on disk; these keep reruns instant)
# ---------------------------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def themes() -> dict[str, dict]:
    return load_all()


@st.cache_resource(show_spinner="Screening the stock universe against every theme (first run only)...")
def universe_table() -> dict[str, dict[str, dict]]:
    return builder.prescreen()


@st.cache_data(show_spinner="Building your fund...")
def run_build(prefs: tuple[tuple[str, str], ...]) -> dict:
    return builder.build(dict(prefs))


@st.cache_data(show_spinner="Running 5,000 simulated years, theme shocks and the mean-variance check...")
def run_risk(holdings: tuple[tuple[str, float], ...]):
    return risk.run_risk(dict(holdings))


@st.cache_data(show_spinner=False)
def companies(tickers: tuple[str, ...]) -> dict[str, dict]:
    return assistant.company_info(list(tickers))


@st.cache_data(show_spinner=False)
def screen_ticker(ticker: str, theme_keys: tuple[str, ...]) -> dict[str, dict]:
    """Tier results for a ticker outside the pre-screened universe."""
    all_themes = themes()
    return {k: screen._screen_one(ticker, all_themes[k], DEFAULT_START, DEFAULT_END) for k in theme_keys}


# ---------------------------------------------------------------------------------------------
# Sidebar: choices
# ---------------------------------------------------------------------------------------------

def sidebar() -> None:
    st.sidebar.header("1. Choose your themes")
    st.sidebar.caption("Want = the fund must have it. Avoid = the fund must stay clear of it.")
    choices = {}
    for key, theme in themes().items():
        choices[key] = st.sidebar.radio(theme["name"], dashboard.CHOICES, index=1, horizontal=True,
                                        key=f"choice_{key}")
    if st.sidebar.button("Build my fund", type="primary", width="stretch"):
        prefs = dashboard.prefs_from_choices(choices)
        if not prefs:
            st.sidebar.warning("Pick at least one theme to Want or Avoid.")
            return
        try:
            st.session_state["build"] = run_build(tuple(sorted(prefs.items())))
            st.session_state["prefs"] = prefs
            st.session_state["chat"] = []
        except builder.BuildError as exc:
            st.sidebar.error(str(exc))


# ---------------------------------------------------------------------------------------------
# Tab 1: the fund
# ---------------------------------------------------------------------------------------------

def fund_tab(build: dict) -> None:
    holdings = dashboard.holdings_from_build(build)
    if not holdings:
        st.error("No stock passes every rule you chose. Try fewer or looser preferences.")
        for w in build.get("warnings", []):
            st.caption(w)
        return

    st.subheader("Your basket")
    rows = []
    for h in build["holdings"]:
        row = {"Holding": h["ticker"], "Weight": f"{h['weight_pct']:.1f}%"}
        row.update(h.get("tiers") or {})
        row["Notes"] = "; ".join(h.get("labels") or [])
        rows.append(row)
    st.dataframe(rows, hide_index=True, width="stretch")
    for w in build.get("warnings", []):
        st.warning(w)
    if build.get("rejected_by_etf_check"):
        st.caption("Passed the exposure test but not the theme-ETF confirmation, so left out: "
                   + ", ".join(build["rejected_by_etf_check"]))

    verification = build.get("verification") or {}
    if verification:
        st.subheader("Does the finished fund match your choices?")
        st.caption("The final basket is screened again from scratch.")
        for c in verification["checks"].values():
            (st.success if c["pass"] else st.error)(f"**{c['choice'].title()} {c['theme']}**: {c['sentence']}")

    st.subheader("Theme heatmap")
    st.caption("Every holding against every theme. Dark blue = High, light blue = Moderate, grey = Limited "
               "(Ltd* = lower confidence), amber ? = the data can't tell (not the same as zero).")
    table = universe_table()
    matrix = dashboard.tier_matrix(table, list(holdings), themes())
    st.plotly_chart(dashboard.heatmap_figure(matrix, holdings), width="stretch")

    st.subheader("Audit trail")
    st.caption("How any one tier was decided: the regression numbers and the thresholds they were held to.")
    c1, c2 = st.columns(2)
    ticker = c1.selectbox("Holding", list(matrix.index), key="audit_ticker")
    names = {th["name"]: k for k, th in themes().items()}
    theme_name = c2.selectbox("Theme", list(names), key="audit_theme")
    result = table.get(ticker, {}).get(names[theme_name], {})
    st.table({"": [r[0] for r in dashboard.audit_rows(result)],
              "Value": [r[1] for r in dashboard.audit_rows(result)]})
    groups = dashboard.group_table(result)
    if groups is not None:
        st.caption("A group counts if its beta sum is above 0.05 and its one-sided p-value is below the "
                   "threshold. The largest counting group sets the tier.")
        st.dataframe(groups, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------------------------
# Tab 2: risk
# ---------------------------------------------------------------------------------------------

def risk_report(build: dict):
    holdings = dashboard.holdings_from_build(build)
    if not holdings:
        return None, None
    try:
        return run_risk(tuple(sorted(holdings.items())))
    except (DataError, SimulationError, ShockError, ValueError) as exc:
        st.error(f"The risk report couldn't run: {exc}")
        return None, None


def risk_tab(report: dict | None, figures: dict | None) -> None:
    if report is None:
        st.info("Build a fund to see its risk.")
        return
    mc = report["monte_carlo"]
    p, b = mc["portfolio"], mc["benchmark"]
    st.subheader("A range of possible years")
    def loss(x):
        return f"-{x:.0%}" if x > 0 else "no loss"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Chance of losing >10%", f"{p['p_loss_over_10']:.0%}")
    m1.caption(f"SPY (the market): {b['p_loss_over_10']:.0%}")
    m2.metric("Bad year (5% VaR)", loss(p["var_5"]))
    m2.caption(f"SPY (the market): {loss(b['var_5'])}")
    m3.metric("Average of worst years (CVaR)", loss(p["cvar_5"]))
    m3.caption(f"SPY (the market): {loss(b['cvar_5'])}")
    m4.metric("Beat SPY", f"{mc['p_beat_benchmark']:.0%} of years")
    st.plotly_chart(figures["fan_chart"], width="stretch")
    for s in mc["sentences"]:
        st.markdown(f"- {s}")

    st.subheader("Theme shocks")
    st.caption(f"What if one theme's stocks moved more than the overall market? ({SHOCK_LABEL}.)")
    by_name = {s["theme_name"]: s for s in report["shocks"]}
    default = max(report["shocks"], key=lambda s: abs(s["portfolio_move"]))["theme_name"]
    c1, c2 = st.columns([2, 3])
    theme_name = c1.selectbox("Theme", list(by_name), index=list(by_name).index(default), key="shock_theme")
    size = c2.select_slider("Shock size", SHOCK_SIZES, value=30, format_func=lambda v: f"{v:+d}%",
                            key="shock_size")
    base = by_name[theme_name]
    result = dashboard.reshock(base, themes()[base["theme"]], size / 100)
    st.metric(f"Estimated portfolio move if {theme_name} moves {size:+d}%", f"{result.portfolio_move:+.1%}")
    st.write(result.sentence)
    contrib = [h for h in result.holdings if h.move is not None and h.ticker != "CASH"]
    if contrib:
        contrib.sort(key=lambda h: h.contribution)
        fig = go.Figure(go.Bar(x=[h.contribution * 100 for h in contrib], y=[h.ticker for h in contrib],
                               orientation="h", marker_color=["#dc2626" if h.contribution < 0 else "#2563eb"
                                                              for h in contrib],
                               hovertemplate="%{y}: %{x:+.2f}% of the portfolio<extra></extra>"))
        fig.update_layout(title="Each holding's effect on the portfolio (percentage points)",
                          xaxis_ticksuffix="%", template="plotly_white", height=max(240, 28 * len(contrib) + 90),
                          margin={"t": 40, "l": 10, "r": 10, "b": 10})
        st.plotly_chart(fig, width="stretch")
    with st.expander("Every theme at +30%"):
        st.dataframe([{"Theme": s["theme_name"], "Estimated portfolio move": f"{s['portfolio_move']:+.1%}"}
                      for s in sorted(report["shocks"], key=lambda s: -abs(s["portfolio_move"]))],
                     hide_index=True, width="stretch")

    st.subheader("Mean-variance check")
    frontier = report.get("frontier") or {}
    if figures and figures.get("frontier") is not None:
        st.plotly_chart(figures["frontier"], width="stretch")
    for s in frontier.get("sentences", []):
        st.markdown(f"- {s}")


# ---------------------------------------------------------------------------------------------
# Tab 3: ask Claude
# ---------------------------------------------------------------------------------------------

def chat_tab(build: dict, report: dict | None) -> None:
    st.subheader("Ask about your fund")
    st.caption("Answers come only from this fund's data. No predictions and no buy/sell advice.")
    held = tuple(sorted(dashboard.holdings_from_build(build)))
    facts = assistant.fund_facts(build, report, dashboard.chain_status(), companies(held))
    history = st.session_state.setdefault("chat", [])
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for col, q in zip(cols, EXAMPLE_QUESTIONS, strict=True):
        if col.button(q, key=f"example_{q}"):
            st.session_state["pending_question"] = q
    conversation = st.container()  # messages go above the input box, like a normal chat
    question = st.chat_input("Ask a question about your fund") or st.session_state.pop("pending_question", None)
    for m in history:
        conversation.chat_message(m["role"]).write(m["content"])
    if not question:
        return
    conversation.chat_message("user").write(question)
    with conversation.chat_message("assistant"):
        try:
            answer = st.write_stream(assistant.ask(question, facts, history))
        except assistant.AssistantError as exc:
            st.error(str(exc))
            return
    history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]


# ---------------------------------------------------------------------------------------------
# Tab 4: on-chain
# ---------------------------------------------------------------------------------------------

def chain_tab(prefs: dict[str, str]) -> None:
    status = dashboard.chain_status()
    st.subheader("Launch your fund on Monad")
    st.info(status["note"])
    c1, c2 = st.columns(2)
    c1.button("Launch fund on Monad", disabled=not status["ready"], help="Arrives with Phase 7")
    c2.button("Deposit test USDC", disabled=not status["ready"], help="Arrives with Phase 7")

    st.subheader("Try to break the rules")
    st.caption("Try adding a stock that goes against your choices. The fund's rules reject it.")
    ticker = st.text_input("Stock to add", value="XOM", key="try_ticker").strip().upper()
    if st.button("Try adding it", key="try_add") and ticker:
        table = universe_table()
        results = table.get(ticker) or screen_ticker(ticker, tuple(sorted(prefs)))
        tiers = {k: (results.get(k) or {}).get("tier", dashboard.NOT_SCREENED) for k in prefs}
        allowed, reasons = dashboard.mandate_check(ticker, prefs, tiers, themes())
        if allowed:
            st.success(f"{ticker} fits every rule of this fund, so it could be added.")
        else:
            st.error(f"Rejected: {ticker} can't be added.\n\n" + "\n\n".join(reasons))
        st.caption("Preview: checked off-chain with the same rules. Once Phase 7 is live, the fund "
                   "contract itself rejects the trade.")


# ---------------------------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------------------------

def main() -> None:
    st.title("Theme Funds")
    st.caption("Pick the themes you want and the ones you want to avoid. We build the fund, show its "
               "risk in plain English, and (soon) launch it on Monad with rules that can't be broken.")
    sidebar()
    build = st.session_state.get("build")
    if not build:
        st.markdown("**How it works:** choose Want / Don't care / Avoid for each theme on the left, "
                    "then press **Build my fund**.")
        return
    prefs = st.session_state.get("prefs", {})
    st.caption("Your choices: " + ", ".join(f"{v} {themes()[k]['name']}" for k, v in prefs.items()))
    report, figures = risk_report(build)
    t1, t2, t3, t4 = st.tabs(["Your fund", "Risk", "Ask about your fund", "Launch on Monad"])
    with t1:
        fund_tab(build)
    with t2:
        risk_tab(report, figures)
    with t3:
        chat_tab(build, report)
    with t4:
        chain_tab(prefs)


main()
