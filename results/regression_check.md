# Regression check

**Verdict.** The math is exactly right, and on clean, simulated data the method finds the right answer almost every time (590 of 600 simulated stocks) while flagging pure noise under 1% of the time. On real stocks it is clearly less reliable. When the references are replaced with real companies from unrelated sectors, it still flags 17.5% of holdings, well above the 5% target. In the sanity table, 8 of the 18 High/Moderate calls look wrong (KO in three themes, AAPL as Healthcare High, SMH as Gold and Clean-energy High, COP as Defense High). The cause is broad co-movement: defensive stocks move together, and so do miners and chips, so a stock can "move with" a reference group without having any real business link to the theme. **"Avoid" results are trustworthy, because Not determined is excluded. "Want" results outside the listed reference companies need a human sanity check.** Method and thresholds were not changed.

Data: 499 trading days (Nov 18 2024 – Nov 13 2026), 122 series. CRWV is left out of these tests because of its short price history. Run `python -m engine.regression_check`; raw numbers are in `results/regression_check_raw.json`.

## Scorecard

| # | Test | Result | Verdict |
|---|---|---|---|
| 1 | Math check: SMH/AI, XOM/Oil, JNJ/Healthcare redone with plain statsmodels plus hand covariance algebra | Tiers identical; largest difference in sum / SE / p-value: 3e-17 | ✅ Pass |
| 2a | Known answers, AI: High-group / Moderate-group / market-only simulated stocks (100 each) | 100% / 100% / 100% correct (market-only: 61% reach Limited, the rest are cautious lower-confidence or Not determined) | ✅ Pass |
| 2b | Known answers, Oil (same design) | 100% / 91% / 99% correct (market-only: 38% reach Limited) | ✅ Pass (Moderate is slightly weaker) |
| 3a | False positives, pure-noise references (1,000 holdings) | 0.9% flagged High/Moderate | ✅ Pass (≤ 5%) |
| 3b | False positives, random real tickers as references; holdings only from sectors none of them are in (999 holdings) | **17.5% flagged** | ⚠️ Concern (> 5%) |
| 4 | Leave-one-out: each Tier 1 reference classified with itself removed (59 references) | 94.9% land High/Moderate in their own theme; 71.2% land in their exact listed group | ✅ Pass / ⚠️ High vs Moderate is blurry |
| 5 | Ground truth: Spearman rank correlation, method score vs direct beta on the theme ETF (107 names each) | Gold/GLD 0.94, Discretionary/XLY 0.84, Healthcare/XLV 0.73, Cyber/CIBR 0.70, Clean/ICLN 0.65, Metals/COPX 0.64, Defense/ITA 0.58, Oil/USO 0.48. All p < 1e-6; median 0.68 | ✅ Pass (Oil weakest) |
| 6 | Sanity table (below) | 8 of 18 High/Moderate calls look wrong | ⚠️ Concern |

Simulation design for test 2: holding = SPY + (true sum) × average of the group's real returns + 1.5% daily noise. The theme's real reference returns were used, so overlap between groups is realistic. "Correct" for market-only means not High/Moderate.

## 6. Sanity table

L = listed tier (the stock is a reference or on the direct list, so there's no regression). ⚠️ = looks wrong.

| | AI | Bank lending | Clean energy | Discretionary | Cyber | Defense | Gold | Healthcare | Metals | Oil |
|---|---|---|---|---|---|---|---|---|---|---|
| SMH | High | Lim-low | **High ⚠️** | Lim | Mod | Lim | **High ⚠️** | Lim | ND | ND |
| NVDA | High (L) | ND | ND | Lim | Lim-low | ND | Lim-low | Lim | ND | ND |
| XOM | Lim-low | ND | ND | ND | ND | ND | Lim | ND | Lim-low | Mod |
| COP | Lim-low | ND | ND | Lim-low | Lim-low | **High ⚠️** | Lim | Lim-low | Lim-low | High (L) |
| JNJ | Lim | Lim-low | **Mod ⚠️** | ND | Lim | ND | Lim-low | High | Lim-low | ND |
| LMT | Lim | Lim-low | ND | ND | ND | High (L) | Lim-low | ND | ND | ND |
| NEM | ND | ND | ND | Lim-low | Lim-low | ND | High (L) | Lim-low | Mod | ND |
| KO | Lim | Lim | **Mod ⚠️** | **Mod ⚠️** | Lim | Lim-low | Lim | **Mod ⚠️** | Lim-low | ND |
| AAPL | Lim | ND | Lim | Mod | Lim-low | Lim-low | Lim | **High ⚠️** | ND | ND |

Reasonable calls: SMH AI High (and Cyber Moderate is defensible), XOM Oil Moderate, JNJ Healthcare High, NEM Metals Moderate (miners), AAPL Discretionary Moderate. NVDA, XOM and LMT have no false flags at all.

## 3 numbers for the pitch

1. **98%**: on 600 simulated stocks with known exposure, the engine gave the right answer 590 times.
2. **Under 1%**: false alarms on pure noise, well inside the 5% budget.
3. **95%**: hide a reference company from the model, and it still picks that company out as exposed to its own theme 95% of the time.

(If you quote a ground-truth number: the method's ranking agrees with the theme ETF at a median Spearman of 0.68, and 0.94 for gold. Don't claim "under 1% false positives on real stocks": against real stocks from unrelated sectors it's 17.5%.)

## Problems, most serious first

1. **Too many false positives on real stocks (17.5% vs a 5% target).** These show up as wrong "want" picks such as KO in Healthcare, Discretionary and Clean energy, AAPL in Healthcare, SMH in Gold, and COP in Defense. The cause is sector or style co-movement that SPY/TLT/VALUE don't remove. "Avoid" is protected because Not determined is excluded.
2. **High vs Moderate isn't reliably separated.** In the leave-one-out test, 10 of 22 Moderate references come out High (TSM, VST, NEE, COST, DIS, DG, RTX, RIO, CVX, SHEL). The tier reflects which group a stock moves with most, not how big its exposure is, so the builder's 2-vs-1 weighting rests on a blurry line.
3. **Bank evidence % is probably understated** (from the evidence skim). MTB's call implies 71% net interest income versus FMP's 56%, because FMP uses a different revenue definition. The ranking of banks is likely fine, but the absolute numbers are low.
4. **Oil has the weakest ground-truth agreement (Spearman 0.48).** Oil stocks move a lot with each other and with the value swing, and only partly with crude itself (USO).
5. **The method is cautious about saying "no exposure."** Only 38–61% of simulated market-only stocks reach a clean Limited; the rest are lower-confidence or Not determined. That's safe, but it keeps "avoid" baskets small.
6. **Minor:** CRWV is left out of these tests (short price history), and the sanity table shows listed tiers for reference companies rather than regression results.
