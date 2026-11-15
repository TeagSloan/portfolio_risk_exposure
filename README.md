# Theme Funds

Pick the themes you want exposure to (e.g. *Want AI*, *Avoid Oil*). Theme Funds builds a stock portfolio that matches, runs a Monte Carlo risk simulation on it, and launches it as an on-chain fund token on Monad testnet. The fund's mandate rules are enforced by the contract, so any change that breaks them is rejected.

Every result comes with a plain-English sentence, because users aren't expected to be finance experts.

## Credits

Everything in this repository was built at **Monad Blitz Oregon (Nov 15, 2026)**. The exposure methodology (how stocks are classified per theme) comes from my prior capstone research.

## How it works

1. **Themes.** Each theme (AI, Oil, Bank lending, …) has reference companies with a disclosed exposure number, such as AI's share of revenue.
2. **Exposure engine.** For each stock, a regression measures how much its daily returns move with each reference group, after controlling for the overall market (SPY), bonds (TLT) and four style swings: value vs growth (IWD − IWF), small vs mega-cap (RSP − SPY), momentum (MTUM − SPY) and low-volatility (USMV − SPY). The stock gets a tier: High / Moderate / Limited / Limited (lower confidence) / Not determined.
   - *Objective skip rule:* a style control is skipped for a theme if that theme's reference companies make up more than 15% of the control ETF's holdings, because then the control would remove the very signal being measured. Today this skips value-vs-growth for AI only (AI references are 27% of the growth ETF). Every skip is recorded with its exact % in the theme file.
3. **Portfolio.** Your choices (want / avoid per theme) become an equal-weight basket (15% cap), which is screened again to confirm it matches. For themes with an ETF, "want" picks are confirmed against the theme ETF; validation numbers come from the unfiltered method.
4. **Risk.** A Monte Carlo simulation shows the range of outcomes and theme shocks (e.g. oil +30%), plus a mean-variance check of the fund against the best mixes of its own stocks. Run `python -m engine.risk --from-build`.
5. **On-chain fund.** The basket launches as an ERC-20 fund token on Monad testnet. Deposits mint at NAV, redemptions burn, and the mandate rules can't be broken.

## Setup

```bash
# Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Settings: copy the template, then fill in your own values (never commit .env)
cp .env.example .env

# Contracts (needs Foundry: https://getfoundry.sh)
cd contracts
forge build
forge test
```

Network: Monad testnet, chain ID 10143, RPC `https://testnet-rpc.monad.xyz`.
