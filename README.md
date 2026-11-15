# Theme Funds

**Everything in this repository was built at Monad Blitz Oregon (University of Oregon,
Nov 15, 2026). The methodology comes from my prior capstone research.**

Pick the themes you want exposure to, and the ones you want to avoid (e.g. *Want AI, Avoid
Oil*). Theme Funds:

1. **Classifies stocks** by how closely their prices move with reference companies that have
   disclosed exposure to each theme (e.g. NVIDIA's AI share of revenue).
2. **Builds a portfolio** from your choices.
3. **Runs a Monte Carlo risk simulation** to show the range of outcomes.
4. **Launches it as a fund token on Monad testnet** whose rules can't be broken. A fund that
   promised "no oil" cannot buy an oil stock.

Every result comes with a plain-English sentence, because users aren't finance experts.

## Setup

Needs Python 3.10+ and, for the contracts, [Foundry](https://getfoundry.sh).

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Then fill in `.env` with your own keys. It is git-ignored; never commit it.

## Run the tests

```bash
python -m pytest
```

## Layout

| Folder | What's in it |
|---|---|
| `engine/` | The Python engine: FMP data, theme regression, portfolio screen, builder, risk |
| `engine/mean_variance/` | Efficient frontier and capital market line for a portfolio |
| `themes/` | One YAML file per theme: reference companies, evidence, control |
| `chain/` | Python scripts that publish results to Monad |
| `contracts/` | Solidity contracts (Foundry), network `monad`, chain ID 10143 |
| `tests/` | Automated tests |
| `data/cache/` | Downloaded data, re-created on demand (not committed) |
