# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## About me
I am a finance student interested in conducting quantitative research on financial markets.

I want explanations of code and structures that someone who is non-technical could understand.

I prefer concise, direct communication without unnecessary jargon.

Every output should feel like advice from an experienced practitioner rather than a consultant or academic.

## Project overview: Theme Funds

Users choose which themes they want exposure to (e.g. Want AI, Avoid Oil). A Python engine classifies stocks by how closely their prices move with reference companies that have disclosed exposure to each theme. We build a portfolio from the user's choices, run a Monte Carlo risk simulation, then launch it as an on-chain fund token on Monad testnet whose rules can't be broken. Users aren't finance experts, so every result needs a plain-English sentence.

Built at Monad Blitz Oregon (Nov 15, 2026). The methodology comes from my prior capstone research.

## Methodology (never change this without asking me)

- Tiers: High / Moderate / Limited / Limited (lower confidence) / Not determined. There is NO Inverse tier.
- A theme is a YAML file in themes/: High and Moderate reference groups (ticker, evidence %, what it measures, fiscal year, source), one zero-exposure control, a direct_classification list (Tier 2), and an optional ground_truth ticker used ONLY for validation (never as a reference).
- Tier 1 = disclosed number → regression reference. Tier 2 = exposed but no disclosed number → classified directly, never a regression reference.
- Picking references (approved): High = theme is >= 40% of revenue, Moderate = 5-40%. AI uses my capstone numbers as given. Approved exceptions: Healthcare and Cybersecurity have 1 Moderate reference each.
- Evidence comes from FMP data only (segment revenue share, income-statement ratios, industry). No SEC filings. Never estimated. No disclosed number → Tier 2.
- Data: ~2 years of daily dividend-adjusted closes from FMP (fallback yfinance), cached. Simple daily returns, inner-join dates, no forward fill.
- For each holding and theme, OLS (statsmodels): r_holding = a + b*SPY + b*TLT + sum of b_j * r_reference_j + error. (Interest-rates theme drops TLT from its controls.)
- For each group: sum the betas, SE from the full covariance matrix, one-sided test of sum > 0.
- A group is eligible if sum > 0.05 AND one-sided p < 0.05 / (number of reference names). The largest eligible sum wins.
- Limited: nothing eligible AND every group's sum + 1.645*SE < 0.05. Plain text: "doesn't rise with this theme."
- Limited (lower confidence): otherwise, if all group sums < 0.05.
- Otherwise Not determined: "the data can't tell", which is NOT the same as zero.
- A holding that is a reference or on the direct list uses its listed tier, with no regression.
- Cash is kept at its weight and not scored.
- Portfolio fingerprint: % of weight that's High+Moderate for each theme.

## Build phases

Work in phases. STOP at each checkpoint so I can check before continuing. Commit and push after every phase.

0. Setup: folders, venv, .gitignore, .env.example, README, this file.
1. FMP client: engine/fmp.py (stable API, key from .env, every response cached in data/cache/fmp/). Test the endpoints on NVDA and XOM. → Checkpoint 1
2. Themes: AI (my reference set exactly), then Oil, then the others (time-boxed to 30 minutes). → Checkpoint 2: one summary table per theme
3. Price data + regression: engine/data.py get_returns(), engine/regression.py, tests on simulated then real data, price check per theme. → Checkpoint 3
4. Portfolio screen: engine/screen.py run_screen(holdings, themes) → JSON; CLI `python -m engine.screen NVDA:30 XOM:20 CASH:50`. → Checkpoint 4

### Later phases (don't build yet)

5. Builder: preferences like {"AI": "want", "Oil": "avoid"} → universe of ~30–40 tickers → "want" keeps High/Moderate, "avoid" keeps only proven Limited (Not determined is excluded) → weight High 2 / Moderate 1, cap 15%, rescale → re-screen to verify.
6. Monte Carlo: 5-day block bootstrap, 5,000 paths, 252 days, fixed seed, vs SPY; fan chart, P(loss > 10%), 5% VaR/CVaR; theme shocks via betas (e.g. Oil +30%), labeled "estimated sensitivity based on past co-movement".
7. Blockchain (deployer wallet via Foundry keystore; chain/publish.py posts engine results to the oracle):
   - ExposureOracle: owner posts ticker / theme / tier / price / baselineHash / statsHash / timestamp. Prices use 8 decimals.
   - MockUSDC: ERC-20 test dollars, 6 decimals, public faucet(). MockStock: one ERC-20 per ticker, 18 decimals. Only MockExchange can mint or burn either.
   - MockExchange: buy(stock, usdcAmount) takes USDC and mints stock at the oracle price; sell(stock, qty) burns stock and mints USDC at the oracle price. Reverts if a price is missing or older than 7 days.
   - ThemeFund (ERC-20 shares): deposit → buy the basket through the exchange at target weights → mint shares at NAV (first deposit: 1 share = $1). redeem → sell a pro-rata slice of each holding → pay USDC → burn shares. NAV = sum(qty × oracle price) + cash. addHolding / rebalance check the mandate against ExposureOracle BEFORE trading and revert with a clear reason, e.g. "Mandate: Oil exposure too high".
   - ThemeFundFactory: creates a ThemeFund with name, symbol, basket, rules.
   - Tests: deposit then redeem with no price change returns about the same USDC; a price rise increases NAV; adding XOM to an Avoid-Oil fund reverts; a stale price reverts.
8. Streamlit dashboard: Want / Don't care / Avoid per theme → Build → heatmap + audit trail → Monte Carlo + shock buttons → Launch fund on Monad (explorer link) → Deposit → "Try adding XOM" shows the rejection in red.

## Rules

- Never print or commit API keys or private keys. Never read .env contents into the chat.
- Small testable steps. Plain-English comments.

## Network

- Monad testnet, chain ID `10143`
- RPC: `https://testnet-rpc.monad.xyz` (set as `MONAD_RPC_URL` in `.env`)
- Foundry endpoint name: `monad` (e.g. `forge script ... --rpc-url monad`), or `FOUNDRY_PROFILE=monad`

## Workflow rules

**Always present a concise written plan and wait for my approval before beginning a multi-step or complex task.**

For coding tasks, follow the steps in [workflows/coding_workflow.md](workflows/coding_workflow.md), with one exception for this project: build directly in `engine/`, `themes/`, `contracts/`, `chain/` and `app.py` instead of `drafts/` and `outputs/`.

## Structure

```
theme-funds/
├── CLAUDE.md          # guidance for Claude (this file)
├── README.md          # what the project is and how to run it
├── workflows/         # workflow instructions and process documents
├── engine/            # Python exposure engine (FMP client, data, regression, screen)
├── themes/            # theme definitions (YAML)
├── contracts/         # Foundry project: Solidity contracts, tests, deploy scripts
├── chain/             # Python (web3.py) code that talks to the contracts
├── data/cache/        # cached API responses and prices (gitignored)
├── requirements.txt   # Python dependencies
└── .env.example       # placeholder settings; copy to .env (never commit .env)
```

## Agent Behavior

Before starting any task:
1. Understand the objective
2. Ask clarifying questions as needed
3. Map out a plan
4. Execute step by step
5. Review the output
6. Make improvements to weak areas
7. Deliver the final result

Important: Never skip planning for complex tasks.

Don't prioritize speed over quality.

Optimize for usefulness.

## File naming rules

Use underscores (_) to separate words in Python and other files. Exception: Solidity files follow the Solidity convention of one contract per file named after the contract (e.g. `ThemeFund.sol`).

Always use lowercase numbers.
