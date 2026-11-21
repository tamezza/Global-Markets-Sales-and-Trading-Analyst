"""Shared simulation tools for the capstone notebooks (Stages 2 and 3).

- simulate_years:      many random years from the same market model as generate_data.py
- make_risk_off_weights: the defensive allocation used when risk triggers fire
- run_policy:          run a management approach (buy and hold, monthly rebalance, risk triggers)
- yearly_metrics:      annual return, volatility and maximum drawdown of each simulated year
"""
from __future__ import annotations

import numpy as np

from generate_data import SECTORS, SECTOR_PARAMS

WEEKS_PER_YEAR = 52
ASSETS = SECTORS + ["Cash"]
ASSET_POSITION = {asset: i for i, asset in enumerate(ASSETS)}

# Random events in simulated years (weekly chances)
VIX_JUMP_CHANCE, RATE_MOVE_CHANCE, SECTOR_SHOCK_CHANCE = 0.08, 0.06, 0.03

# Management rules
POLICIES = ["Buy and hold", "Monthly rebalance", "Rebalance + risk triggers"]
REBALANCE_EVERY_N_WEEKS = 4
VIX_SWITCH_ON, VIX_SWITCH_OFF = 20, 17
DRAWDOWN_SWITCH_ON, DRAWDOWN_SWITCH_OFF = -0.05, -0.03
TRADING_COST = 0.0005                      # 5 bp of the amount traded

# Client limits used when building the risk-off allocation
MAX_CASH, MAX_SECTOR = 0.20, 0.40


def simulate_years(n_years, n_weeks=WEEKS_PER_YEAR, seed=7):
    """Generate n_years random years of weekly sector returns (%), policy rate (%) and VIX."""
    rng = np.random.default_rng(seed)
    n_sectors = len(SECTORS)
    vix = np.empty((n_years, n_weeks))
    policy_rate = np.empty((n_years, n_weeks))
    sector_returns = np.empty((n_years, n_weeks, n_sectors))
    params = np.array([SECTOR_PARAMS[sector] for sector in SECTORS])    # alpha, beta, rate sensitivity, noise vol
    alpha, beta, rate_sensitivity, noise_vol = params.T
    previous_vix = np.full(n_years, 15.0)
    previous_rate = np.full(n_years, 3.0)

    for week in range(n_weeks):
        has_vix_jump = rng.random(n_years) < VIX_JUMP_CHANCE
        vix_jump = has_vix_jump * rng.normal(8, 3, n_years)
        new_vix = np.maximum(10, 15 + 0.65 * (previous_vix - 15) + vix_jump + rng.normal(0, 1.2, n_years))

        has_rate_move = rng.random(n_years) < RATE_MOVE_CHANCE
        rate_move_bp = has_rate_move * rng.choice([-25, 25], n_years)
        new_rate = np.clip(previous_rate + rate_move_bp / 100, 1, 6)
        rate_move_bp = (new_rate - previous_rate) * 100                 # after the 1%-6% bounds

        market_return = 0.20 - 0.30 * (new_vix - previous_vix) + rng.normal(0, 1.0, n_years)

        sector_shock = np.zeros((n_years, n_sectors))
        has_sector_shock = rng.random(n_years) < SECTOR_SHOCK_CHANCE
        shock_size = rng.choice([-4, 4], has_sector_shock.sum())          # drawn before the sector (keeps the seed's sequence)
        shocked_sector = rng.integers(0, n_sectors, has_sector_shock.sum())
        sector_shock[has_sector_shock, shocked_sector] = shock_size

        noise = rng.normal(0, 1, (n_years, n_sectors)) * noise_vol
        sector_returns[:, week, :] = (alpha + np.outer(market_return, beta)
                                      + np.outer(rate_move_bp / 25, rate_sensitivity) + sector_shock + noise)
        vix[:, week], policy_rate[:, week] = new_vix, new_rate
        previous_vix, previous_rate = new_vix, new_rate
    return sector_returns, policy_rate, vix


def make_risk_off_weights(target_weights):
    """Defensive version of an allocation: take 8 pts from Technology and 2 from Renewable Energy,
    move them to cash (up to the 20% cap), and put the rest into Healthcare (up to the 40% cap)."""
    weights = np.asarray(target_weights, dtype=float).copy()
    tech, renewable = ASSET_POSITION["Technology"], ASSET_POSITION["Renewable Energy"]
    healthcare, cash = ASSET_POSITION["Healthcare"], ASSET_POSITION["Cash"]
    taken_from_tech = min(0.08, weights[tech])
    taken_from_renewable = min(0.02, weights[renewable])
    weights[tech] -= taken_from_tech
    weights[renewable] -= taken_from_renewable
    to_move = taken_from_tech + taken_from_renewable
    to_cash = min(to_move, MAX_CASH - weights[cash])
    weights[cash] += to_cash
    weights[healthcare] += to_move - to_cash
    assert abs(weights.sum() - 1) < 1e-9
    assert weights[cash] <= MAX_CASH + 1e-9 and weights[:cash].max() <= MAX_SECTOR + 1e-9
    return weights


def run_policy(sector_returns, policy_rate, vix, policy, target_weights, risk_off_weights=None):
    """Run one management approach over many simulated years at once.

    sector_returns: (n_years, n_weeks, n_sectors), weekly %
    policy_rate, vix: (n_years, n_weeks)
    target_weights: allocation over ASSETS (sectors + cash), summing to 1
    Returns weekly portfolio returns (n_years, n_weeks) in %, the risk-off flag of each week, and total turnover.
    """
    target_weights = np.asarray(target_weights, dtype=float)
    if risk_off_weights is None:
        risk_off_weights = make_risk_off_weights(target_weights)
    n_years, n_weeks, _ = sector_returns.shape
    weights = np.tile(target_weights, (n_years, 1))
    portfolio_value = np.ones(n_years)
    peak_value = np.ones(n_years)
    in_risk_off = np.zeros(n_years, dtype=bool)
    weekly_returns = np.empty((n_years, n_weeks))
    risk_off_flags = np.zeros((n_years, n_weeks), dtype=bool)
    turnover = np.zeros(n_years)

    for week in range(n_weeks):
        # 1. Decide whether to trade, using last week's information only
        if policy != "Buy and hold" and week > 0:
            weights_to_hold = np.tile(target_weights, (n_years, 1))
            state_changed = np.zeros(n_years, dtype=bool)
            if policy == "Rebalance + risk triggers":
                drawdown = portfolio_value / peak_value - 1
                switch_on = (vix[:, week - 1] > VIX_SWITCH_ON) | (drawdown < DRAWDOWN_SWITCH_ON)
                switch_off = (vix[:, week - 1] < VIX_SWITCH_OFF) & (drawdown > DRAWDOWN_SWITCH_OFF)
                state_changed = (switch_on & ~in_risk_off) | (switch_off & in_risk_off)
                in_risk_off = np.where(switch_on, True, np.where(switch_off, False, in_risk_off))
                weights_to_hold[in_risk_off] = risk_off_weights
            trade_now = state_changed | (week % REBALANCE_EVERY_N_WEEKS == 0)
            amount_traded = np.abs(weights_to_hold - weights).sum(axis=1) * trade_now
            turnover += amount_traded
            weights = np.where(trade_now[:, None], weights_to_hold, weights)
            portfolio_value *= 1 - TRADING_COST * amount_traded
        risk_off_flags[:, week] = in_risk_off

        # 2. Earn this week's returns (cash earns the policy rate)
        cash_return = policy_rate[:, week:week + 1] / WEEKS_PER_YEAR
        asset_returns = np.concatenate([sector_returns[:, week, :], cash_return], axis=1) / 100
        portfolio_return = (weights * asset_returns).sum(axis=1)
        weekly_returns[:, week] = 100 * portfolio_return
        portfolio_value *= 1 + portfolio_return
        peak_value = np.maximum(peak_value, portfolio_value)

        # 3. Weights drift with prices until the next trade
        weights = weights * (1 + asset_returns)
        weights /= weights.sum(axis=1, keepdims=True)
    return weekly_returns, risk_off_flags, turnover


def yearly_metrics(weekly_returns):
    """Weekly % returns (n_years, n_weeks) -> annual return, annual volatility and max drawdown per year, in %."""
    value_index = np.cumprod(1 + weekly_returns / 100, axis=1)
    max_drawdown = 100 * (value_index / np.maximum.accumulate(value_index, axis=1) - 1).min(axis=1)
    annual_return = 100 * (value_index[:, -1] - 1)
    annual_volatility = weekly_returns.std(axis=1, ddof=1) * np.sqrt(WEEKS_PER_YEAR)
    return annual_return, annual_volatility, max_drawdown
