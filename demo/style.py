"""Colors, fonts and small HTML building blocks for demo_app.py.

Nothing here computes a number. Every function takes values the engine already produced and
returns HTML (or restyles a Plotly figure) so the dashboard looks like one product with the
League page: black background, rose for buttons and "want", champagne gold for "avoid", mint and
coral only for gains and losses (always with a + or - sign). Type has a sportsbook / scoreboard feel:
headings, labels and the big numbers in a bold condensed face (Barlow Condensed, uppercase for headers and
labels), text, buttons and tables in Inter, addresses and hashes in JetBrains Mono. Every digit is tabular
(fixed width), so numbers don't jiggle while they count.
"""

from __future__ import annotations

import re
from html import escape

# ---------------------------------------------------------------------------------------------
# Palette and type (shared with the League page design)
# ---------------------------------------------------------------------------------------------

INK = "#0B0A0B"          # page background (black)
CARD = "#171315"         # panels
RAISED = "#211B1E"       # inputs, hover
LINE = "#2E2529"         # borders
TEXT = "#F5EEF1"
MUTED = "#B8A9B0"
ROSE = "#C2456F"         # buttons and "want" fills (white text reads on it)
ROSE_HOVER = "#AD3A61"
BLUSH = "#F4A6BF"        # highlights: the fund line, numbers you want to see
BLUSH_TEXT = "#F9C9D8"   # text on rose-tinted chips
ROSE_SOFT = "#3A1A27"    # rose-tinted chip background
CHAMPAGNE = "#E8C98F"    # "avoid"
CHAMPAGNE_SOFT = "#2E2516"
GAIN = "#6FD6AE"
LOSS = "#FF8A7A"
NEUTRAL_BAR = "#3A3034"  # themes that aren't part of your choices

TIER_STYLE = {  # (background, text) per tier, readable on black
    "High": (ROSE_SOFT, BLUSH_TEXT),
    "Moderate": ("#2C1A22", "#E9A9BF"),
    "Limited": ("#16261F", "#8FDDBD"),
    "Limited (lower confidence)": ("#17221D", "#A4CFBB"),
    "Not determined": (CHAMPAGNE_SOFT, CHAMPAGNE),
    "Not screened": ("#1E191B", MUTED),
}

FONTS = ("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800"
         "&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap")
DISPLAY = "'Barlow Condensed', 'Arial Narrow', 'Roboto Condensed', system-ui, sans-serif"  # headings, labels, big numbers
SANS = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"  # text, buttons, inputs, tables
MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"  # addresses and hashes

# NOTE: no "<" + letter anywhere inside this CSS (Streamlit's sanitizer would drop the whole block).
CSS = f"""
<style>
@import url('{FONTS}');
html, body, .stApp, .stMarkdown, p, label, input, textarea, button, table {{ font-family: {SANS}; }}
.stApp {{ background: {INK}; color: {TEXT}; font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased; }}
code, pre, .tf-mono {{ font-family: {MONO} !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {{ display: none; }}
.block-container {{ max-width: 1240px; padding-top: 2.2rem; padding-bottom: 6rem; }}
h1, h2, h3 {{ font-family: {DISPLAY} !important; font-weight: 700 !important; text-transform: uppercase;
  letter-spacing: 0.02em; line-height: 1.05; color: {TEXT}; }}
p, li, label, .stMarkdown {{ color: {TEXT}; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED} !important; }}
[data-testid="stWidgetLabel"] p {{ color: {TEXT}; font-weight: 600; }}
.stButton > button, .stLinkButton > a {{ border-radius: 10px; min-height: 44px; font-weight: 600; }}
[data-testid="stBaseButton-primary"], .stButton button[kind="primary"] {{ background: {ROSE}; border: 0; color: #fff; }}
[data-testid="stBaseButton-primary"]:hover, .stButton button[kind="primary"]:hover {{ background: {ROSE_HOVER}; color: #fff; }}
[data-testid="stBaseButton-primary"] p, .stButton button[kind="primary"] p {{ color: #fff; font-weight: 600; }}
[data-testid="stBaseButton-secondary"] {{ background: {RAISED}; border: 1px solid {LINE}; color: {TEXT}; }}
[data-testid="stExpander"] {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
.stApp [data-testid="stButtonGroup"] button {{ background: {RAISED}; border-color: {LINE}; color: {MUTED}; }}
.stApp [data-testid="stButtonGroup"] button p {{ color: {MUTED}; font-weight: 600; }}
.stApp [data-testid="stButtonGroup"] button:hover {{ border-color: {ROSE}; }}
.stApp [data-testid="stButtonGroup"] button[aria-checked="true"] {{ background: {ROSE_SOFT}; border-color: {ROSE}; }}
.stApp [data-testid="stButtonGroup"] button[aria-checked="true"] p {{ color: {BLUSH_TEXT}; }}
[data-testid="stMetricValue"] {{ font-family: {DISPLAY}; font-weight: 800; font-variant-numeric: tabular-nums; }}
[data-testid="stMetricLabel"] p {{ font-family: {DISPLAY}; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.04em; color: {MUTED}; }}
[data-testid="stTabs"] button p {{ font-size: 16px; font-weight: 600; }}
[data-testid="stTabs"] [aria-selected="true"] p {{ color: {BLUSH}; }}
div[data-baseweb="select"] > div, input, textarea {{ background: {RAISED} !important; color: {TEXT} !important; }}
:focus-visible {{ outline: 2px solid {BLUSH} !important; outline-offset: 2px; }}

.tf-hero {{ position: relative; overflow: hidden; isolation: isolate; padding: 48px 40px 40px; margin-bottom: 8px;
  border: 1px solid {LINE}; border-radius: 16px; background: {CARD}; }}
.tf-hero::before {{ content: ""; position: absolute; inset: -40%; z-index: -2;
  background: radial-gradient(40% 35% at 20% 30%, rgba(194, 69, 111, .30), transparent 70%),
              radial-gradient(35% 30% at 80% 20%, rgba(244, 166, 191, .16), transparent 70%),
              radial-gradient(45% 40% at 70% 85%, rgba(232, 201, 143, .12), transparent 70%);
  animation: tf-drift 18s ease-in-out infinite alternate; will-change: transform; }}
/* No raw less-than signs anywhere in this CSS: Streamlit's sanitizer drops the WHOLE style block if its text
   looks like a tag. The grain image is %-encoded and @property syntax uses the CSS escape \\3C. */
.tf-hero::after {{ content: ""; position: absolute; inset: 0; z-index: -1; opacity: .07; pointer-events: none;
  background-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"); }}
@keyframes tf-drift {{ from {{ transform: translate3d(-4%, -2%, 0) scale(1); }} to {{ transform: translate3d(4%, 3%, 0) scale(1.08); }} }}
.tf-hero .eyebrow {{ font-family: {DISPLAY}; font-weight: 700; font-size: 16px; letter-spacing: .06em;
  text-transform: uppercase; color: {BLUSH}; margin-bottom: 12px; }}
.tf-hero .props {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 24px; }}
.tf-hero .props span {{ font-size: 13px; color: {TEXT}; background: rgba(23, 19, 21, .7); border: 1px solid {LINE};
  border-radius: 999px; padding: 6px 12px; }}
@property --tf-a {{ syntax: "\\3C integer\\3E"; initial-value: 0; inherits: false; }}
@property --tf-b {{ syntax: "\\3C integer\\3E"; initial-value: 0; inherits: false; }}
.tf-count {{ --tf-a: var(--a); --tf-b: var(--b); counter-reset: a var(--tf-a) b var(--tf-b);
  animation: tf-count 900ms cubic-bezier(.2,.8,.2,1) both; }}
.tf-count .i::after {{ content: counter(a); }}
.tf-count .f::after {{ content: counter(b, var(--fs, decimal)); }}
@keyframes tf-count {{ from {{ --tf-a: 0; --tf-b: 0; }} }}
.tf-tile {{ animation: tf-rise 400ms cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d, 0ms); }}
@keyframes tf-rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
.tf-hold .bar {{ grid-column: 2 / -1; height: 4px; background: {RAISED}; border-radius: 4px; overflow: hidden; margin-top: 2px; }}
.tf-hold .bar span {{ display: block; height: 100%; background: {ROSE}; border-radius: 4px; transform-origin: left;
  animation: tf-bar 600ms cubic-bezier(.2,.8,.2,1) both; }}
@keyframes tf-bar {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
.tf-hold .why {{ grid-column: 2 / -1; font-size: 13px; color: {MUTED}; line-height: 1.45; }}
@media (prefers-reduced-motion: reduce) {{ .tf-hero::before, .tf-count, .tf-tile, .tf-hold .bar span {{ animation: none; }} }}
.tf-hero h1 {{ font-size: clamp(56px, 9vw, 104px); line-height: 0.9; margin: 0; font-weight: 800 !important;
  letter-spacing: 0.01em; }}
.tf-hero p {{ margin: 16px 0 0; color: {MUTED}; font-size: 19px; max-width: 640px; line-height: 1.55; }}

.tf-step {{ margin: 64px 0 20px; padding-top: 28px; border-top: 1px solid {LINE}; }}
.tf-step h2 {{ font-size: clamp(34px, 5vw, 46px); margin: 0; line-height: 1; font-weight: 800 !important; }}
.tf-step p {{ margin: 8px 0 0; color: {MUTED}; font-size: 16px; max-width: 720px; line-height: 1.55; }}

.tf-fp {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 18px; padding: 28px 28px 18px; }}
.tf-fp-cols {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 12px; align-items: end;
  height: 260px; border-bottom: 1px solid {LINE}; }}
.tf-fp-col {{ position: relative; height: 100%; display: flex; flex-direction: column; justify-content: flex-end;
  align-items: stretch; }}
.tf-fp-bar {{ border-radius: 8px 8px 2px 2px; min-height: 3px; transform-origin: bottom;
  animation: tf-grow 900ms cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d); }}
.tf-fp-val {{ font-family: {DISPLAY}; font-weight: 800; font-size: 26px; margin-bottom: 6px; line-height: 1;
  text-align: center; font-variant-numeric: tabular-nums; }}
.tf-fp-names {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 12px; padding-top: 10px; }}
.tf-fp-names div {{ font-size: 13px; line-height: 1.3; color: {MUTED}; text-align: center; }}
.tf-fp-names b {{ display: block; color: {TEXT}; font-weight: 600; }}
.tf-fp-legend {{ display: flex; gap: 18px; flex-wrap: wrap; margin-top: 16px; font-size: 14px; color: {MUTED}; }}
.tf-fp-legend i {{ display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 6px;
  vertical-align: -1px; }}
@keyframes tf-grow {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
@media (prefers-reduced-motion: reduce) {{ .tf-fp-bar {{ animation: none; }} }}

.tf-funnel {{ display: flex; flex-direction: column; gap: 12px; }}
.tf-funnel .row {{ display: grid; grid-template-columns: minmax(0, 1fr) 64px; column-gap: 12px; align-items: end; }}
.tf-funnel .lbl {{ font-size: 14px; color: {TEXT}; line-height: 1.35; margin-bottom: 6px; }}
.tf-funnel .bar {{ background: {RAISED}; border-radius: 6px; height: 10px; overflow: hidden; }}
.tf-funnel .bar span {{ display: block; height: 100%; background: {ROSE}; border-radius: 6px; }}
.tf-funnel .num {{ font-family: {DISPLAY}; font-weight: 800; font-size: 30px; text-align: right;
  font-variant-numeric: tabular-nums; line-height: 1; }}

.tf-hold {{ display: flex; flex-direction: column; }}
.tf-hold .row {{ display: grid; grid-template-columns: 76px minmax(0, 1fr) auto 64px; column-gap: 16px; row-gap: 6px;
  align-items: center; padding: 16px 4px; border-top: 1px solid {LINE}; }}
.tf-hold .row:first-child {{ border-top: 0; }}
.tf-hold .tk {{ font-family: {DISPLAY}; font-weight: 700; font-size: 20px; letter-spacing: 0.02em; }}
.tf-hold .nm {{ font-size: 14px; color: {TEXT}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.tf-hold .ind {{ font-size: 13px; color: {MUTED}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.tf-hold .w {{ text-align: right; font-variant-numeric: tabular-nums; color: {TEXT}; font-family: {SANS};
  font-weight: 600; font-size: 17px; }}
.tf-chips {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}
.tf-chip {{ font-size: 12px; font-weight: 600; padding: 4px 9px; border-radius: 999px; white-space: nowrap; }}

.tf-tiles {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
@media (max-width: 900px) {{ .tf-tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .tf-fp-cols {{ height: 200px; }} .tf-fp-val {{ font-size: 20px; }} }}
.tf-tile {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; padding: 16px 18px; }}
.tf-tile .k {{ font-family: {DISPLAY}; font-weight: 700; font-size: 15px; letter-spacing: 0.04em;
  text-transform: uppercase; color: {MUTED}; line-height: 1.2; }}
.tf-tile .v {{ font-family: {DISPLAY}; font-size: 48px; font-weight: 800; margin-top: 6px; line-height: 1;
  font-variant-numeric: tabular-nums; }}
.tf-tile .b {{ font-size: 13px; color: {MUTED}; margin-top: 2px; }}

.tf-big {{ font-family: {DISPLAY}; font-size: clamp(80px, 12vw, 120px); font-weight: 800; line-height: 0.95;
  font-variant-numeric: tabular-nums; letter-spacing: 0; }}
.tf-sentence {{ font-size: 17px; line-height: 1.55; color: {TEXT}; max-width: 680px; }}
.tf-checks {{ display: flex; flex-direction: column; gap: 8px; }}
.tf-check {{ display: flex; gap: 12px; align-items: flex-start; background: {CARD}; border: 1px solid {LINE};
  border-radius: 12px; padding: 12px 14px; font-size: 15px; line-height: 1.5; }}
.tf-check .ic {{ flex: none; width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; font-weight: 600; font-size: 13px; margin-top: 1px; }}
.tf-rules {{ display: flex; flex-direction: column; gap: 8px; }}
.tf-rule {{ display: flex; gap: 12px; align-items: center; background: {CARD}; border: 1px solid {LINE};
  border-radius: 12px; padding: 12px 14px; font-size: 15px; }}
.tf-banner {{ border-radius: 14px; padding: 18px 20px; font-size: 18px; font-weight: 600; line-height: 1.45; }}
.tf-banner.bad {{ background: #2B1513; border: 1px solid #7A3530; color: #FFB8AC; }}
.tf-banner.good {{ background: #13261E; border: 1px solid #2B5A46; color: #A6EBCF; }}
.tf-banner small {{ display: block; font-size: 14px; font-weight: 500; color: {MUTED}; margin-top: 6px; }}
.tf-addr {{ font-family: {MONO}; font-size: 12px; color: {MUTED}; word-break: break-all; }}
.tf-empty {{ background: {CARD}; border: 1px dashed {LINE}; border-radius: 16px; padding: 48px 24px; text-align: center;
  color: {MUTED}; font-size: 17px; margin-top: 24px; }}
.tf-empty b {{ display: block; font-family: {DISPLAY}; font-weight: 800; font-size: 30px; text-transform: uppercase;
  letter-spacing: 0.02em; color: {TEXT}; margin-bottom: 8px; }}
.tf-entry {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 16px; padding: 24px; margin-bottom: 16px; }}
.tf-entry .k {{ font-family: {DISPLAY}; font-weight: 700; font-size: 15px; letter-spacing: 0.04em;
  text-transform: uppercase; color: {MUTED}; }}
.tf-entry .nm {{ font-family: {DISPLAY}; font-size: 40px; font-weight: 800; text-transform: uppercase;
  letter-spacing: 0.01em; line-height: 1; margin: 6px 0 16px; overflow-wrap: anywhere; }}
.tf-entry .tf-hold .row {{ padding: 10px 0; row-gap: 4px; }}
.tf-entry .tf-hold .tk {{ font-size: 15px; }}
.tf-entry .note {{ font-size: 13px; color: {MUTED}; margin-top: 12px; line-height: 1.45; }}
.tf-intro {{ margin: 32px 0 24px; }}
.tf-intro h2 {{ font-size: 40px; margin: 0; line-height: 1.1; }}
.tf-intro p {{ margin: 8px 0 0; color: {MUTED}; font-size: 16px; max-width: 760px; line-height: 1.55; }}
.tf-intro .modes {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }}
.tf-intro .modes span {{ font-size: 13px; background: {CARD}; border: 1px solid {LINE}; border-radius: 999px;
  padding: 6px 12px; color: {TEXT}; }}
.tf-intro .modes b {{ color: {BLUSH}; font-weight: 600; }}
.st-key-tf_qr {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 16px; padding: 24px; gap: 12px; }}
.st-key-tf_qr [data-testid="stImage"] img {{ border-radius: 12px; }}
.st-key-tf_qr [data-testid="stCode"] pre {{ font-size: 12px; background: {RAISED}; }}
.tf-qrtext h3 {{ font-family: {DISPLAY}; font-size: 26px; font-weight: 800; text-transform: uppercase; margin: 0 0 8px; }}
.tf-qrtext p {{ color: {MUTED}; font-size: 14px; line-height: 1.5; margin: 0; }}
.tf-entry .row {{ display: grid; grid-template-columns: 72px minmax(0, 1fr) 48px; gap: 12px; align-items: center;
  padding: 8px 0; border-top: 1px solid {LINE}; }}
.tf-entry .tk {{ font-family: {DISPLAY}; font-weight: 700; font-size: 19px; letter-spacing: 0.02em; }}
.tf-entry .bar {{ background: {RAISED}; border-radius: 6px; height: 8px; overflow: hidden; }}
.tf-entry .bar span {{ display: block; height: 100%; background: {ROSE}; border-radius: 6px; }}
.tf-entry .w {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; color: {MUTED}; }}
.tf-qr {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 16px; padding: 24px; text-align: center; }}
.tf-qr .code {{ display: inline-block; border-radius: 12px; overflow: hidden; line-height: 0; }}
.tf-qr .code svg {{ width: 232px; height: 232px; }}
.tf-qr h3 {{ font-size: 26px; margin: 16px 0 8px; }}
.tf-qr p {{ color: {MUTED}; font-size: 14px; line-height: 1.5; margin: 0 auto; max-width: 320px; }}
</style>
"""


def chip(text: str, kind: str) -> str:
    """A small rounded label. kind: want, avoid, or a tier name."""
    if kind == "want":
        bg, fg = ROSE_SOFT, BLUSH_TEXT
    elif kind == "avoid":
        bg, fg = CHAMPAGNE_SOFT, CHAMPAGNE
    else:
        bg, fg = TIER_STYLE.get(kind, TIER_STYLE["Not screened"])
    return f'<span class="tf-chip" style="background:{bg};color:{fg}">{escape(text)}</span>'


def hero(active_step: int = 0) -> str:
    """The page title over a slowly drifting rose-and-champagne gradient with fine grain. active_step is kept for
    older callers; the step pills are gone."""
    props = "".join(f"<span>{escape(p)}</span>" for p in
                    ("666 stocks scored on 10 themes", "Rules enforced on Monad", "Race your fund in the League"))
    return ('<div class="tf-hero"><div class="eyebrow">Built on Monad</div><h1>Theme Funds</h1>'
            '<p>Invest in what you believe in. Tell us the themes you want and the ones to avoid. We pick '
            'stocks by what they actually move with, not their labels, then lock your rules on Monad.</p>'
            f'<div class="props">{props}</div></div>')


def step(n: int, title: str, sentence: str) -> str:
    """A section heading. n is kept for older callers but no longer shown."""
    return f'<div class="tf-step"><h2>{escape(title)}</h2><p>{escape(sentence)}</p></div>'


def fingerprint(columns: list[dict]) -> str:
    """The fund's exposure to every theme as one row of columns.

    columns: [{"name", "pct" (0-100), "role": "want" | "avoid" | "none"}] in display order.
    """
    n = len(columns)
    cols, names = [], []
    for i, c in enumerate(columns):
        pct = max(0.0, min(100.0, float(c["pct"])))
        if c["role"] == "want":
            fill, val_color = ROSE, BLUSH
        elif c["role"] == "avoid":
            fill, val_color = (LOSS if pct > 0 else CHAMPAGNE), CHAMPAGNE
        else:
            fill, val_color = NEUTRAL_BAR, MUTED
        cols.append(f'<div class="tf-fp-col"><div class="tf-fp-val" style="color:{val_color}">{pct:.0f}%</div>'
                    f'<div class="tf-fp-bar" style="height:{max(pct, 1.2):.1f}%;background:{fill};'
                    f'--d:{i * 60}ms"></div></div>')
        role = {"want": "Want", "avoid": "Avoid"}.get(c["role"], "")
        names.append(f'<div><b>{escape(c["name"])}</b>{role}</div>')
    legend = (f'<div class="tf-fp-legend"><span><i style="background:{ROSE}"></i>A theme you want</span>'
              f'<span><i style="background:{CHAMPAGNE}"></i>A theme you avoid (should stay near 0%)</span>'
              f'<span><i style="background:{NEUTRAL_BAR}"></i>Not part of your choices</span></div>')
    return (f'<div class="tf-fp" role="img" aria-label="Share of the fund in High or Moderate stocks for each theme">'
            f'<div class="tf-fp-cols" style="--n:{n}">{"".join(cols)}</div>'
            f'<div class="tf-fp-names" style="--n:{n}">{"".join(names)}</div>{legend}</div>')


def funnel(steps: list[dict]) -> str:
    """steps: [{"step": text, "left": count}] from the builder."""
    if not steps:
        return ""
    top = max(1, steps[0]["left"])
    rows = []
    for s in steps:
        w = 100 * s["left"] / top
        rows.append(f'<div class="row"><div><div class="lbl">{escape(s["step"])}</div>'
                    f'<div class="bar"><span style="width:{max(w, 1.5):.1f}%"></span></div></div>'
                    f'<div class="num">{s["left"]:,}</div></div>')
    return f'<div class="tf-funnel">{"".join(rows)}</div>'


def holdings(rows: list[dict]) -> str:
    """rows: [{"ticker", "name", "industry", "weight", "chips": [html], "why" (optional one line)}]
    Each row: ticker, company, theme chips, weight, a weight bar (relative to the largest holding) and why it's in."""
    top = max([r["weight"] for r in rows] or [1]) or 1
    out = []
    for i, r in enumerate(rows):
        why = f'<div class="why">{escape(r["why"])}</div>' if r.get("why") else ""
        out.append(f'<div class="row"><span class="tk">{escape(r["ticker"])}</span>'
                   f'<div style="min-width:0"><div class="nm">{escape(r.get("name") or "")}</div>'
                   f'<div class="ind">{escape(r.get("industry") or "")}</div></div>'
                   f'<div class="tf-chips">{"".join(r.get("chips", []))}</div>'
                   f'<span class="w">{r["weight"]:.1f}%</span>'
                   f'<div class="bar"><span style="width:{100 * r["weight"] / top:.0f}%;animation-delay:{i * 30}ms">'
                   f'</span></div>{why}</div>')
    return f'<div class="tf-hold">{"".join(out)}</div>'


_NUM = re.compile(r"^([−+-]?)(\d+)(?:\.(\d{1,2}))?(%?)$")


def count_up(value: str) -> str:
    """A number that counts up from 0 when it first appears (CSS only; st.html runs no scripts). Text that
    isn't a plain number (e.g. "no loss") is shown as is."""
    m = _NUM.match(value)
    if not m:
        return escape(value)
    sign, whole, frac, pct = m.groups()
    if frac is None:
        return f'<span class="tf-count" style="--a:{int(whole)};--b:0">{sign}<span class="i"></span>{pct}</span>'
    style = "--fs:decimal-leading-zero" if len(frac) == 2 else ""
    return (f'<span class="tf-count" style="--a:{int(whole)};--b:{int(frac)};{style}">{sign}<span class="i"></span>.'
            f'<span class="f"></span>{pct}</span>')


def _sign_color(value: str) -> str:
    """A signed value is a return: mint when it starts with +, coral when it starts with a minus. Anything else
    (a probability, "no loss") keeps the normal text color."""
    v = value.strip()
    return GAIN if v.startswith("+") else LOSS if v.startswith(("−", "-")) else TEXT


def tiles(items: list[tuple[str, str, str]]) -> str:
    """items: [(label, value, comparison line)]. Values count up on first render; tiles rise in one by one."""
    cells = "".join(f'<div class="tf-tile" style="--d:{i * 60}ms"><div class="k">{escape(k)}</div>'
                    f'<div class="v" style="color:{_sign_color(v)}" aria-label="{escape(v)}">{count_up(v)}</div>'
                    f'<div class="b">{escape(b)}</div></div>' for i, (k, v, b) in enumerate(items))
    return f'<div class="tf-tiles">{cells}</div>'


def checks(items: list[tuple[bool, str]]) -> str:
    rows = []
    for ok, text in items:
        bg, fg, mark = ("#13261E", GAIN, "✓") if ok else ("#2B1513", LOSS, "!")
        rows.append(f'<div class="tf-check"><span class="ic" style="background:{bg};color:{fg}" '
                    f'aria-label="{"passes" if ok else "does not pass"}">{mark}</span><span>{text}</span></div>')
    return f'<div class="tf-checks">{"".join(rows)}</div>'


def rules(items: list[tuple[str, str]]) -> str:
    """items: [(kind want/avoid, plain-English rule)]"""
    rows = "".join(f'<div class="tf-rule">{chip("Want" if k == "want" else "Avoid", k)}<span>{escape(t)}</span></div>'
                   for k, t in items)
    return f'<div class="tf-rules">{rows}</div>'


def banner(text: str, good: bool, small: str = "") -> str:
    extra = f"<small>{escape(small)}</small>" if small else ""
    return f'<div class="tf-banner {"good" if good else "bad"}">{escape(text)}{extra}</div>'


def big_number(value: float, suffix: str = "%") -> str:
    color = GAIN if value > 0 else LOSS if value < 0 else TEXT
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f'<div class="tf-big" style="color:{color}">{sign}{abs(value):.1f}{suffix}</div>'


# ---------------------------------------------------------------------------------------------
# Plotly
# ---------------------------------------------------------------------------------------------

HEATMAP_COLORS = {  # tier -> cell color for the dark heatmap (same order as engine.dashboard.TIER_ORDER)
    "High": ROSE, "Moderate": "#5E2840", "Limited": "#173A2D", "Limited (lower confidence)": "#182A22",
    "Not determined": "#3A3020", "Not screened": "#1E191B",
}


def recolor_heatmap(fig, tier_order: list[str]):
    """Swap app.py's light heatmap colors for dark-theme ones. Same tiers, same cells; only colors change."""
    n = len(tier_order)
    scale = []
    for i, tier in enumerate(tier_order):
        color = HEATMAP_COLORS.get(tier, "#1E191B")
        scale += [[i / n, color], [(i + 1) / n, color]]
    fig.update_traces(colorscale=scale, textfont={"color": TEXT, "size": 13}, xgap=3, ygap=3)
    return plotly_dark(fig, height=fig.layout.height)


COLORWAY = [BLUSH, CHAMPAGNE, ROSE, GAIN, MUTED, "#E07A9B", "#D9B37A", LOSS]


def plotly_dark(fig, height: int | None = None):
    """Restyle any Plotly figure to match the page: palette colors, no gridline clutter, short eased transitions,
    clean hover labels."""
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": SANS, "color": TEXT, "size": 14}, colorway=COLORWAY,
        margin={"t": 30, "l": 10, "r": 10, "b": 10},
        hoverlabel={"bgcolor": CARD, "bordercolor": LINE, "font": {"family": SANS, "color": TEXT, "size": 13}},
        legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": MUTED}},
        transition={"duration": 300, "easing": "cubic-in-out"},
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE, tickfont={"color": MUTED})
    fig.update_yaxes(showgrid=True, gridcolor="rgba(46, 37, 41, .5)", zeroline=False, linecolor=LINE,
                     tickfont={"color": MUTED})
    if height:
        fig.update_layout(height=height)
    return fig


# ---------------------------------------------------------------------------------------------
# Fantasy Fund League tab
# ---------------------------------------------------------------------------------------------

def empty_state(text: str, title: str = "Nothing here yet") -> str:
    return f'<div class="tf-empty"><b>{escape(title)}</b>{escape(text)}</div>'


def league_entry(name: str, rows: list[dict], note: str = "") -> str:
    """The fund as it will be entered in the League: full name (wraps, never cut) over a compact holdings table.
    rows: same as holdings() (ticker, name, industry, weight, chips)."""
    extra = f'<div class="note">{escape(note)}</div>' if note else ""
    return (f'<div class="tf-entry"><div class="k">Your League entry</div><div class="nm">{escape(name)}</div>'
            f'{holdings(rows)}{extra}</div>')


def qr_card(svg: str, title: str, sentence: str) -> str:
    """svg comes from segno (generated locally), so it is inserted as is."""
    return (f'<div class="tf-qr"><div class="code">{svg}</div><h3>{escape(title)}</h3>'
            f'<p>{escape(sentence)}</p></div>')


def league_intro() -> str:
    """The League tab's heading: weekly matchups on live prices, plus today's simulated trading day."""
    return ('<div class="tf-intro"><h2>Fantasy Fund League</h2>'
            "<p>Put your fund up against everyone else's. Each week is a matchup on live market prices: entries "
            "lock Monday at 6:30 AM PT (market open) and the best return by Friday's close takes the pot. Today, "
            "with markets closed, we race a simulated trading day built from real market moves, 9:30 AM to "
            "4:00 PM in 60 seconds. Testnet MON only.</p>"
            '<div class="modes"><span><b>Weekly</b> · live prices · locks Mon 6:30 AM PT</span>'
            '<span><b>Today</b> · simulated trading day · 60-second race</span></div></div>')


def qr_text(title: str, sentence: str) -> str:
    return f'<div class="tf-qrtext"><h3>{escape(title)}</h3><p>{escape(sentence)}</p></div>'
