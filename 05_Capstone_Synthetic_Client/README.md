# Part 5 — Capstone: A Synthetic Client, End to End

**Status:** 🔄 In progress (Stages 1–2 of 4 done)

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

## Roadmap

| Stage | Skill from | Notebook | Status |
|-------|-----------|----------|--------|
| 1. Market insight | Part 1 | [01_market_insight.ipynb](01_market_insight.ipynb) | ✅ Done |
| 2. Live market dynamics: replay the year with rebalancing triggers; rate and drawdown stress tests | Part 2 | [02_live_dynamics.ipynb](02_live_dynamics.ipynb) | ✅ Done |
| 3. Product recommendation: an allocation that meets every client constraint, with products mapped to objectives | Part 3 | `03_product_recommendation.ipynb` | ⏳ |
| 4. Process automation: a working reconciliation engine, scored against the ground truth | Part 4 | `04_reconciliation_engine.ipynb` | ⏳ |
| Final report combining all four stages | — | `Capstone_Report.tex` | ⏳ |

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

## Reproduce

```bash
pip install -r ../requirements.txt
python src/generate_data.py            # optional: the data are already committed
jupyter notebook 01_market_insight.ipynb   # then 02_live_dynamics.ipynb
```
