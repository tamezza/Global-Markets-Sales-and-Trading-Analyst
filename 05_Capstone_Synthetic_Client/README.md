# Part 5 — Capstone: A Synthetic Client, End to End

**Status:** ✅ Done

**Final report:** [Capstone_Report.pdf](Capstone_Report.pdf), a 10-page client review combining the four stages, with recommendations.

## Why this capstone

Parts 1–4 followed Forage's scenarios and data. This capstone applies the same four skills to a client and market I built myself, so that every step can be checked and reproduced. It also goes further than the simulation where the simulation stopped short:

- a full year of data instead of a single week,
- a reconciliation engine that actually runs, instead of a description of one,
- known ground truth, so every analysis can be scored against what really happened.

## The client: Kestrel Bay Capital (fictional)

| | |
|---|---|
| Type | Mid-sized multi-family office, $250m AUM |
| Allocation | Technology 35 · Healthcare 15 · Financials 10 · Renewable Energy 15 · Real Estate 10 · Cash 15 |
| Risk tolerance | Moderate-high, 5–7 year horizon |
| Objectives | Return of at least 6% a year · maximum drawdown under 10% · at least 15% in sustainable assets · faster, reliable trade reporting |
| Constraints | No sector above 40% · cash between 5% and 20% · no leverage |

## The synthetic data (`src/generate_data.py`, fixed seed)

| File | Content |
|------|---------|
| `data/client_profile.json` | The client above |
| `data/market_weekly.csv` | 52 weeks: 6 sector returns from a factor model (market, rates, events), VIX, policy rate (3.00% → 3.75% → 3.25%), sentiment, 9 events |
| `data/trades_oms.csv` | 3,000 trades from the order management system |
| `data/trades_custodian.csv` | The same trades as booked by the custodian, with planted breaks: price, quantity, date, missing and duplicate trades, plus ID-format differences that are *not* real breaks |
| `data/breaks_truth.csv` | Ground truth for every planted break, used to score the reconciliation engine |
| `outputs/exceptions_report.csv` | The engine's exception report: break type, priority, OMS vs custodian values, suggested action |

## Roadmap

| Stage | Skill from | Notebook | Status |
|-------|-----------|----------|--------|
| 1. Market insight | Part 1 | [01_market_insight.ipynb](01_market_insight.ipynb) | ✅ Done |
| 2. Live market dynamics: replay the year with rebalancing triggers; rate and drawdown stress tests | Part 2 | [02_live_dynamics.ipynb](02_live_dynamics.ipynb) | ✅ Done |
| 3. Product recommendation: an allocation that meets every client constraint, with products mapped to objectives | Part 3 | [03_product_recommendation.ipynb](03_product_recommendation.ipynb) | ✅ Done |
| 4. Process automation: a working reconciliation engine, scored against the ground truth | Part 4 | [04_reconciliation_engine.ipynb](04_reconciliation_engine.ipynb) | ✅ Done |
| Final report combining all four stages | — | [Capstone_Report.pdf](Capstone_Report.pdf) | ✅ Done |

## Stage 1 findings

- **The year went well:** the portfolio returned **+16.3%** against a 6% target, and its maximum drawdown was only −2.9% against a 10% limit. A calm year does not test the drawdown limit, so Stage 2 stress-tests it.
- **Technology concentration:** Technology is 35% of the capital but **51% of the risk**.
- **Best risk-adjusted sector:** Renewable Energy had the best return per unit of volatility (1.65). This supports the client's sustainability objective rather than costing it return.
- **A gap in the portfolio:** the client holds no Energy, which rose 25% and tends to move *with* interest rates, so it could hedge the portfolio's rate exposure.
- **A lesson about the data:** with only 5 rate moves in the year, the measured rate sensitivities are unreliable. The generator builds Technology to fall when rates rise, yet the estimate came out near zero. One year of data cannot measure this, so Stage 2 uses explicit rate scenarios instead.

## Stage 2 findings

Three ways of managing the same allocation were compared: buy and hold, monthly rebalancing, and monthly rebalancing with *risk-off triggers*. In risk-off mode, when VIX goes above 20 or the portfolio falls 5% below its peak, the portfolio moves from Technology to Healthcare and cash, within the client's limits.

- **The actual year cannot tell them apart:** all three returned about +16%. The triggers fired for 8 weeks, cost 0.3 points and lowered the drawdown slightly (−2.7% vs −3.0%).
- **5,000 simulated years show the trade-off:**

  | | Buy and hold | Monthly rebalance | With triggers |
  |---|---|---|---|
  | Chance of a drawdown worse than 10% | 6.2% | 5.8% | **4.2%** |
  | Median return | +13.3% | +13.3% | +12.2% |
  | Chance of missing the 6% target | 21.2% | 20.8% | 23.6% |

  The triggers cut the chance of breaching the drawdown limit by about a third, but give up about 1 point of median return and miss the 6% target slightly more often. Whether that is worth it is the client's choice. The simulation puts a number on it.
- **Stage 1 underestimated the rate risk, and even got its direction wrong:** with the generator's true sensitivities, a +100 bp rate shock costs the portfolio **−1.9%**. The Stage 1 estimates, based on 5 rate moves, predicted **+0.3%**. One year of data was not enough to measure rate risk, which supports Stage 1's caution.

## Stage 3 findings

Every allocation in 5% steps that respects the client's rules was checked: **40,840** of them (each sector at most 40%, cash 5–20%, Renewable Energy at least 15%, no leverage). Each building block is mapped to a product: technology ETF, healthcare ETF, financials ETF, energy ETF, clean-energy ETF, REIT fund, and money-market fund for cash.

- **Today's allocation is already close to the best the rules allow.** The candidates that beat it do so by only about 0.1 point of return.
- **Option A** came from the rule I fixed in advance: highest median return without a higher chance of breaching the drawdown limit. It is Tech 30 / Healthcare 40 / Financials 10 / Renewable 15 / Cash 5. It pushes Healthcare to the 40% cap and cash to the 5% minimum.
- **Option B** came from a safety-first rule that I added *after* seeing A's result, and I say so in the notebook. It is Tech 35 / Healthcare 15 / Financials 15 / Energy 5 / Renewable 15 / Cash 15.
- **Both were validated on 5,000 new simulated years** the choice never saw. B beat A by 2.6 standard errors and needs 10 points of trading instead of 25, so **B is recommended**. The trades: **Financials +5, Energy +5, Real Estate −10**.
- **What B delivers:** return +0.11 points a year over today (statistically real, but small). A +100 bp rate rise now costs −1.36% instead of −1.90%, because the client swaps the most rate-sensitive sector (Real Estate) for two that gain when rates rise (Financials and Energy). This is the Stage 1 insight about Energy, now confirmed.
- **What B does not fix:** Technology still carries about 52% of the risk. Option A cuts that to 43%, but only by concentrating in Healthcare and running cash at the minimum. The bigger risk lever remains the Stage 2 triggers, which take the breach chance from 5.6% to 4.1%.
- **Lesson:** a systematic search can show that the right answer is "small changes". Saying so, and showing that the gain is real but modest, is more credible than presenting a dramatic reallocation.

The shared simulation code (simulated years, management approaches, metrics) is in `src/portfolio_simulation.py`, used by Stages 2 and 3.

## Stage 4 findings

Part 4 *described* a reconciliation engine. Here it is built ([src/reconciliation.py](src/reconciliation.py)) and scored against the ground truth, which the engine never sees. The test: 3,000 trades, 270 planted breaks, and 30 decoys where the same trade ID is written differently.

| | Naive spreadsheet lookup | Rule-based engine |
|---|---|---|
| Trades flagged | 1,372 | 270 |
| Real breaks found | 260 of 270 | **270 of 270** |
| False alarms | 1,112 | **0** |
| Correct break type | 81% | **100%** |
| Precision (share of flags that are real) | 19% | **100%** |
| Analyst hours a year (10 min per flag; manual today: 20 min per trade = 1,000 h) | 229 h | **45 h (−96%)** |

- **The naive lookup drowns real breaks in noise.** 1,082 of its false alarms are price rounding in the third decimal. It also flags the 30 decoys as missing trades and never notices duplicate bookings.
- **The engine applies four simple rules:** standardise trade IDs, count bookings per trade, allow a price tolerance, and give each trade a single break type by severity. Each break comes with a priority based on the money at stake and a suggested action ([outputs/exceptions_report.csv](outputs/exceptions_report.csv)).
- **The tolerance setting is not fragile:** the engine makes no errors for any tolerance from 2 to 75 bp. The 10 bp setting sits well inside that range.
- **Why 100% is not the headline:** the planted breaks are cleanly separated from the noise. Real reconciliations also involve partial fills, corporate actions, FX and split accounts. The meaningful results are the comparison with the naive lookup, the safe tolerance range, and the analyst time saved.

## Reproduce

```bash
pip install -r ../requirements.txt
python src/generate_data.py            # optional: the data are already committed
jupyter notebook 01_market_insight.ipynb   # then 02, 03 and 04_reconciliation_engine.ipynb
pdflatex Capstone_Report.tex             # report built from figures/
```
