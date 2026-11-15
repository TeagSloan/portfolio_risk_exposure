# CLAUDE.md

This file provides a guidance to claude code when working in this repository

## About me
I am a finance student interested in conducting quantitative research on financial markets.

I want explanations of code and structures that someone who is non-technical could understand.

I prefer concise, direct communication without unnecessary jargon

Every output should feel like advice from an experienced practitioner rather than a consultant or academic

## Project overview

**Theme Funds** (built at Monad Blitz Oregon, Nov 15, 2026). Users choose which themes they
want exposure to (e.g. Want AI, Avoid Oil). A Python engine classifies stocks by how closely
their prices move with reference companies that have disclosed exposure to each theme. We
build a portfolio from the user's choices, run a Monte Carlo risk simulation, then launch it
as an on-chain fund token on Monad testnet whose rules can't be broken. Users aren't finance
experts, so **every result needs a plain-English sentence**.

The methodology comes from my prior capstone research.

## Workflow rules

**Always present a concise written plan and wait for my approval before beginning a multi-step or complex task**

For coding tasks, follow the steps in [workflows/coding_workflow.md](workflows/coding_workflow.md).

### Hackathon rules (override the coding workflow for this project)

- Work on branch `Wes` until told otherwise.
- Work in phases. STOP at each checkpoint so I can check before continuing.
- Commit and push after every phase.
- Never print or commit API keys or personal contact details. They live only in `.env`
  (git-ignored). `.env.example` holds placeholders only.
- Quality bar per phase: tests + linter (`ruff check .`) + an end-to-end run. Report test
  coverage but don't gate on it. Run the full eight-point check from the coding workflow
  before the demo.
- Code lives in `engine/`, `themes/`, `chain/` and `contracts/` (not `drafts/` / `outputs/`).

## Methodology (LOCKED: never change without asking me)

- Tiers: High / Moderate / Limited / Limited (lower confidence) / Not determined.
  There is NO Inverse tier.
- A theme is a YAML file in `themes/`: High and Moderate reference groups (ticker, evidence %,
  what it measures, fiscal year, source), one zero-exposure control, a `direct_classification`
  list (Tier 2), and an optional `ground_truth` ticker used ONLY for validation (never as a
  reference).
- Tier 1 = disclosed number → regression reference. Tier 2 = exposed but no disclosed number →
  classified directly, never a regression reference.
- Data: ~2 years of daily dividend-adjusted closes from FMP (fallback yfinance), cached.
  Simple daily returns, inner-join dates, no forward fill.
- For each holding and theme, OLS (statsmodels):
  `r_holding = a + b*SPY + b*TLT + sum of b_j * r_reference_j + b_c * r_control + error`.
  (The interest-rates theme drops TLT from its controls.)
  - The zero-exposure control IS included in the regression as a regressor, but is NOT
    part of any group's sum. (Confirmed by Wes.)
- For each group: sum the betas, SE from the full covariance matrix, one-sided test of sum > 0.
- A group is eligible if sum > 0.05 AND one-sided p < 0.05 / (number of reference names
  **in that group**). (Confirmed by Wes: the denominator is per group.) The largest eligible
  sum wins.
- Limited: nothing eligible AND every group's sum + 1.645*SE < 0.05.
  Plain text: "doesn't rise with this theme."
- Limited (lower confidence): otherwise, if all group sums < 0.05.
- Otherwise Not determined: "the data can't tell", which is NOT the same as zero.
- A holding that is a reference or on the direct list uses its listed tier, with no regression.
- Cash is kept at its weight and not scored.
- Portfolio fingerprint: % of weight that's High+Moderate for each theme.

## Phases

0. Setup (done): folders, venv, `.gitignore`, `.env.example`, README, Foundry project.
1. FMP client: `engine/fmp.py`, every response cached in `data/cache/fmp/`. CHECKPOINT 1.
2. Themes: AI (Wes's reference set, exactly), Oil, then 8 more themes with a 30-minute cap.
   CHECKPOINT 2.
3. Price data + regression: `engine/data.py`, `engine/regression.py`, price checks.
   CHECKPOINT 3.
4. Portfolio screen: `engine/screen.py`, `python -m engine.screen NVDA:30 XOM:20 CASH:50`.
   CHECKPOINT 4.

### Later phases (not built yet)

4b. **"Ask about your fund" assistant** (pulled forward for the demo): `engine/assistant.py`
    calls the Claude API with a system prompt holding the fund's facts (holdings, tiers,
    fingerprint; later Monte Carlo, frontier position, contract address, mandate rules).
    Rules for the assistant: answer only from those facts; "Not determined" means "the data
    can't tell"; no predictions or buy/sell advice; plain English. Key from `.env`
    (`ANTHROPIC_API_KEY`).
5. Builder: preferences like `{"AI": "want", "Oil": "avoid"}` → universe of ~30–40 tickers →
   "want" keeps High/Moderate, "avoid" keeps only proven Limited (Not determined is excluded)
   → weight High 2 / Moderate 1, cap 15%, rescale → re-screen to verify.
6. Risk: Monte Carlo with a 5-day block bootstrap, 5,000 paths, 252 days, fixed seed, vs SPY;
   fan chart, P(loss > 10%), 5% VaR/CVaR; theme shocks via betas (e.g. Oil +30%), labeled
   "estimated sensitivity based on past co-movement". Plus the **mean-variance view**
   (`engine/mean_variance/`): the built fund plotted against the efficient frontier, capital
   market line, minimum-variance and tangency portfolios of its own holdings, with a plain
   sentence. This is a check only; it never changes the builder's weights.
7. Blockchain: deployer wallet via Foundry keystore; ExposureOracle (post
   ticker/theme/tier/price/baselineHash/statsHash), MockStock ERC-20s, ThemeFund (deposit →
   mint at NAV, redeem → burn, mandate rules per theme; adding a holding that breaks a rule
   reverts, e.g. "Mandate: Oil exposure too high"), ThemeFundFactory; `chain/publish.py`
   posts results to the oracle. Weekend demo: replay recent real prices at accelerated speed
   so the fund value visibly moves.
8. Streamlit dashboard: Want / Don't care / Avoid per theme → Build → heatmap + audit trail →
   Monte Carlo + shock buttons → mean-variance chart → Launch fund on Monad (explorer link) →
   Deposit → "Try adding XOM" shows the rejection in red → "Ask about your fund" chat.

## Structure

```
portfolio_risk_exposure/
├── CLAUDE.md          # guidance for Claude (this file)
├── README.md          # project overview and setup
├── workflows/         # workflow instructions and process documents
├── engine/            # Python engine: data, regression, screen, builder, risk
│   └── mean_variance/ # efficient frontier / CML tool
├── themes/            # one YAML file per theme
├── chain/             # Python scripts that talk to Monad
├── contracts/         # Foundry project (Solidity)
├── tests/             # automated tests
└── data/cache/        # downloaded data (git-ignored)
```

## Agent Behavior

Before starting any task:
1. Understand the objective
2. Ask clarifying questions as needed
3. Map out a plan
4. Execute step by step
5. review the output
6. Make improvements to weak areas
7. Deliver the final result

Important: Never skip planning for complex tasks

Don't prioritize speed over quality

Optimize for usefulness

## File naming rules

Use underscores (_) to separate words

Always use lowercase numbers
