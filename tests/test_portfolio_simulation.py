"""The simulation must be reproducible and respect the client's rules."""
import numpy as np
import pytest

from portfolio_simulation import (ASSETS, MAX_CASH, MAX_SECTOR, make_risk_off_weights, run_policy,
                                  simulate_years, yearly_metrics)

CLIENT_WEIGHTS = np.array([0.35, 0.15, 0.10, 0.00, 0.15, 0.10, 0.15])   # Kestrel Bay, order of ASSETS


def test_simulated_years_are_reproducible_with_the_same_seed():
    first = simulate_years(50, seed=123)
    second = simulate_years(50, seed=123)
    for array_a, array_b in zip(first, second):
        np.testing.assert_array_equal(array_a, array_b)


def test_different_seeds_give_different_years():
    returns_a, _, _ = simulate_years(50, seed=1)
    returns_b, _, _ = simulate_years(50, seed=2)
    assert not np.allclose(returns_a, returns_b)


def test_risk_off_allocation_for_the_client():
    risk_off = make_risk_off_weights(CLIENT_WEIGHTS)
    expected = dict(zip(ASSETS, [0.27, 0.20, 0.10, 0.00, 0.13, 0.10, 0.20]))
    np.testing.assert_allclose(risk_off, [expected[asset] for asset in ASSETS])


@pytest.mark.parametrize("seed", range(20))
def test_risk_off_allocation_always_respects_the_rules(seed):
    # Random allocations that themselves respect the client's rules (cash 5-20%, no sector above 40%)
    rng = np.random.default_rng(seed)
    while True:
        cash = rng.uniform(0.05, MAX_CASH)
        sector_weights = rng.dirichlet(np.ones(6)) * (1 - cash)
        if sector_weights.max() <= MAX_SECTOR:
            break
    weights = np.append(sector_weights, cash)
    risk_off = make_risk_off_weights(weights)
    assert risk_off.sum() == pytest.approx(1)
    assert risk_off[-1] <= MAX_CASH + 1e-9
    assert risk_off[:-1].max() <= MAX_SECTOR + 1e-9


def test_buy_and_hold_never_trades():
    returns, rates, vix = simulate_years(20, seed=5)
    _, risk_off_flags, turnover = run_policy(returns, rates, vix, "Buy and hold", CLIENT_WEIGHTS)
    assert (turnover == 0).all()
    assert not risk_off_flags.any()


def test_yearly_metrics_on_a_known_path():
    weekly_returns = np.array([[10.0, -50.0, 20.0]])        # +10%, -50%, +20%
    annual_return, _, max_drawdown = yearly_metrics(weekly_returns)
    assert annual_return[0] == pytest.approx(100 * (1.1 * 0.5 * 1.2 - 1))
    assert max_drawdown[0] == pytest.approx(-50.0)


def test_risk_off_moves_only_what_fits_when_cash_and_healthcare_are_nearly_full():
    # Regression test: Healthcare 38% and cash 17% leave room for only 5 of the 10 points to move
    weights = np.array([0.20, 0.38, 0.10, 0.00, 0.15, 0.00, 0.17])
    risk_off = make_risk_off_weights(weights)
    position = {asset: i for i, asset in enumerate(ASSETS)}
    assert risk_off[position["Cash"]] == pytest.approx(MAX_CASH)
    assert risk_off[position["Healthcare"]] == pytest.approx(MAX_SECTOR)
    assert risk_off.sum() == pytest.approx(1)
