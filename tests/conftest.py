"""Shared setup for the tests: make the capstone's src/ modules importable and load its data once."""
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CAPSTONE_DIR = REPO_ROOT / "05_Capstone_Synthetic_Client"
DATA_DIR = CAPSTONE_DIR / "data"
sys.path.insert(0, str(CAPSTONE_DIR / "src"))


@pytest.fixture(scope="session")
def oms_trades():
    return pd.read_csv(DATA_DIR / "trades_oms.csv")


@pytest.fixture(scope="session")
def custodian_trades():
    return pd.read_csv(DATA_DIR / "trades_custodian.csv")


@pytest.fixture(scope="session")
def ground_truth():
    truth = pd.read_csv(DATA_DIR / "breaks_truth.csv")
    # An ID written differently is the same trade, so the correct answer is "match"
    truth["expected_status"] = truth["break_type"].replace({"none": "match", "id_format": "match"})
    return truth
