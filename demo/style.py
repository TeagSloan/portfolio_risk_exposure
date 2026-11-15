"""Colors, fonts and small HTML building blocks for demo_app.py.

Nothing here computes a number. Every function takes values the engine already produced and
returns HTML (or restyles a Plotly figure) so the dashboard looks like one product with the
League page: black background, rose for buttons and "want", champagne gold for "avoid", mint and
coral only for gains and losses (always with a + or - sign). Headings and big numbers use a serif
(Fraunces) so it reads like a private bank, body text a clean sans (Manrope).
"""

from __future__ import annotations

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

FONTS = ("https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700"
         "&family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&display=swap")
SERIF = "Fraunces, Georgia, serif"
SANS = "Manrope, system-ui, sans-serif"

CSS = f"""
<style>
@import url('{FONTS}');
html, body, .stApp, .stMarkdown, p, label, input, textarea, button {{ font-family: {SANS}; }}
.stApp {{ background: {INK}; color: {TEXT}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {{ display: none; }}
.block-container {{ max-width: 1240px; padding-top: 2.2rem; padding-bottom: 6rem; }}
h1, h2, h3 {{ font-family: {SERIF} !important; font-weight: 500 !important; letter-spacing: -0.01em; color: {TEXT}; }}
p, li, label, .stMarkdown {{ color: {TEXT}; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED} !important; }}
[data-testid="stWidgetLabel"] p {{ color: {TEXT}; font-weight: 600; }}
.stButton > button, .stLinkButton > a {{ border-radius: 10px; min-height: 44px; font-weight: 600; }}
[data-testid="stBaseButton-primary"], .stButton button[kind="primary"] {{ background: {ROSE}; border: 0; color: #fff; }}
[data-testid="stBaseButton-primary"]:hover, .stButton button[kind="primary"]:hover {{ background: {ROSE_HOVER}; color: #fff; }}
[data-testid="stBaseButton-primary"] p, .stButton button[kind="primary"] p {{ color: #fff; font-weight: 600; }}
[data-testid="stBaseButton-secondary"] {{ background: {RAISED}; border: 1px solid {LINE}; color: {TEXT}; }}
[data-testid="stExpander"] {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
[data-testid="stMetricValue"] {{ font-family: {SERIF}; }}
[data-testid="stTabs"] button p {{ font-size: 16px; font-weight: 600; }}
[data-testid="stTabs"] [aria-selected="true"] p {{ color: {BLUSH}; }}
div[data-baseweb="select"] > div, input, textarea {{ background: {RAISED} !important; color: {TEXT} !important; }}
:focus-visible {{ outline: 2px solid {BLUSH} !important; outline-offset: 2px; }}

.tf-hero {{ padding: 8px 0 32px; border-bottom: 1px solid {LINE}; margin-bottom: 8px; }}
.tf-hero h1 {{ font-size: 76px; line-height: 0.95; margin: 0; font-weight: 500 !important; letter-spacing: -0.025em; }}
.tf-hero p {{ margin: 16px 0 0; color: {MUTED}; font-size: 19px; max-width: 640px; line-height: 1.55; }}

.tf-step {{ margin: 64px 0 20px; padding-top: 28px; border-top: 1px solid {LINE}; }}
.tf-step h2 {{ font-size: 40px; margin: 0; line-height: 1.1; }}
.tf-step p {{ margin: 8px 0 0; color: {MUTED}; font-size: 16px; max-width: 720px; line-height: 1.55; }}

.tf-fp {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 18px; padding: 28px 28px 18px; }}
.tf-fp-cols {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 12px; align-items: end;
  height: 260px; border-bottom: 1px solid {LINE}; }}
.tf-fp-col {{ position: relative; height: 100%; display: flex; flex-direction: column; justify-content: flex-end;
  align-items: stretch; }}
.tf-fp-bar {{ border-radius: 8px 8px 2px 2px; min-height: 3px; transform-origin: bottom;
  animation: tf-grow 900ms cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d); }}
.tf-fp-val {{ font-family: {SERIF}; font-weight: 500; font-size: 22px; margin-bottom: 6px;
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
.tf-funnel .num {{ font-family: {SERIF}; font-weight: 500; font-size: 24px; text-align: right;
  font-variant-numeric: tabular-nums; line-height: 1; }}

.tf-hold {{ display: flex; flex-direction: column; }}
.tf-hold .row {{ display: grid; grid-template-columns: 76px minmax(0, 1fr) auto 64px; gap: 14px; align-items: center;
  padding: 12px 4px; border-top: 1px solid {LINE}; }}
.tf-hold .row:first-child {{ border-top: 0; }}
.tf-hold .tk {{ font-family: {SANS}; font-weight: 700; font-size: 16px; letter-spacing: 0.02em; }}
.tf-hold .nm {{ font-size: 14px; color: {TEXT}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.tf-hold .ind {{ font-size: 13px; color: {MUTED}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.tf-hold .w {{ text-align: right; font-variant-numeric: tabular-nums; color: {MUTED}; }}
.tf-chips {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}
.tf-chip {{ font-size: 12px; font-weight: 600; padding: 4px 9px; border-radius: 999px; white-space: nowrap; }}

.tf-tiles {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
@media (max-width: 900px) {{ .tf-tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .tf-hero h1 {{ font-size: 44px; }} .tf-fp-cols {{ height: 200px; }} }}
.tf-tile {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; padding: 16px 18px; }}
.tf-tile .k {{ font-size: 13px; color: {MUTED}; }}
.tf-tile .v {{ font-family: {SERIF}; font-size: 36px; font-weight: 500; margin-top: 4px;
  font-variant-numeric: tabular-nums; }}
.tf-tile .b {{ font-size: 13px; color: {MUTED}; margin-top: 2px; }}

.tf-big {{ font-family: {SERIF}; font-size: 96px; font-weight: 500; line-height: 1;
  font-variant-numeric: tabular-nums; letter-spacing: -0.03em; }}
.tf-sentence {{ font-size: 17px; line-height: 1.55; color: {TEXT}; max-width: 680px; }}
.tf-checks {{ display: flex; flex-direction: column; gap: 8px; }}
.tf-check {{ display: flex; gap: 12px; align-items: flex-start; background: {CARD}; border: 1px solid {LINE};
  border-radius: 12px; padding: 12px 14px; font-size: 15px; line-height: 1.5; }}
.tf-check .ic {{ flex: none; width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; font-weight: 700; font-size: 13px; margin-top: 1px; }}
.tf-rules {{ display: flex; flex-direction: column; gap: 8px; }}
.tf-rule {{ display: flex; gap: 12px; align-items: center; background: {CARD}; border: 1px solid {LINE};
  border-radius: 12px; padding: 12px 14px; font-size: 15px; }}
.tf-banner {{ border-radius: 14px; padding: 18px 20px; font-size: 18px; font-weight: 600; line-height: 1.45; }}
.tf-banner.bad {{ background: #2B1513; border: 1px solid #7A3530; color: #FFB8AC; }}
.tf-banner.good {{ background: #13261E; border: 1px solid #2B5A46; color: #A6EBCF; }}
.tf-banner small {{ display: block; font-size: 14px; font-weight: 500; color: {MUTED}; margin-top: 6px; }}
.tf-addr {{ font-family: ui-monospace, Menlo, monospace; font-size: 14px; color: {MUTED}; word-break: break-all; }}
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
    """The page title. active_step is kept for older callers; the step pills are gone."""
    return ('<div class="tf-hero"><h1>Theme Funds</h1>'
            '<p>Invest in what you believe in. Tell us the themes you want and the ones to avoid. We pick '
            'stocks by what they actually move with, not their labels, then lock your rules on Monad.</p></div>')


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
    """rows: [{"ticker", "name", "industry", "weight", "chips": [html]}]"""
    out = []
    for r in rows:
        out.append(f'<div class="row"><span class="tk">{escape(r["ticker"])}</span>'
                   f'<div style="min-width:0"><div class="nm">{escape(r.get("name") or "")}</div>'
                   f'<div class="ind">{escape(r.get("industry") or "")}</div></div>'
                   f'<div class="tf-chips">{"".join(r.get("chips", []))}</div>'
                   f'<span class="w">{r["weight"]:.1f}%</span></div>')
    return f'<div class="tf-hold">{"".join(out)}</div>'


def tiles(items: list[tuple[str, str, str]]) -> str:
    """items: [(label, value, comparison line)]"""
    cells = "".join(f'<div class="tf-tile"><div class="k">{escape(k)}</div><div class="v">{escape(v)}</div>'
                    f'<div class="b">{escape(b)}</div></div>' for k, v, b in items)
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


def plotly_dark(fig, height: int | None = None):
    """Restyle any Plotly figure to match the page."""
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": SANS, "color": TEXT, "size": 14},
        margin={"t": 30, "l": 10, "r": 10, "b": 10}, hoverlabel={"bgcolor": CARD, "bordercolor": LINE},
        legend={"bgcolor": "rgba(0,0,0,0)"},
    )
    fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    if height:
        fig.update_layout(height=height)
    return fig
