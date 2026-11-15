# Theme Funds

Pick the themes you want exposure to (e.g. *Want AI*, *Avoid Oil*). Theme Funds builds a stock portfolio that matches, runs a Monte Carlo risk simulation on it, and launches it as an on-chain fund token on Monad testnet. The fund's mandate rules are enforced by the contract, so any change that breaks them is rejected.

Every result comes with a plain-English sentence, because users aren't expected to be finance experts.

## Credits

Everything in this repository was built at **Monad Blitz Oregon (Nov 15, 2026)**. The exposure methodology (how stocks are classified per theme) comes from my prior capstone research.

## How it works

1. **Themes.** Each theme (AI, Oil, Bank lending, …) has reference companies with a disclosed exposure number, such as AI's share of revenue.
2. **Exposure engine.** For each stock, a regression measures how much its daily returns move with each reference group, after controlling for the overall market (SPY), bonds (TLT) and four style swings: value vs growth (IWD − IWF), small vs mega-cap (RSP − SPY), momentum (MTUM − SPY) and low-volatility (USMV − SPY). The stock gets a tier: High / Moderate / Limited / Limited (lower confidence) / Not determined.
   - *Objective skip rule:* a style control is skipped for a theme if that theme's reference companies make up more than 15% of the control ETF's holdings, because then the control would remove the very signal being measured. Today this skips value-vs-growth for AI only (AI references are 27% of the growth ETF). Every skip is recorded with its exact % in the theme file.
3. **Portfolio.** Two ways in. *Check my portfolio* (`python -m engine.screen NVDA:30 XOM:20 CASH:50`) scores any NYSE/NASDAQ stocks on every theme. *Build my ETF* (`python -m engine.builder --want ai --avoid oil --region all`) picks individual stocks from a pre-scored universe of ~666 NYSE + NASDAQ stocks (data/exposure_table.parquet): "want" needs a High/Moderate result AND a real business link (the stock's industry), "avoid" needs Limited. Equal weight, 15% cap, a funnel of how many stocks pass each rule, then a re-check with *Check my portfolio*. Rebuild the data with `python -m engine.universe`, `python -m engine.fetch_prices`, `python -m engine.build_table`.
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

# Dashboard (opens in your browser). The "Ask about your fund" chat needs ANTHROPIC_API_KEY in .env
streamlit run app.py

# Contracts (needs Foundry: https://getfoundry.sh)
cd contracts
forge build
forge test
```

Network: Monad testnet, chain ID 10143, RPC `https://testnet-rpc.monad.xyz`.

## Putting it on Monad testnet (Phase 7)

The contracts live in `contracts/src/` and the Python that talks to them in `chain/`.

```bash
# 1. Store the deployer wallet in a Foundry keystore (asks for the key and a password; never paste it elsewhere)
cast wallet import deployer --interactive

# 2. Deploy the oracle, exchange and factory, then copy the printed FACTORY_ADDRESS into .env
cd contracts
forge script script/Deploy.s.sol --rpc-url monad --account deployer --broadcast
# Optional: also approve team wallets to publish (public addresses, comma-separated):
#   PUBLISHERS=0xabc...,0xdef... forge script script/Deploy.s.sol --rpc-url monad --account deployer --broadcast
# Hand both contracts to another owner later:
#   cast send <ORACLE_ADDRESS> "transferOwnership(address)" <NEW_OWNER> --rpc-url monad --account deployer
#   cast send <EXCHANGE_ADDRESS> "transferOwnership(address)" <NEW_OWNER> --rpc-url monad --account deployer
cd ..

# 3. Publish the latest built fund's tiers and prices (plus XOM for the rejection demo)
python -m chain.publish --extra XOM --dry-run     # shows what would be posted, sends nothing
python -m chain.publish --extra XOM

# 4. Launch the built fund as its own token, deposit test dollars, and show the mandate rejecting XOM
python -m chain.launch --dry-run                  # shows the fund, basket and mandate; sends nothing
python -m chain.launch --deposit 1000 --try-add XOM

# Weekend demo: replay the last 20 trading days of real prices, one every 3 seconds
python -m chain.publish --extra XOM --replay 20 --interval 3
```

The launched fund's address and explorer link are saved to `results/fund_latest.json`.

On testnet the stocks are simulated tokens priced from our own data feed. In production this would plug into tokenized stocks.
