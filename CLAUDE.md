# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## About me
I am a finance student interested in conducting quantitative research on financial markets.

I want explanations of code and structures that someone who is non-technical could understand.

I prefer concise, direct communication without unnecessary jargon.

Every output should feel like advice from an experienced practitioner rather than a consultant or academic.

## TOP-LEVEL GOAL (read first; everything else serves this)

**Theme Funds: two ways in, one regression engine.** Users aren't finance experts, so every result needs a plain-English sentence.

**Way 1: "Check my portfolio" (stocks → exposure).** The user enters any NYSE/NASDAQ stocks + weights. Each stock is run through the regression for every theme (AI, Oil, Gold, Aerospace & defense, Healthcare, Copper+lithium, Clean energy, Consumer discretionary, Cybersecurity, Bank lending). Show the % of the portfolio exposed to each theme, each stock's tier, a plain-English sentence and the audit trail. Stocks not already scored are pulled live from FMP.

**Way 2: "Build my ETF" (preferences → stocks).** The user picks Want / Don't care / Avoid per theme (e.g. high AI, low Oil) + region. We pick individual stocks only (no ETFs, funds or bonds) from a universe of NYSE + NASDAQ stocks (top ~500 US + ~150 international ADRs, market cap >= $2B) that were ALL run through the regression ahead of time and saved in an exposure table. Equal weight, 15% cap. Show the funnel (how many stocks survive each rule), then re-check the result with Way 1.

**The regression (the core, current focus).** Each theme is its own regression of a stock on SPY, TLT, style controls, the theme's control company and its reference companies (disclosed exposure from filings). Tier rules as in the Methodology section. It must score ANY stock on EVERY theme, quickly and at scale (vectorized), and match run_screen exactly.

**After either way (later).** Monte Carlo risk view, then launch the portfolio on Monad as a fund token whose preferences become on-chain rules.

Built at Monad Blitz Oregon (Nov 15, 2026). The methodology comes from my prior capstone research.

## Methodology (never change this without asking me)

- Tiers: High / Moderate / Limited / Limited (lower confidence) / Not determined. There is NO Inverse tier.
- A theme is a YAML file in themes/: High and Moderate reference groups (ticker, evidence %, what it measures, fiscal year, source), one zero-exposure control, a direct_classification list (Tier 2), and an optional ground_truth ticker used ONLY for validation (never as a reference).
- Tier 1 = disclosed number → regression reference. Tier 2 = exposed but no disclosed number → classified directly, never a regression reference.
- Picking references (approved): High = theme is >= 40% of revenue, Moderate = 5-40%. AI uses my capstone numbers as given. Approved exceptions: Cybersecurity and Clean energy have 1 Moderate reference each; Gold and Healthcare have none (FCX/SCCO, PG/WM, KR dropped); Consumer discretionary Moderate is COST and DG (DIS dropped). Clean energy is solar + renewables (FSLR, SEDG, RUN) + NEE; uranium/nuclear names dropped. Bank Moderates WFC/C/BAC now exceed 40% under the new NII formula; not regrouped (pending decision).
- Price check (engine/price_check.py): each reference must move with its own group beyond SPY and the theme's style controls (and with the ground truth if the theme has one); the control company must NOT. Known fails (version B): MSFT (AI Moderate; accepted), COST and DG (Consumer discretionary Moderate; pending).
- Bank lending / net interest income (formerly "Interest rates"): evidence = NII / (NII + non-interest income), with non-interest income = FMP revenue - interestIncome (FMP has no non-interest-income line; for MTB this gives 79% vs ~71% implied by its earnings call). No ground truth. TLT was dropped because banks didn't move opposite to long bonds beyond the market in this window; validated by group consistency only, like AI.
- Evidence comes from FMP data only (segment revenue share, income-statement ratios, industry). No SEC filings. Never estimated. No disclosed number → Tier 2.
- Data: ~2 years of daily dividend-adjusted closes from FMP (fallback yfinance), cached. Simple daily returns, inner-join dates, no forward fill.
- For each holding and theme, OLS (statsmodels): r_holding = a + b*SPY + b*TLT + style controls + sum of b_j * r_reference_j + b_c * r_control + error. Style controls are daily return spreads (inner-joined dates, no forward fill): VALUE = IWD - IWF, SIZE = RSP - SPY, MOM = MTUM - SPY, LOWVOL = USMV - SPY. Objective skip rule (engine/controls.py), same for every theme: a style control is skipped if the theme's Tier 1 references are more than 15% of any non-SPY leg's holdings (FMP ETF holdings). Every skip and its exact % is recorded in the theme YAML (style_skips). Current result: only AI skips VALUE (refs are 27.1% of IWF). Controls are never in a High/Moderate group and never count in the Bonferroni denominator. Non-US stocks (e.g. ADRs) also get INTL = VXUS - SPY as a control (not in the Bonferroni denominator). The sector control was tested as version C, did worse (results/method_comparison.md) and its code was deleted. This replaces the earlier hand-made 'no VALUE for AI and Cyber' exception.
- Business check (Way 2 only): each theme YAML has allowed_industries (FMP industry names whose core business is the theme). business_linked = the stock's industry is in that list OR it's a named reference / Tier 2 company (engine/business.py).
- For each group: sum the betas, SE from the full covariance matrix, one-sided test of sum > 0.
- A group is eligible if sum > 0.05 AND one-sided p < 0.05 / (number of reference names), counting ALL High and Moderate references in the theme plus the control company (e.g. AI: 7 references + 1 control → 0.05/8). The largest eligible sum wins.
- Limited: nothing eligible AND every group's sum + 1.645*SE < 0.05. Plain text: "doesn't rise with this theme."
- Limited (lower confidence): otherwise, if all group sums < 0.05.
- Otherwise Not determined: "the data can't tell", which is NOT the same as zero.
- A holding that is a reference or on the direct list uses its listed tier, with no regression.
- Cash is kept at its weight and not scored.
- Portfolio fingerprint (Way 1), per theme: "Business-linked exposure %" (the headline: High/Moderate holdings that are also business_linked) and "Price co-movement only %" (High/Moderate but not business_linked, labeled as such). Each holding's row shows its tier and "business linked: yes/no". high_moderate_pct (the two added) is kept for the Way 2 re-check.

## Build phases

Work in phases. STOP at each checkpoint so I can check before continuing. Commit and push after every phase.

0. Setup: folders, venv, .gitignore, .env.example, README, this file.
1. FMP client: engine/fmp.py (stable API, key from .env, every response cached in data/cache/fmp/). Test the endpoints on NVDA and XOM. → Checkpoint 1
2. Themes: AI (my reference set exactly), then Oil, then the others (Bank lending, Gold, Aerospace & defense, Healthcare, Copper+lithium, Clean energy, Consumer discretionary, Cybersecurity) (time-boxed to 30 minutes). → Checkpoint 2: one summary table per theme
3. Price data + regression: engine/data.py get_returns(), engine/regression.py, tests on simulated then real data, price check per theme. → Checkpoint 3
4. Portfolio screen: engine/screen.py run_screen(holdings, themes) → JSON; CLI `python -m engine.screen NVDA:30 XOM:20 CASH:50`. → Checkpoint 4

### Later phases (don't build yet)

5. Way 2 builder (built: engine/builder.py, reads data/exposure_table.parquet). Universe: data/universe.csv from the FMP screener (engine/universe.py): NYSE + NASDAQ stocks only (no ETFs/funds/preferreds/units, one share class per company), market cap >= $2B, avg volume >= 200k, top 500 US + top 150 international by market cap, plus all theme references and Tier 2 names. Prices: python -m engine.fetch_prices (resumable). Table: python -m engine.build_table (engine/exposure.py; batch OLS for full-history stocks, run_screen's own code for the rest; tested to match run_screen within 1e-8). Rules: want = High/Moderate AND business_linked; avoid X = passes unless the regression flags it High or Moderate on X (Not determined, Limited and Limited (lower confidence) all pass), with a safety net: stocks business_linked to X are excluded even if Not determined; each pick's tier on the avoided theme is shown; dont_care = no rule; region all/us/intl; must pass every rule. Ranking, per want theme: (a) the theme's Tier 1 reference companies first, (b) then High before Moderate, (c) then by the t-statistic of the want theme's largest group sum (signed, not floored at 0; Tier 2 names keep their listed tier for Way 1 but rank by t like any other stock) (several want themes: add up each theme's percentile rank in that ordering; no want theme: market cap); top TOP_N = 15; equal weight, 15% cap, cash for any remainder. The t-statistic for reference companies on their own theme comes from a leave-one-out regression (removed from their group, same controls), and for Tier 2 names from an ordinary regression: ranking only, their listed tier never changes; warn if fewer than 6; funnel counts; re-check with Way 1 (run_screen). The two-key ETF rule was dropped.
6. Risk (built: engine/monte_carlo.py, engine/shocks.py, engine/frontier_view.py, engine/risk.py; `python -m engine.risk --from-build`). Monte Carlo: 5-day block bootstrap, 5,000 paths, 252 days, fixed seed (20261115), portfolio and SPY resampled on the same dates, cash earns 0, daily rebalancing; fan chart, P(loss > 10%), 5% VaR/CVaR, P(beat SPY). Theme shocks via betas (e.g. Oil +30%), labeled "estimated sensitivity based on past co-movement": each holding's beta to the theme's equal-weighted reference basket (itself excluded if it's a reference), with the same controls the classification uses (SPY, TLT and the theme's style controls, plus the holding's sector control if a theme turns it on); a shock = the basket moves X% with the controls flat; portfolio move = sum of weight x beta x X. Mean-variance check (engine/mean_variance/, 10y monthly, each stock's own history): fund vs efficient frontier, CML, min-variance and tangency mixes of its own stocks. Check only; never changes weights.
7. Blockchain (deployer wallet via Foundry keystore; chain/publish.py posts engine results to the oracle):
   - ExposureOracle: the owner or an approved publisher posts ticker / theme / tier / price / baselineHash / statsHash / timestamp. Prices use 8 decimals. Publishers: the owner calls setPublisher(wallet, true/false) on the oracle and the exchange (listing stocks); Deploy.s.sol approves PUBLISHERS=0x..,0x.. at deploy time. Both contracts have transferOwnership.
   - MockUSDC: ERC-20 test dollars, 6 decimals, public faucet(). MockStock: one ERC-20 per ticker, 18 decimals. Only MockExchange can mint or burn either.
   - MockExchange: buy(stock, usdcAmount) takes USDC and mints stock at the oracle price; sell(stock, qty) burns stock and mints USDC at the oracle price. Reverts if a price is missing or older than 7 days.
   - ThemeFund (ERC-20 shares): deposit → buy the basket through the exchange at target weights → mint shares at NAV (first deposit: 1 share = $1). redeem → sell a pro-rata slice of each holding → pay USDC → burn shares. NAV = sum(qty × oracle price) + cash. addHolding / rebalance check the mandate against ExposureOracle BEFORE trading and revert with a clear reason, e.g. "Mandate: Oil exposure too high".
   - ThemeFundFactory: creates a ThemeFund with name, symbol, basket, rules.
   - Tests: deposit then redeem with no price change returns about the same USDC; a price rise increases NAV; adding XOM to an Avoid-Oil fund reverts; a stale price reverts.
8. Streamlit dashboard (built: app.py, engine/dashboard.py, engine/assistant.py, chain/app_actions.py; `streamlit run app.py`). Two ways in: "Build my ETF" (Want / Don't care / Avoid per theme + region → funnel → basket → Way 1 re-check) and "Check my portfolio" (any stocks + weights → % exposed per theme, tiers, sentences). Both: heatmap + audit trail, risk (Monte Carlo, shock slider, mean-variance), and the "Ask about your fund" chat (Claude Haiku 5.5 only, low effort, answers only from the fund's facts incl. company names/industries; ANTHROPIC_API_KEY in .env). Launch on Monad (built funds only): unlock the Foundry keystore with a password typed in the app (kept in memory only) → Publish (tiers + prices + XOM) → Launch (explorer link on Monad) → Deposit → "Try adding XOM" rehearsed against the live contract, rejection in red. Without MONAD_RPC_URL / FACTORY_ADDRESS / keystore, the tab lists the missing steps and previews the mandate check off-chain. chain/publish.py sends 20% gas headroom + 3,000 gas per timestamped item (estimates were short by 2,800 per re-posted price).

## Notes for TeagSloan (contracts/ and chain/)

- `results/build_latest.json` (Way 2 output) changed: it now has `funnel` (list of {step, left}), `region`, `ranked_by` and
  `survivors`; there is no `points` field any more; each holding has `name`, `industry`, `want_tiers`, `avoid_tiers`
  ({theme name: tier on the avoided theme}), `strength` ({theme name: strength score}) `t_stat`, `reference` (Tier 1 reference on that want theme) and `rank_score`. `tiers` (want + avoid tiers) and `labels` (avoid notes: lower confidence / the data can't tell) are kept for app.py and engine/assistant.py. `ticker` and
  `weight_pct` are unchanged, and CASH is still a holding when there's a remainder.
- `engine.builder.prescreen()` still returns {ticker: {theme: result}} in run_screen's shape, now read from
  `data/exposure_table.parquet` (666 stocks) instead of the old 106-name cache.
- "avoid" now allows Not determined (see the Builder rules above), so a fund's avoid mandate should only reject High/Moderate.
- Way 1 fingerprints (`results/screen_latest.json`) gained `business_linked_pct` and `price_only_pct` per theme and a
  `business_linked` flag per holding result; `high_moderate_pct` is unchanged.
- The Defense theme's display name is now "Aerospace & defense" (the key is still `defense`).

## Rules

- Never print or commit API keys or private keys. Never read .env contents into the chat.
- Small testable steps. Plain-English comments.

## Network

- Monad testnet, chain ID `10143`
- RPC: `https://testnet-rpc.monad.xyz` (set as `MONAD_RPC_URL` in `.env`)
- Foundry endpoint name: `monad` (e.g. `forge script ... --rpc-url monad`), or `FOUNDRY_PROFILE=monad`
- Live deployment (Nov 15 2026): factory `0x62cd00e1e5123d511201878679d3aCB62Dd62E5a`, oracle `0x55AbD9CBEc8beB920EB4C8aA408088522e8A4df0`, exchange `0x46baB6E7ba190930A82367e1C0822da541FD0577`. Owner `0xE0175dd6faBb0aB0479633aE73fD6AcDBAEfd03f`; three team wallets are approved publishers (see README). Don't redeploy unless asked.

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
