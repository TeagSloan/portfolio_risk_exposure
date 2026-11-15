"""How the dashboard looks: one stylesheet, the fund header, the rejection panel and chart styling.

The idea is a fund fact sheet. Each colour has one job:
- ink navy   text and the fund header
- ledger blue  High / Moderate exposure, buttons, selected choices
- violet     anything that lives on Monad (the launch button, the fund's address, the Monad tab)
- red        a refusal: the mandate rejecting a stock is the loudest thing on the page

Colours and the typeface themselves are set in .streamlit/config.toml. Nothing here changes what the
app does; app.py calls these to draw things.
"""

from __future__ import annotations

from html import escape as _escape_attr

import streamlit as st

INK = "#14213D"
BLUE = "#1F4E9E"
VIOLET = "#6E54E8"
RED = "#C8322B"
SLATE = "#5B6678"
FONT = "'Schibsted Grotesk', -apple-system, 'Segoe UI', sans-serif"

_CSS = f"""
<style>
/* Numbers line up in columns. */
[data-testid="stMetricValue"], [data-testid="stTable"] td, .tf-fund, .tf-reject {{
  font-variant-numeric: tabular-nums;
}}
h1 {{ font-weight: 800; letter-spacing: -0.02em; }}
h2, h3 {{ font-weight: 700; letter-spacing: -0.01em; }}
[data-testid="stMetricValue"] {{ font-weight: 700; }}

/* Tabs read as the four steps of the page; the Monad tab is violet. */
[role="tablist"] {{ gap: 1.75rem; }}
[role="tablist"] [role="tab"] p {{ font-size: 1.05rem; font-weight: 600; }}
[role="tablist"] [role="tab"]:last-of-type p {{ color: {VIOLET}; }}

/* Anything that sends the fund to Monad is violet. */
.st-key-launch button, .st-key-launch button:hover, .st-key-launch button:focus {{
  background: {VIOLET}; border-color: {VIOLET}; color: #fff;
}}
.st-key-launch button:hover {{ filter: brightness(1.08); }}
.st-key-launch button:focus-visible {{ outline: 3px solid {INK}; outline-offset: 2px; }}

/* Fund header: the built fund's name, symbol and mandate. */
.tf-fund {{
  background: {INK}; color: #fff; border-radius: 6px; padding: 1.4rem 1.6rem; margin: 0.4rem 0 1.2rem;
  display: flex; flex-wrap: wrap; gap: 1rem 2.5rem; align-items: flex-end; justify-content: space-between;
}}
.tf-fund-name {{ font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.15; }}
.tf-fund-symbol {{ font-weight: 500; color: #B9C4DA; margin-left: 0.6rem; }}
.tf-rules {{ margin-top: 0.7rem; display: flex; flex-wrap: wrap; gap: 0.5rem; }}
.tf-rule {{ font-size: 0.95rem; font-weight: 600; padding: 0.2rem 0.7rem; border-radius: 3px; }}
.tf-rule-want {{ background: {BLUE}; color: #fff; }}
.tf-rule-avoid {{ border: 1.5px solid #B9C4DA; color: #fff; }}
.tf-chain {{ font-size: 0.95rem; text-align: right; color: #B9C4DA; }}
.tf-chain strong {{ color: #fff; }}
.tf-chain a, .tf-live {{ color: #C9BEFF !important; font-weight: 600; }}
.tf-address {{ font-size: 0.85rem; word-break: break-all; }}

/* Rejection: the mandate saying no. */
.tf-reject {{
  border: 2px solid {RED}; border-radius: 6px; background: #fff; padding: 1.3rem 1.6rem; margin: 0.6rem 0;
  animation: tf-refuse 0.35s ease-out 1;
}}
.tf-reject-word {{ color: {RED}; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; }}
.tf-reject-reason {{ color: {INK}; font-size: 1.3rem; font-weight: 600; margin-top: 0.5rem; }}
.tf-reject-source {{ color: {SLATE}; font-size: 0.95rem; margin-top: 0.7rem; }}
@keyframes tf-refuse {{
  0% {{ transform: translateX(0); }} 25% {{ transform: translateX(-7px); }}
  50% {{ transform: translateX(6px); }} 75% {{ transform: translateX(-3px); }} 100% {{ transform: translateX(0); }}
}}
@media (prefers-reduced-motion: reduce) {{ .tf-reject {{ animation: none; }} }}
@media (max-width: 640px) {{
  .tf-fund-name {{ font-size: 1.5rem; }} .tf-chain {{ text-align: left; }} .tf-reject-word {{ font-size: 1.7rem; }}
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
    """Give a Plotly chart the page's typeface and ink colour. Returns the same figure."""
    if fig is not None:
        fig.update_layout(font={"family": FONT, "color": INK}, paper_bgcolor="rgba(0,0,0,0)",
                          hoverlabel={"font": {"family": FONT}})
    return fig
