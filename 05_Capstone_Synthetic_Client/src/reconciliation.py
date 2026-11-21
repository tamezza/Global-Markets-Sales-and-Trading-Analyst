"""Trade reconciliation: compare the order management system (OMS) with the custodian's records.

Two engines:
- naive_reconcile:  what a quick spreadsheet lookup does (exact ID match, exact field comparison)
- reconcile:        a rule-based engine (normalised IDs, duplicate detection, price tolerance,
                    one clear break type per trade, exception report with a priority and an action)

Both return one row per OMS trade with a 'status' column:
    "match", "price", "quantity", "settle_date", "missing", "duplicate"
Neither engine ever reads the ground truth.
"""
from __future__ import annotations

import pandas as pd

BREAK_TYPES = ["price", "quantity", "settle_date", "missing", "duplicate"]

SUGGESTED_ACTION = {
    "price": "Check the execution price with the broker; ask the custodian to amend the booking",
    "quantity": "Confirm the filled quantity with the trader; amend the side that is wrong",
    "settle_date": "Check the trade date / settlement instructions; usually a booking-date error",
    "missing": "Custodian has no record: send the trade details to the custodian today",
    "duplicate": "Custodian booked the trade twice: request cancellation of the duplicate",
}


def normalise_trade_id(trade_ids: pd.Series) -> pd.Series:
    """' kb-000123' and 'KB-000123' are the same trade: strip spaces and use upper case."""
    return trade_ids.astype(str).str.strip().str.upper()


def naive_reconcile(oms: pd.DataFrame, custodian: pd.DataFrame) -> pd.DataFrame:
    """Exact lookup on the raw trade ID, exact comparison of every field (first match only)."""
    first_booking = custodian.drop_duplicates("trade_id")
    merged = oms.merge(first_booking, on="trade_id", how="left", suffixes=("", "_cust"), indicator=True)
    status = pd.Series("match", index=merged.index)
    status[merged["settle_ref_date"] != merged["trade_date"]] = "settle_date"
    status[merged["quantity_cust"] != merged["quantity"]] = "quantity"
    status[merged["price_cust"] != merged["price"]] = "price"
    status[merged["_merge"] == "left_only"] = "missing"
    return pd.DataFrame({"trade_id": merged["trade_id"], "status": status})


def reconcile(oms: pd.DataFrame, custodian: pd.DataFrame, price_tolerance_bp: float = 10.0) -> pd.DataFrame:
    """Rule-based reconciliation. Checks, in order of severity:
    missing booking -> duplicate booking -> quantity -> price (outside tolerance) -> trade date.
    price_tolerance_bp: price differences up to this many basis points count as rounding, not a break.
    """
    custodian = custodian.assign(trade_key=normalise_trade_id(custodian["trade_id"]))
    oms = oms.assign(trade_key=normalise_trade_id(oms["trade_id"]))

    bookings_per_trade = custodian["trade_key"].value_counts()
    first_booking = custodian.drop_duplicates("trade_key").drop(columns="trade_id")
    merged = oms.merge(first_booking, on="trade_key", how="left", suffixes=("", "_cust"), indicator=True)

    is_missing = merged["_merge"] == "left_only"
    is_duplicate = merged["trade_key"].map(bookings_per_trade).fillna(0) > 1
    quantity_gap = merged["quantity_cust"] - merged["quantity"]
    price_gap_bp = 10_000 * (merged["price_cust"] - merged["price"]) / merged["price"]
    date_differs = merged["settle_ref_date"] != merged["trade_date"]

    status = pd.Series("match", index=merged.index)
    status[date_differs] = "settle_date"
    status[price_gap_bp.abs() > price_tolerance_bp] = "price"
    status[quantity_gap != 0] = "quantity"
    status[is_duplicate] = "duplicate"
    status[is_missing] = "missing"

    result = pd.DataFrame({
        "trade_id": merged["trade_id"],
        "status": status,
        "ticker": merged["ticker"],
        "side": merged["side"],
        "notional_usd": merged["quantity"] * merged["price"],
        "oms_price": merged["price"], "custodian_price": merged["price_cust"],
        "price_gap_bp": price_gap_bp.round(1),
        "oms_quantity": merged["quantity"], "custodian_quantity": merged["quantity_cust"],
        "oms_date": merged["trade_date"], "custodian_date": merged["settle_ref_date"],
    })
    result["action"] = result["status"].map(SUGGESTED_ACTION).fillna("")
    return result


def exception_report(reconciled: pd.DataFrame) -> pd.DataFrame:
    """Breaks only, largest money at risk first, with a simple priority."""
    breaks = reconciled[reconciled["status"] != "match"].copy()
    breaks["priority"] = pd.cut(breaks["notional_usd"], bins=[0, 100_000, 1_000_000, float("inf")],
                                labels=["Low", "Medium", "High"]).astype(str)
    breaks.loc[breaks["status"].isin(["missing", "duplicate"]), "priority"] = "High"   # settlement risk
    priority_rank = breaks["priority"].map({"High": 0, "Medium": 1, "Low": 2})
    breaks = breaks.assign(priority_rank=priority_rank).sort_values(["priority_rank", "notional_usd"],
                                                                   ascending=[True, False])
    return breaks.drop(columns="priority_rank")
