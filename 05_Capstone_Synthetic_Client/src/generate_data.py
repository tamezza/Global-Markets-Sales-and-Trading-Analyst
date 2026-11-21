"""Generate the synthetic data set for the capstone project.

Everything here is invented: the client, the market and the trades. The
generator is deterministic (fixed seed), so running it again reproduces the
same files exactly.

Outputs (written to ../data/):
    client_profile.json   the fictional client: allocation, objectives, constraints
    market_weekly.csv     52 weeks of sector returns, VIX, policy rate, sentiment, events
    trades_oms.csv        3,000 trades as recorded by the order management system
    trades_custodian.csv  the same trades as booked by the custodian, with planted breaks
    breaks_truth.csv      ground truth: which trades carry which break (for scoring)

Usage:
    python src/generate_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2025
N_WEEKS = 52
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SECTORS = ["Technology", "Healthcare", "Financials", "Energy",
           "Renewable Energy", "Real Estate"]

# Weekly factor model for each sector:
#   return = alpha + beta * market_return + rate_sensitivity * (rate change in 25 bp steps) + noise
# A negative rate_sensitivity means the sector falls when rates rise (growth, long-duration assets).
SECTOR_PARAMS = {
    #                    alpha  beta   rate_sensitivity  noise_vol   (all in % per week)
    "Technology":       (0.10, 1.30, -0.80, 1.40),
    "Healthcare":       (0.06, 0.60, -0.10, 0.80),
    "Financials":       (0.05, 1.00,  0.60, 1.10),
    "Energy":           (0.04, 0.80,  0.30, 1.80),
    "Renewable Energy": (0.08, 1.40, -1.00, 1.90),
    "Real Estate":      (0.03, 0.90, -0.90, 1.20),
}

# Scripted market events: week -> (label, VIX shock, rate change in bp, extra sector moves in %)
EVENTS = {
    8:  ("Rate hike +25 bp", 4, 25, {}),
    14: ("Geopolitical shock", 9, 0, {"Energy": 3.0}),
    16: ("Rate hike +25 bp", 3, 25, {}),
    22: ("Strong tech earnings", -3, 0, {"Technology": 3.0}),
    24: ("Rate hike +25 bp", 3, 25, {}),
    30: ("Regional bank stress", 7, 0, {"Financials": -4.0, "Real Estate": -1.5}),
    40: ("First rate cut -25 bp", -4, -25, {}),
    45: ("Renewable subsidy package", -1, 0, {"Renewable Energy": 4.0}),
    48: ("Rate cut -25 bp", -2, -25, {}),
}

# Planted reconciliation issues, as a share of all trades.
# "id_format" is NOT a real break: the same trade ID written differently.
# A naive exact match flags it; a good reconciliation engine should not.
PLANTED_BREAKS = [("price", 0.040), ("quantity", 0.020), ("settle_date", 0.015),
                  ("missing", 0.010), ("duplicate", 0.005), ("id_format", 0.010)]


def make_client_profile() -> dict:
    return {
        "name": "Kestrel Bay Capital",
        "note": "Fictional client created for this capstone; any resemblance to a real firm is coincidental.",
        "type": "Mid-sized multi-family office",
        "aum_usd": 250_000_000,
        "allocation_pct": {"Technology": 35, "Healthcare": 15, "Financials": 10,
                           "Energy": 0, "Renewable Energy": 15, "Real Estate": 10,
                           "Cash": 15},
        "risk_tolerance": "Moderate-high",
        "horizon_years": "5-7",
        "objectives": [
            "Long-term growth above a 6% annual target",
            "Keep the portfolio's maximum drawdown under 10%",
            "Maintain a sustainability tilt (at least 15% in renewable or ESG assets)",
            "Faster, more reliable trade reporting from the bank",
        ],
        "constraints": [
            "No single sector above 40%",
            "Cash between 5% and 20%",
            "No leverage",
        ],
        "concerns": [
            "Technology concentration and sensitivity to interest rates",
            "Rate path uncertainty: hikes early in the year, cuts expected later",
            "Late or inaccurate trade confirmations from the bank's back office",
        ],
    }


def make_market(rng: np.random.Generator) -> pd.DataFrame:
    weeks = np.arange(1, N_WEEKS + 1)
    dates = pd.date_range("2025-01-03", periods=N_WEEKS, freq="W-FRI")

    policy_rate = np.empty(N_WEEKS)
    vix = np.empty(N_WEEKS)
    market_return = np.empty(N_WEEKS)
    returns_by_sector = {sector: np.empty(N_WEEKS) for sector in SECTORS}
    event_labels = []

    previous_rate, previous_vix = 3.00, 15.0
    for i, week in enumerate(weeks):
        label, vix_shock, rate_change_bp, sector_shocks = EVENTS.get(week, ("", 0, 0, {}))
        event_labels.append(label)

        policy_rate[i] = previous_rate + rate_change_bp / 100
        # VIX is pulled back towards 15 each week, plus event shocks and noise
        vix[i] = max(10.0, 15 + 0.65 * (previous_vix - 15) + vix_shock + rng.normal(0, 1.2))
        vix_change = vix[i] - previous_vix
        # the market falls when fear (VIX) rises
        market_return[i] = 0.20 - 0.30 * vix_change + rng.normal(0, 1.0)

        for sector in SECTORS:
            alpha, beta, rate_sensitivity, noise_vol = SECTOR_PARAMS[sector]
            returns_by_sector[sector][i] = (alpha + beta * market_return[i]
                                            + rate_sensitivity * (rate_change_bp / 25)
                                            + sector_shocks.get(sector, 0.0)
                                            + rng.normal(0, noise_vol))
        previous_rate, previous_vix = policy_rate[i], vix[i]

    market = pd.DataFrame({"week": weeks, "date": dates.date,
                           "policy_rate_pct": policy_rate.round(2),
                           "vix": vix.round(1),
                           "market_return_pct": market_return.round(2)})
    for sector in SECTORS:
        market[f"{sector} (%)"] = returns_by_sector[sector].round(2)
    four_week_trend = pd.Series(market_return).rolling(4, min_periods=1).mean()
    market["sentiment"] = np.select([four_week_trend > 0.4, four_week_trend < -0.4],
                                    ["Positive", "Negative"], "Neutral")
    market["event"] = event_labels
    return market


def make_trades(rng: np.random.Generator, n_trades: int = 3000
                ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Order-management records, custodian records with planted breaks, and the ground truth."""
    tickers_by_sector = {"Technology": ["NVLT", "QBIT", "CLDX"], "Healthcare": ["MEDA", "GENX"],
                         "Financials": ["BKRZ", "INSU"], "Renewable Energy": ["SOLR", "WNDP"],
                         "Real Estate": ["RETX", "LOGI"]}
    base_price = {ticker: rng.uniform(20, 400)
                  for tickers in tickers_by_sector.values() for ticker in tickers}
    all_tickers = list(base_price)

    business_days = pd.bdate_range("2025-01-02", "2025-12-31")
    oms_trades = pd.DataFrame({
        "trade_id": [f"KB-{i:06d}" for i in range(1, n_trades + 1)],
        "trade_date": rng.choice(business_days, n_trades),
        "ticker": rng.choice(all_tickers, n_trades),
        "side": rng.choice(["BUY", "SELL"], n_trades, p=[0.55, 0.45]),
        "quantity": (rng.integers(1, 200, n_trades) * 50),
    })
    oms_trades["price"] = [round(base_price[ticker] * (1 + rng.normal(0, 0.05)), 2)
                           for ticker in oms_trades["ticker"]]
    oms_trades = oms_trades.sort_values(["trade_date", "trade_id"]).reset_index(drop=True)
    oms_trades["trade_date"] = pd.to_datetime(oms_trades["trade_date"]).dt.date

    custodian_trades = oms_trades.copy()
    truth = pd.DataFrame({"trade_id": oms_trades["trade_id"], "break_type": "none"})
    shuffled_rows = rng.permutation(n_trades)

    next_row = 0
    for break_type, share in PLANTED_BREAKS:
        n_rows = int(round(share * n_trades))
        rows = shuffled_rows[next_row:next_row + n_rows]
        next_row += n_rows
        truth.loc[rows, "break_type"] = break_type
        if break_type == "price":
            price_errors = rng.choice([0.99, 1.01, 1.10, 0.90], n_rows)
            custodian_trades.loc[rows, "price"] = (custodian_trades.loc[rows, "price"] * price_errors).round(2)
        elif break_type == "quantity":
            custodian_trades.loc[rows, "quantity"] = (custodian_trades.loc[rows, "quantity"]
                                                      + rng.choice([-50, 50, 500], n_rows))
        elif break_type == "settle_date":
            custodian_trades.loc[rows, "trade_date"] = [day + pd.Timedelta(days=1)
                                                        for day in custodian_trades.loc[rows, "trade_date"]]
        elif break_type == "id_format":
            custodian_trades.loc[rows, "trade_id"] = [f" {trade_id.lower()}"
                                                      for trade_id in custodian_trades.loc[rows, "trade_id"]]
    # Tiny rounding noise on every price: real systems disagree in the 3rd decimal
    custodian_trades["price"] = (custodian_trades["price"]
                                 + rng.choice([0, 0, 0, 0.004, -0.004], n_trades)).round(3)

    missing_rows = truth.index[truth["break_type"] == "missing"]
    duplicated_rows = truth.index[truth["break_type"] == "duplicate"]
    custodian_trades = (pd.concat([custodian_trades.drop(index=missing_rows), custodian_trades.loc[duplicated_rows]])
                        .sort_values("trade_date").reset_index(drop=True))
    custodian_trades = custodian_trades.rename(columns={"trade_date": "settle_ref_date"})
    return oms_trades, custodian_trades, truth


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "client_profile.json").write_text(json.dumps(make_client_profile(), indent=2))

    market = make_market(rng)
    market.to_csv(DATA_DIR / "market_weekly.csv", index=False)

    oms_trades, custodian_trades, truth = make_trades(rng)
    oms_trades.to_csv(DATA_DIR / "trades_oms.csv", index=False)
    custodian_trades.to_csv(DATA_DIR / "trades_custodian.csv", index=False)
    truth.to_csv(DATA_DIR / "breaks_truth.csv", index=False)

    n_breaks = (truth["break_type"] != "none").sum()
    print(f"market_weekly.csv: {len(market)} weeks | trades_oms.csv: {len(oms_trades)} | "
          f"trades_custodian.csv: {len(custodian_trades)} | planted issues: {n_breaks}")


if __name__ == "__main__":
    main()
