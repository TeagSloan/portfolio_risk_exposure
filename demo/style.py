"""Colors, fonts and small HTML building blocks for demo_app.py.

Nothing here computes a number. Every function takes values the engine already produced and
returns HTML (or restyles a Plotly figure) so the dashboard looks like one product with the
League page: dark background, one violet accent, orange for "avoid", green/red only for gains
and losses (always with a + or - sign).
"""

from __future__ import annotations

from html import escape

# ---------------------------------------------------------------------------------------------
# Palette and type (shared with the League page design)
# ---------------------------------------------------------------------------------------------

INK = "#0E0F14"          # page background
CARD = "#171922"         # panels
RAISED = "#1F2230"       # inputs, hover
LINE = "#262A38"         # borders
TEXT = "#F2F3F7"
MUTED = "#9AA1B5"
VIOLET = "#8B7CF6"       # the one accent: "want", buttons, the fund itself
VIOLET_SOFT = "#2A2350"
BUTTON = "#6E5CE6"       # violet dark enough for white button text (4.5:1)
AMBER = "#FF9F5A"        # "avoid"
AMBER_SOFT = "#3A2417"
GAIN = "#3ECF8E"
LOSS = "#F2555A"

TIER_STYLE = {  # (background, text) per tier, readable on dark
    "High": ("#2A2350", "#DCD6FF"),
    "Moderate": ("#232042", "#B9B0F7"),
    "Limited": ("#1C2A24", "#7FD9AE"),
    "Limited (lower confidence)": ("#1C2622", "#9CCFB6"),
    "Not determined": ("#2C2618", "#E5C07B"),
    "Not screened": ("#1E222B", MUTED),
}

FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
         "&family=Space+Grotesk:wght@500;600;700&display=swap")

CSS = f"""
<style>
@import url('{FONTS}');
html, body, .stApp, .stMarkdown, p, label, input, textarea, button {{ font-family: Inter, system-ui, sans-serif; }}
.stApp {{ background: {INK}; color: {TEXT}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {{ display: none; }}
.block-container {{ max-width: 1240px; padding-top: 2.2rem; padding-bottom: 6rem; }}
h1, h2, h3 {{ font-family: 'Space Grotesk', Inter, sans-serif !important; letter-spacing: -0.02em; color: {TEXT}; }}
p, li, label, .stMarkdown {{ color: {TEXT}; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED} !important; }}
[data-testid="stWidgetLabel"] p {{ color: {TEXT}; font-weight: 600; }}
.stButton > button, .stLinkButton > a {{ border-radius: 10px; min-height: 44px; font-weight: 600; }}
[data-testid="stBaseButton-primary"], .stButton button[kind="primary"] {{ background: {BUTTON}; border: 0; color: #fff; }}
[data-testid="stBaseButton-primary"]:hover, .stButton button[kind="primary"]:hover {{ background: #5F4CD9; color: #fff; }}
[data-testid="stBaseButton-primary"] p, .stButton button[kind="primary"] p {{ color: #fff; font-weight: 600; }}
[data-testid="stBaseButton-secondary"] {{ background: {RAISED}; border: 1px solid {LINE}; color: {TEXT}; }}
[data-testid="stExpander"] {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
[data-testid="stMetricValue"] {{ font-family: 'Space Grotesk', sans-serif; }}
div[data-baseweb="select"] > div, input, textarea {{ background: {RAISED} !important; color: {TEXT} !important; }}
:focus-visible {{ outline: 2px solid {VIOLET} !important; outline-offset: 2px; }}

.tf-hero {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 24px;
  padding-bottom: 28px; border-bottom: 1px solid {LINE}; margin-bottom: 8px; }}
.tf-hero h1 {{ font-size: 64px; line-height: 0.95; margin: 0; font-weight: 700; }}
.tf-hero p {{ margin: 12px 0 0; color: {MUTED}; font-size: 18px; max-width: 620px; line-height: 1.5; }}
.tf-steps {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.tf-steps span {{ font-size: 14px; color: {MUTED}; border: 1px solid {LINE}; border-radius: 999px; padding: 6px 12px; }}
.tf-steps span.on {{ color: {TEXT}; border-color: {VIOLET}; background: {VIOLET_SOFT}; }}

.tf-step {{ display: flex; gap: 18px; align-items: baseline; margin: 56px 0 18px; }}
.tf-step .n {{ font-family: 'Space Grotesk', sans-serif; font-size: 20px; font-weight: 700; color: {INK};
  background: {VIOLET}; width: 40px; height: 40px; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; flex: none; transform: translateY(6px); }}
.tf-step h2 {{ font-size: 36px; margin: 0; line-height: 1.1; }}
.tf-step p {{ margin: 6px 0 0; color: {MUTED}; font-size: 16px; max-width: 720px; line-height: 1.5; }}

.tf-fp {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 18px; padding: 28px 28px 18px; }}
.tf-fp-cols {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 12px; align-items: end;
  height: 260px; border-bottom: 1px solid {LINE}; }}
.tf-fp-col {{ position: relative; height: 100%; display: flex; flex-direction: column; justify-content: flex-end;
  align-items: stretch; }}
.tf-fp-bar {{ border-radius: 8px 8px 2px 2px; min-height: 3px; transform-origin: bottom;
  animation: tf-grow 900ms cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d); }}
.tf-fp-val {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 22px; margin-bottom: 6px;
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
.tf-funnel .bar span {{ display: block; height: 100%; background: {VIOLET}; border-radius: 6px; }}
.tf-funnel .num {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 22px; text-align: right;
  font-variant-numeric: tabular-nums; line-height: 1; }}

.tf-hold {{ display: flex; flex-direction: column; }}
.tf-hold .row {{ display: grid; grid-template-columns: 76px minmax(0, 1fr) auto 64px; gap: 14px; align-items: center;
  padding: 12px 4px; border-top: 1px solid {LINE}; }}
.tf-hold .row:first-child {{ border-top: 0; }}
.tf-hold .tk {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 18px; }}
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
.tf-tile .v {{ font-family: 'Space Grotesk', sans-serif; font-size: 34px; font-weight: 700; margin-top: 4px;
  font-variant-numeric: tabular-nums; }}
.tf-tile .b {{ font-size: 13px; color: {MUTED}; margin-top: 2px; }}

.tf-big {{ font-family: 'Space Grotesk', sans-serif; font-size: 88px; font-weight: 700; line-height: 1;
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
.tf-banner.bad {{ background: #2A1518; border: 1px solid #6A2A30; color: #FFB3AE; }}
.tf-banner.good {{ background: #14281F; border: 1px solid #2A5A44; color: #9EEBC6; }}
.tf-banner small {{ display: block; font-size: 14px; font-weight: 500; color: {MUTED}; margin-top: 6px; }}
.tf-addr {{ font-family: ui-monospace, Menlo, monospace; font-size: 14px; color: {MUTED}; word-break: break-all; }}
</style>
"""


def chip(text: str, kind: str) -> str:
    """A small rounded label. kind: want, avoid, or a tier name."""
    if kind == "want":
        bg, fg = VIOLET_SOFT, "#DCD6FF"
    elif kind == "avoid":
        bg, fg = AMBER_SOFT, "#FFC9A3"
    else:
        bg, fg = TIER_STYLE.get(kind, TIER_STYLE["Not screened"])
    return f'<span class="tf-chip" style="background:{bg};color:{fg}">{escape(text)}</span>'


def hero(active_step: int) -> str:
    steps = ["Choose themes", "See what you own", "Stress test", "Launch on Monad"]
    pills = "".join(f'<span class="{"on" if i + 1 <= active_step else ""}">{i + 1}. {s}</span>'
                    for i, s in enumerate(steps))
    return ('<div class="tf-hero"><div><h1>Theme Funds</h1>'
            '<p>Tell us the themes you want and the ones you want to avoid. We pick stocks by what they '
            'actually move with, not their labels, then launch the fund on Monad with rules nobody can break.</p>'
            f'</div><div class="tf-steps">{pills}</div></div>')


def step(n: int, title: str, sentence: str) -> str:
    return (f'<div class="tf-step"><span class="n" aria-hidden="true">{n}</span><div>'
            f'<h2>{escape(title)}</h2><p>{escape(sentence)}</p></div></div>')


def fingerprint(columns: list[dict]) -> str:
    """The fund's exposure to every theme as one row of columns.

    columns: [{"name", "pct" (0-100), "role": "want" | "avoid" | "none"}] in display order.
    """
    n = len(columns)
    cols, names = [], []
    for i, c in enumerate(columns):
        pct = max(0.0, min(100.0, float(c["pct"])))
        if c["role"] == "want":
            fill, val_color = VIOLET, "#DCD6FF"
        elif c["role"] == "avoid":
            fill, val_color = (LOSS if pct > 0 else AMBER), "#FFC9A3"
        else:
            fill, val_color = "#3A3F52", MUTED
        cols.append(f'<div class="tf-fp-col"><div class="tf-fp-val" style="color:{val_color}">{pct:.0f}%</div>'
                    f'<div class="tf-fp-bar" style="height:{max(pct, 1.2):.1f}%;background:{fill};'
                    f'--d:{i * 60}ms"></div></div>')
        role = {"want": "Want", "avoid": "Avoid"}.get(c["role"], "")
        names.append(f'<div><b>{escape(c["name"])}</b>{role}</div>')
    legend = (f'<div class="tf-fp-legend"><span><i style="background:{VIOLET}"></i>A theme you want</span>'
              f'<span><i style="background:{AMBER}"></i>A theme you avoid (should stay near 0%)</span>'
              f'<span><i style="background:#3A3F52"></i>Not part of your choices</span></div>')
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
        bg, fg, mark = ("#14281F", GAIN, "✓") if ok else ("#2A1518", LOSS, "!")
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
    "High": "#6E5CE6", "Moderate": "#3E3580", "Limited": "#1C3A2E", "Limited (lower confidence)": "#1A2A24",
    "Not determined": "#3A3020", "Not screened": "#1E222B",
}


def recolor_heatmap(fig, tier_order: list[str]):
    """Swap app.py's light heatmap colors for dark-theme ones. Same tiers, same cells; only colors change."""
    n = len(tier_order)
    scale = []
    for i, tier in enumerate(tier_order):
        color = HEATMAP_COLORS.get(tier, "#1E222B")
        scale += [[i / n, color], [(i + 1) / n, color]]
    fig.update_traces(colorscale=scale, textfont={"color": TEXT, "size": 13}, xgap=3, ygap=3)
    return plotly_dark(fig, height=fig.layout.height)


def plotly_dark(fig, height: int | None = None):
    """Restyle any Plotly figure to match the page."""
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "color": TEXT, "size": 14},
        margin={"t": 30, "l": 10, "r": 10, "b": 10}, hoverlabel={"bgcolor": CARD, "bordercolor": LINE},
        legend={"bgcolor": "rgba(0,0,0,0)"},
    )
    fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    if height:
        fig.update_layout(height=height)
    return fig
