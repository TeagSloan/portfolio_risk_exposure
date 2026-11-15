# Theme Funds

Pick the themes you want exposure to (e.g. *Want AI*, *Avoid Oil*). Theme Funds builds a stock portfolio that matches, runs a Monte Carlo risk simulation on it, and launches it as an on-chain fund token on Monad testnet. The fund's mandate rules are enforced by the contract, so any change that breaks them is rejected.

Every result comes with a plain-English sentence, because users aren't expected to be finance experts.

## Credits

Everything in this repository was built at **Monad Blitz Oregon (Nov 15, 2026)**. The exposure methodology (how stocks are classified per theme) comes from my prior capstone research.

## How it works

1. **Themes.** Each theme (AI, Oil, Bank lending, …) has reference companies with a disclosed exposure number, such as AI's share of revenue.
2. **Exposure engine.** For each stock, a regression measures how much its daily returns move with each reference group, after controlling for the overall market (SPY), bonds (TLT) and the value-vs-growth swing (IWD minus IWF). The stock gets a tier: High / Moderate / Limited / Limited (lower confidence) / Not determined.
   - *Why AI and Cybersecurity skip the value-vs-growth control:* the growth index is mostly these themes' own stocks, so controlling for it removes the very signal being measured. With it, oil producers wrongly came out "AI High"; without it, they don't.
3. **Portfolio.** Your choices (want / avoid per theme) become a weighted basket, which is screened again to confirm it matches.
4. **Risk.** A Monte Carlo simulation shows the range of outcomes and theme shocks (e.g. oil +30%).
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

## Putting it on Monad testnet (Phase 7)

The contracts live in `contracts/src/` and the Python that talks to them in `chain/`.

```bash
# 1. Store the deployer wallet in a Foundry keystore (asks for the key and a password; never paste it elsewhere)
cast wallet import deployer --interactive

# 2. Deploy the oracle, exchange and factory, then copy the printed FACTORY_ADDRESS into .env
cd contracts
forge script script/Deploy.s.sol --rpc-url monad --account deployer --broadcast
cd ..

# 3. Publish the latest built fund's tiers and prices (plus XOM for the rejection demo)
python -m chain.publish --extra XOM --dry-run     # shows what would be posted, sends nothing
python -m chain.publish --extra XOM

# Weekend demo: replay the last 20 trading days of real prices, one every 3 seconds
python -m chain.publish --extra XOM --replay 20 --interval 3
```

On testnet the stocks are simulated tokens priced from our own data feed. In production this would plug into tokenized stocks.
