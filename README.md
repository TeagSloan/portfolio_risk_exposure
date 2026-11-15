# Theme Funds

Pick the themes you want exposure to (e.g. *Want AI*, *Avoid Oil*), get a stock basket that matches, and launch it as an on-chain fund token on Monad testnet. The fund's mandate rules are enforced by the contract, so any basket change that breaks them is rejected.

## What was built where

| Part | Origin |
|---|---|
| Exposure engine (`engine/`, `themes/`): regression method that classifies each stock per theme as High / Moderate / Limited / Limited (lower confidence) / Inverse / Not determined | **Prior work** |
| Smart contracts (`contracts/`): ExposureOracle, MockStock, ThemeFund, ThemeFundFactory | **Built at Monad Blitz Oregon (Nov 15, 2026)** |
| On-chain oracle feed and fund tokens | **Built at Monad Blitz Oregon (Nov 15, 2026)** |
| Integration (`chain/`, web3.py) and Streamlit dashboard | **Built at Monad Blitz Oregon (Nov 15, 2026)** |

## How it fits together

1. **Engine** scores stocks against each theme and assigns an exposure tier.
2. **ExposureOracle** stores those results on-chain (ticker, theme, tier, price, and hashes of the inputs), posted by the owner.
3. **ThemeFundFactory** creates a **ThemeFund**: an ERC-20 fund token that holds a basket of **MockStock** test tokens. Deposits mint fund tokens at NAV, redemptions burn them.
4. Each fund has mandate rules per theme. A basket change that breaks a rule reverts with a clear reason.

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
