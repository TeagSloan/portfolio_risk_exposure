# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## About me
I am a finance student interested in conducting quantitative research on financial markets.

I want explanations of code and structures that someone who is non-technical could understand.

I prefer concise, direct communication without unnecessary jargon.

Every output should feel like advice from an experienced practitioner rather than a consultant or academic.

## Project overview: Theme Funds

Theme Funds: users pick theme exposures (e.g. Want AI, Avoid Oil). A Python regression engine (engine/, prior work, don't change its method) classifies stocks per theme as High / Moderate / Limited / Limited (lower confidence) / Inverse / Not determined. We build a basket and launch it as an on-chain fund token on Monad testnet whose rules can't be broken.

Contracts: ExposureOracle (owner posts ticker, theme, tier, price, baselineHash, statsHash, timestamp), MockStock (ERC-20 test token per ticker), ThemeFund (ERC-20 fund token: deposit mints at NAV, redeem burns, holds a basket, mandate rules per theme, any basket change that breaks a rule reverts with a clear reason), ThemeFundFactory (creates a ThemeFund with name, symbol, basket, rules).

Python in chain/ uses web3.py. Dashboard is Streamlit app.py with a server-side demo wallet from .env.

Rules: never print or commit keys. Small testable steps. Plain-English comments.

## Network

- Monad testnet, chain ID `10143`
- RPC: `https://testnet-rpc.monad.xyz` (set as `MONAD_RPC_URL` in `.env`)
- Foundry endpoint name: `monad` (e.g. `forge script ... --rpc-url monad`), or `FOUNDRY_PROFILE=monad`

## Workflow rules

**Always present a concise written plan and wait for my approval before beginning a multi-step or complex task.**

For coding tasks, follow the steps in [workflows/coding_workflow.md](workflows/coding_workflow.md), with one exception for this project: build directly in `engine/`, `contracts/`, `chain/` and `app.py` instead of `drafts/` and `outputs/`.

## Structure

```
theme-funds/
├── CLAUDE.md          # guidance for Claude (this file)
├── README.md          # what the project is, what was built where, how to run it
├── workflows/         # workflow instructions and process documents
├── engine/            # exposure regression engine (prior work, don't change the method)
├── themes/            # theme definitions (YAML) used by the engine
├── contracts/         # Foundry project: Solidity contracts, tests, deploy scripts
├── chain/             # Python (web3.py) code that talks to the contracts
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
