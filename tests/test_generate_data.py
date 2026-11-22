"""The synthetic data must be exactly reproducible: same seed -> byte-identical files."""
import json

import numpy as np

import generate_data
from conftest import DATA_DIR


def test_generator_reproduces_committed_files_exactly(tmp_path):
    rng = np.random.default_rng(generate_data.SEED)        # same order of random draws as generate_data.main()
    market = generate_data.make_market(rng)
    oms_trades, custodian_trades, truth = generate_data.make_trades(rng)

    regenerated = {
        "market_weekly.csv": market,
        "trades_oms.csv": oms_trades,
        "trades_custodian.csv": custodian_trades,
        "breaks_truth.csv": truth,
    }
    for file_name, table in regenerated.items():
        table.to_csv(tmp_path / file_name, index=False)
        assert (tmp_path / file_name).read_bytes() == (DATA_DIR / file_name).read_bytes(), file_name


def test_client_profile_matches_generator():
    committed = json.loads((DATA_DIR / "client_profile.json").read_text())
    assert committed == generate_data.make_client_profile()


def test_client_allocation_sums_to_100_and_respects_rules():
    allocation = generate_data.make_client_profile()["allocation_pct"]
    assert sum(allocation.values()) == 100
    assert max(weight for asset, weight in allocation.items() if asset != "Cash") <= 40
    assert 5 <= allocation["Cash"] <= 20


def test_planted_breaks_have_the_documented_counts(ground_truth):
    counts = ground_truth["break_type"].value_counts()
    expected = {break_type: round(share * 3000) for break_type, share in generate_data.PLANTED_BREAKS}
    for break_type, expected_count in expected.items():
        assert counts[break_type] == expected_count, break_type
