"""How the dashboard looks: one stylesheet, the fund header, the rejection panel and chart styling.

Follows the team's "Shared look" sheet so the dashboard and the League page read as one product:
- dark background, cards with 16 px corners and a 1 px border, no shadows, no gradients
- one accent (purple); green and red only for gains, losses and a refusal
- Space Grotesk for headings and big numbers, Inter for everything else, JetBrains Mono for addresses

Colours and typefaces themselves are set in .streamlit/config.toml. Nothing here changes what the app
does; app.py calls these to draw things.
"""

from __future__ import annotations

from html import escape as _escape_attr

import streamlit as st

BACKGROUND = "#0E0F14"
CARD = "#171922"
RAISED = "#1F2230"
BORDER = "#262A38"
TEXT = "#F2F3F7"
MUTED = "#9AA1B5"
ACCENT = "#8B7CF6"
GAIN = "#3ECF8E"
LOSS = "#F2555A"
HEADING_FONT = "'Space Grotesk', -apple-system, 'Segoe UI', sans-serif"
BODY_FONT = "Inter, -apple-system, 'Segoe UI', sans-serif"
MONO_FONT = "'JetBrains Mono', ui-monospace, Menlo, monospace"

_CSS = f"""
<style>
/* Numbers line up in columns. */
[data-testid="stMetricValue"], [data-testid="stTable"] td, .tf-fund, .tf-reject {{
  font-variant-numeric: tabular-nums;
}}
h1, h2, h3 {{ letter-spacing: -0.01em; }}

/* Headline numbers sit on cards, in the heading typeface. */
[data-testid="stMetric"] {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; padding: 1rem 1.2rem;
}}
[data-testid="stMetricValue"] {{ font-family: {HEADING_FONT}; font-weight: 600; font-size: 1.9rem; }}
[data-testid="stMetricLabel"] {{ color: {MUTED}; }}
/* Let long labels and values wrap instead of being cut off with "...". */
[data-testid="stMetricValue"] > div, [data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] > div {{
  white-space: normal; overflow: visible; text-overflow: clip;
}}

/* Sidebar: keep Want / Don't care / Avoid on one line. */
[data-testid="stSidebar"] [role="radiogroup"] {{ flex-wrap: nowrap; gap: 0.7rem; }}
[data-testid="stSidebar"] [role="radiogroup"] p {{ font-size: 0.9rem; white-space: nowrap; }}

/* Tabs read as the four steps of the page. */
[role="tablist"] {{ gap: 1.75rem; }}
[role="tablist"] [role="tab"] p {{ font-size: 1.05rem; font-weight: 600; }}

/* Fund header: the built fund's name, symbol and mandate. */
.tf-fund {{
  background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 16px;
  padding: 1.4rem 1.6rem; margin: 0.4rem 0 1.2rem;
  display: flex; flex-wrap: wrap; gap: 1rem 2.5rem; align-items: flex-end; justify-content: space-between;
}}
.tf-fund-name {{ font-family: {HEADING_FONT}; font-size: 1.9rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.15; }}
.tf-fund-symbol {{ font-weight: 500; color: {ACCENT}; margin-left: 0.6rem; }}
.tf-rules {{ margin-top: 0.8rem; display: flex; flex-wrap: wrap; gap: 0.5rem; }}
.tf-rule {{ font-size: 0.92rem; font-weight: 600; padding: 0.25rem 0.8rem; border-radius: 999px; }}
.tf-rule-want {{ background: {ACCENT}; color: {BACKGROUND}; }}
.tf-rule-avoid {{ background: {RAISED}; border: 1px solid {BORDER}; color: {TEXT}; }}
.tf-chain {{ font-size: 0.95rem; text-align: right; color: {MUTED}; }}
.tf-chain strong {{ color: {TEXT}; }}
.tf-chain a, .tf-live {{ color: {ACCENT} !important; font-weight: 600; }}
.tf-address {{ font-family: {MONO_FONT}; font-size: 0.85rem; word-break: break-all; color: {TEXT}; }}

/* Rejection: the mandate saying no. */
.tf-reject {{
  border: 1px solid {LOSS}; border-radius: 16px; background: {CARD}; padding: 1.3rem 1.6rem; margin: 0.6rem 0;
  animation: tf-refuse 0.35s ease-out 1;
}}
.tf-reject-word {{ color: {LOSS}; font-family: {HEADING_FONT}; font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1; }}
.tf-reject-reason {{ color: {TEXT}; font-size: 1.25rem; font-weight: 600; margin-top: 0.5rem; }}
.tf-reject-source {{ color: {MUTED}; font-size: 0.95rem; margin-top: 0.7rem; }}
@keyframes tf-refuse {{
  0% {{ transform: translateX(0); }} 25% {{ transform: translateX(-7px); }}
  50% {{ transform: translateX(6px); }} 75% {{ transform: translateX(-3px); }} 100% {{ transform: translateX(0); }}
}}
@media (prefers-reduced-motion: reduce) {{ .tf-reject {{ animation: none; }} }}
@media (max-width: 640px) {{
  .tf-fund-name {{ font-size: 1.5rem; }} .tf-chain {{ text-align: left; }} .tf-reject-word {{ font-size: 1.6rem; }}
}}
</style>
"""


def escape(text: str) -> str:
    """Make text safe to show inside the page (quotes are left alone so apostrophes read normally)."""
    return _escape_attr(str(text), quote=False)


def apply() -> None:
    """Add the stylesheet. Call once, right after st.set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)


def fund_header_html(name: str, symbol: str, prefs: dict[str, str], theme_names: dict[str, str],
                     fund: dict | None = None, explorer_url: str | None = None) -> str:
    """The band at the top of a built fund. `fund` is the launched fund's details, if it has been launched."""
    order = sorted(prefs, key=lambda k: (prefs[k] != "want", k))
    rules = "".join(
        f'<span class="tf-rule tf-rule-{escape(prefs[k])}">{escape(prefs[k].title())} '
        f'{escape(theme_names.get(k, k))}</span>'
        for k in order if prefs[k] in ("want", "avoid")
    )
    if fund:
        where = escape(str(fund.get("network") or "the chain"))
        address = escape(str(fund.get("address", "")))
        link = (f'<a href="{_escape_attr(explorer_url)}" target="_blank" rel="noopener">View on the explorer</a>'
                if explorer_url else "")
        chain = (f'<div class="tf-chain"><span class="tf-live">Live on {where}</span>'
                 f'<div class="tf-address">{address}</div>{link}</div>')
    else:
        chain = '<div class="tf-chain"><strong>Not launched yet</strong><br>Launch it from the Launch on Monad tab</div>'
    return (f'<div class="tf-fund"><div><div class="tf-fund-name">{escape(name)}'
            f'<span class="tf-fund-symbol">${escape(symbol)}</span></div>'
            f'<div class="tf-rules">{rules}</div></div>{chain}</div>')


def fund_header(build: dict, prefs: dict[str, str], themes: dict[str, dict], fund: dict | None = None) -> None:
    """Draw the fund header for a built fund. Uses the launched fund's name once there is one."""
    from chain import app_actions
    from chain.publish import PublishError

    if not any(h.get("ticker") != "CASH" for h in build.get("holdings", [])):
        return  # nothing passed the rules, so there is no fund to head
    name, symbol = (fund or {}).get("name"), (fund or {}).get("symbol")
    if not name or not symbol:
        try:
            plan = app_actions.plan_for(build)
            name, symbol = name or plan["name"], symbol or plan["symbol"]
        except PublishError:
            name, symbol = name or "Your ETF", symbol or "ETF"
    explorer = app_actions.explorer_links(fund).get("fund") if fund else None
    names = {k: t["name"] for k, t in themes.items()}
    st.markdown(fund_header_html(name, symbol, prefs, names, fund, explorer), unsafe_allow_html=True)


def rejection_html(ticker: str, reasons: list[str], on_chain: bool) -> str:
    source = ("Refused by the fund contract on Monad. Rehearsed against the live contract; nothing was sent."
              if on_chain else
              "Preview: checked off-chain with the same rules, because no chain is connected yet.")
    body = "".join(f'<div class="tf-reject-reason">{escape(r)}</div>' for r in reasons if r)
    return (f'<div class="tf-reject" role="alert"><div class="tf-reject-word">Rejected: {escape(ticker)} '
            f'can\'t be added</div>{body}<div class="tf-reject-source">{source}</div></div>')


def rejection(ticker: str, reasons: list[str] | str, on_chain: bool) -> None:
    """Draw the mandate's refusal. `reasons` are the contract's (or the rules') own plain-English reasons."""
    reasons = [reasons] if isinstance(reasons, str) else list(reasons)
    st.markdown(rejection_html(ticker, reasons, on_chain), unsafe_allow_html=True)


def chart(fig):
    """Put a Plotly chart on the dark page with the page's typeface. Returns the same figure."""
    if fig is not None:
        fig.update_layout(template="plotly_dark", font={"family": BODY_FONT, "color": TEXT},
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          hoverlabel={"font": {"family": BODY_FONT}})
        fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER)
        fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    return fig
