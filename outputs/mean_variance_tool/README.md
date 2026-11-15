# Mean-variance portfolio tool

Takes a stock portfolio (tickers and weights) and shows where it sits on the
classic risk/return chart:

- **Efficient frontier**: the best expected return available at each level of risk,
  using only the stocks in the portfolio. Long-only (no short selling).
- **Capital market line**: the line from the risk-free rate through the tangency
  portfolio. Points on it are mixes of the tangency portfolio with Treasuries.
- **Minimum-variance portfolio**: the lowest-risk mix of the stocks.
- **Tangency portfolio**: the mix with the highest Sharpe ratio (return per unit of risk).
- **Your portfolio**, plus each stock on its own for context.

Below the chart, a table gives expected return, risk (volatility) and Sharpe ratio
for your portfolio, the minimum-variance portfolio and the tangency portfolio.

## How the numbers are built

| Input | Source / method |
|---|---|
| Prices | FMP daily closes adjusted for dividends and splits, so returns include dividends |
| Returns | Month-end to month-end, last 10 years (120 months). The current, unfinished month is left out |
| Expected return | Average monthly return x 12 |
| Risk | Covariance of monthly returns x 12; volatility is its square root |
| Risk-free rate | Latest 10-year Treasury yield from FMP, pulled each run |

**Stocks with less than 10 years of history:** pick a window mode.

- `shared` (default): every stock is measured over the same period, the stretch
  they all have data for. One young stock shortens the window for all of them.
- `max_available`: each stock's expected return and volatility use its own history
  (up to 10 years). How stocks move together (correlation) uses the shared period.

The stocks need at least 24 months of shared history either way.

**Treat the chart with some caution.** Expected returns here are historical averages,
and those are noisy. The frontier and tangency weights can shift a lot when the data
window moves. The chart shows how the portfolio *did*; it is not a forecast.

## Install

Needs Python 3.10 or newer. From this folder:

```bash
pip install -r requirements.txt
```

Set your FMP API key. Never put the key in the code or commit it to git:

```bash
export FMP_API_KEY="your_key_here"
```

## Run from the command line

```bash
python analyze_portfolio.py AAPL=0.4 MSFT=0.35 XOM=0.25 --output chart.html
```

For a portfolio with a younger stock (ARM listed in 2023), using each stock's own history:

```bash
python analyze_portfolio.py AAPL=0.5 ARM=0.5 --window max_available --output chart_arm.html
```

This prints the summary table and saves an interactive chart. Open the `.html` file in
a browser and hover over any point to see its weights.

Rules for the portfolio:

- at least two stocks
- weights add up to 100%; anything between 99% and 101% is rescaled to exactly 100%
- no negative weights (short positions are not supported yet)

If something is wrong (bad ticker, weights off, FMP unreachable), the tool prints a
one-line `Error: ...` message and exits with code 1.

## Use from the main app

```python
from analyze_portfolio import analyze_portfolio

result = analyze_portfolio({"AAPL": 0.4, "MSFT": 0.35, "XOM": 0.25},
                           window_mode="shared")

result.figure          # the plotly chart: show it, or result.figure.to_html()
result.summary         # return, volatility, sharpe and weights for each marked portfolio
result.frontier        # points along the efficient frontier, with weights
result.risk_free_rate  # e.g. 0.0515 for 5.15%
result.windows         # the data period used for each stock
```

All errors the tool raises on purpose inherit from `errors.PortfolioToolError` and carry
a message that can be shown to the user as-is.

## Files

| File | What it does |
|---|---|
| `analyze_portfolio.py` | Entry point: checks input, runs the steps, command line |
| `data_fetcher.py` | Pulls prices and the 10-year yield from FMP |
| `return_calculator.py` | Prices to monthly returns, expected returns and risk; window modes |
| `optimizer.py` | Minimum-variance portfolio, efficient frontier, tangency portfolio |
| `chart_builder.py` | Draws the chart and table |
| `errors.py` | Error types with plain-language messages |
| `tests/` | Automated tests; they use made-up prices and need no internet or key |

## Run the tests and the style checker

```bash
python -m pytest --cov=. --cov-report=term-missing
```

```bash
ruff check .
```
