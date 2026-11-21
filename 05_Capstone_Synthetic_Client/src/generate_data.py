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
DATA = Path(__file__).resolve().parent.parent / "data"

SECTORS = ["Technology", "Healthcare", "Financials", "Energy",
           "Renewable Energy", "Real Estate"]

# Weekly factor model: r = alpha + beta * market + gamma * (rate change in 25 bp steps) + noise
# gamma < 0: the sector falls when rates rise (growth, long-duration assets)
SECTOR_PARAMS = {
    #                    alpha  beta   gamma  idio vol (all in % per week)
    "Technology":       (0.10, 1.30, -0.80, 1.40),
    "Healthcare":       (0.06, 0.60, -0.10, 0.80),
    "Financials":       (0.05, 1.00,  0.60, 1.10),
    "Energy":           (0.04, 0.80,  0.30, 1.80),
    "Renewable Energy": (0.08, 1.40, -1.00, 1.90),
    "Real Estate":      (0.03, 0.90, -0.90, 1.20),
}

# Market events: week -> (label, VIX shock, rate change in bp, sector shocks in %)
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


def client_profile() -> dict:
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


def market(rng: np.random.Generator) -> pd.DataFrame:
    weeks = np.arange(1, 53)
    dates = pd.date_range("2025-01-03", periods=52, freq="W-FRI")

    rate = np.empty(52); vix = np.empty(52); mkt = np.empty(52)
    r_prev, v_prev = 3.00, 15.0
    rows = {s: np.empty(52) for s in SECTORS}
    labels = []
    for i, w in enumerate(weeks):
        label, v_shock, d_bp, s_shock = EVENTS.get(w, ("", 0, 0, {}))
        labels.append(label)
        rate[i] = r_prev + d_bp / 100
        vix[i] = max(10.0, 15 + 0.65 * (v_prev - 15) + v_shock + rng.normal(0, 1.2))
        d_vix = vix[i] - v_prev
        mkt[i] = 0.20 - 0.30 * d_vix + rng.normal(0, 1.0)
        for s in SECTORS:
            a, b, g, sd = SECTOR_PARAMS[s]
            rows[s][i] = a + b * mkt[i] + g * (d_bp / 25) + s_shock.get(s, 0.0) + rng.normal(0, sd)
        r_prev, v_prev = rate[i], vix[i]

    df = pd.DataFrame({"week": weeks, "date": dates.date, "policy_rate_pct": rate.round(2),
                       "vix": vix.round(1), "market_return_pct": mkt.round(2)})
    for s in SECTORS:
        df[f"{s} (%)"] = rows[s].round(2)
    trend = pd.Series(mkt).rolling(4, min_periods=1).mean()
    df["sentiment"] = np.select([trend > 0.4, trend < -0.4], ["Positive", "Negative"], "Neutral")
    df["event"] = labels
    return df


def trades(rng: np.random.Generator, n: int = 3000) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Order-management records, custodian records with planted breaks, and the ground truth."""
    tickers = {"Technology": ["NVLT", "QBIT", "CLDX"], "Healthcare": ["MEDA", "GENX"],
               "Financials": ["BKRZ", "INSU"], "Renewable Energy": ["SOLR", "WNDP"],
               "Real Estate": ["RETX", "LOGI"]}
    px = {t: rng.uniform(20, 400) for ts in tickers.values() for t in ts}
    all_t = list(px)

    days = pd.bdate_range("2025-01-02", "2025-12-31")
    oms = pd.DataFrame({
        "trade_id": [f"KB-{i:06d}" for i in range(1, n + 1)],
        "trade_date": rng.choice(days, n),
        "ticker": rng.choice(all_t, n),
        "side": rng.choice(["BUY", "SELL"], n, p=[0.55, 0.45]),
        "quantity": (rng.integers(1, 200, n) * 50),
    })
    oms["price"] = [round(px[t] * (1 + rng.normal(0, 0.05)), 2) for t in oms["ticker"]]
    oms = oms.sort_values(["trade_date", "trade_id"]).reset_index(drop=True)
    oms["trade_date"] = pd.to_datetime(oms["trade_date"]).dt.date

    cust = oms.copy()
    truth = pd.DataFrame({"trade_id": oms["trade_id"], "break_type": "none"})
    idx = rng.permutation(n)

    # Planted issues (shares of all trades). "id_format" is NOT a real break:
    # the same trade written differently. A naive exact-match flags it; a good engine does not.
    plan = [("price", 0.040), ("quantity", 0.020), ("settle_date", 0.015),
            ("missing", 0.010), ("duplicate", 0.005), ("id_format", 0.010)]
    start = 0
    for kind, share in plan:
        k = int(round(share * n)); sel = idx[start:start + k]; start += k
        truth.loc[sel, "break_type"] = kind
        if kind == "price":
            cust.loc[sel, "price"] = (cust.loc[sel, "price"] * rng.choice([0.99, 1.01, 1.10, 0.90], k)).round(2)
        elif kind == "quantity":
            cust.loc[sel, "quantity"] = cust.loc[sel, "quantity"] + rng.choice([-50, 50, 500], k)
        elif kind == "settle_date":
            cust.loc[sel, "trade_date"] = [d + pd.Timedelta(days=1) for d in cust.loc[sel, "trade_date"]]
        elif kind == "id_format":
            cust.loc[sel, "trade_id"] = [f" {t.lower()}" for t in cust.loc[sel, "trade_id"]]
    # Tiny rounding noise on every price: real systems disagree in the 3rd decimal
    cust["price"] = (cust["price"] + rng.choice([0, 0, 0, 0.004, -0.004], n)).round(3)

    missing = truth.index[truth["break_type"] == "missing"]
    dup = truth.index[truth["break_type"] == "duplicate"]
    cust = pd.concat([cust.drop(index=missing), cust.loc[dup]]).sort_values("trade_date").reset_index(drop=True)
    cust = cust.rename(columns={"trade_date": "settle_ref_date"})
    return oms, cust, truth


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "client_profile.json").write_text(json.dumps(client_profile(), indent=2))
    mk = market(rng)
    mk.to_csv(DATA / "market_weekly.csv", index=False)
    oms, cust, truth = trades(rng)
    oms.to_csv(DATA / "trades_oms.csv", index=False)
    cust.to_csv(DATA / "trades_custodian.csv", index=False)
    truth.to_csv(DATA / "breaks_truth.csv", index=False)
    print(f"market_weekly.csv: {len(mk)} weeks | trades_oms.csv: {len(oms)} | "
          f"trades_custodian.csv: {len(cust)} | breaks: {(truth.break_type != 'none').sum()}")


if __name__ == "__main__":
    main()
