"""The reconciliation engine must find every real break and ignore harmless differences."""
import pandas as pd
import pytest

from reconciliation import exception_report, naive_reconcile, normalise_trade_id, reconcile


def classification_accuracy(result, ground_truth):
    scored = result[["trade_id", "status"]].merge(ground_truth, on="trade_id")
    return (scored["status"] == scored["expected_status"]).mean()


def test_engine_classifies_every_trade_correctly(oms_trades, custodian_trades, ground_truth):
    result = reconcile(oms_trades, custodian_trades, price_tolerance_bp=10)
    assert len(result) == len(oms_trades)
    assert classification_accuracy(result, ground_truth) == 1.0


def test_engine_treats_rewritten_ids_as_matches(oms_trades, custodian_trades, ground_truth):
    result = reconcile(oms_trades, custodian_trades).merge(ground_truth, on="trade_id")
    rewritten_ids = result[result["break_type"] == "id_format"]
    assert len(rewritten_ids) == 30
    assert (rewritten_ids["status"] == "match").all()


def test_naive_lookup_is_worse_than_engine(oms_trades, custodian_trades, ground_truth):
    naive = naive_reconcile(oms_trades, custodian_trades)
    assert classification_accuracy(naive, ground_truth) < 0.7          # documented: about 61%


@pytest.mark.parametrize("raw, expected", [(" kb-000123", "KB-000123"), ("KB-000123 ", "KB-000123"),
                                           ("kb-000123", "KB-000123")])
def test_trade_id_normalisation(raw, expected):
    assert normalise_trade_id(pd.Series([raw])).iloc[0] == expected


def make_one_trade(oms_price, custodian_price):
    oms = pd.DataFrame({"trade_id": ["KB-000001"], "trade_date": ["2025-01-02"], "ticker": ["NVLT"],
                        "side": ["BUY"], "quantity": [100], "price": [oms_price]})
    custodian = oms.rename(columns={"trade_date": "settle_ref_date"}).assign(price=custodian_price)
    return oms, custodian


@pytest.mark.parametrize("custodian_price, expected_status", [
    (100.05, "match"),     # 5 bp: rounding, inside the 10 bp tolerance
    (100.50, "price"),     # 50 bp: a real price break
])
def test_price_tolerance(custodian_price, expected_status):
    oms, custodian = make_one_trade(100.0, custodian_price)
    assert reconcile(oms, custodian, price_tolerance_bp=10)["status"].iloc[0] == expected_status


def test_exception_report_lists_high_priority_first(oms_trades, custodian_trades):
    report = exception_report(reconcile(oms_trades, custodian_trades))
    assert len(report) == 270
    priority_order = report["priority"].map({"High": 0, "Medium": 1, "Low": 2})
    assert priority_order.is_monotonic_increasing
    assert (report.loc[report["status"].isin(["missing", "duplicate"]), "priority"] == "High").all()
