"""Tests for flat-file to SQLite migration."""
import json
import os
import tempfile
from stock_checker.migrate_to_sqlite import migrate_if_needed


def test_migrate_creates_default_user_and_portfolio():
    d = tempfile.mkdtemp()
    # Write legacy flat files
    portfolio = {
        "initial_cash": 100000.0,
        "cash": 95000.0,
        "commission_rate": 0.0025,
        "commission_min_eur": 1.0,
        "fee_preset": "revolut_standard",
        "holdings": {"AAPL": 10},
        "avg_buy_price": {"AAPL": 150.0},
        "total_fees_paid": 5.0,
        "fee_allowance_month": "",
        "fee_allowance_used": 0,
        "free_legs_per_month": 1,
    }
    with open(os.path.join(d, "portfolio.json"), "w") as f:
        json.dump(portfolio, f)

    trade = {
        "timestamp": "2026-10-24T12:00:00",
        "type": "BUY",
        "symbol": "AAPL",
        "quantity": 10,
        "price": 150.0,
        "cost": 1500.0,
        "commission": 3.75,
        "total_cost": 1503.75,
        "cash_remaining": 98496.25,
    }
    with open(os.path.join(d, "trades.jsonl"), "w") as f:
        f.write(json.dumps(trade) + "\n")

    result = migrate_if_needed(d)
    assert result["migrated"] is True
    assert result["portfolio_id"] >= 1

    # Legacy files renamed
    assert os.path.exists(os.path.join(d, "portfolio.json.migrated"))
    assert not os.path.exists(os.path.join(d, "portfolio.json"))

    # Verify data in SQLite
    from stock_checker.persistence import DataPersistence
    p = DataPersistence(data_dir=d)
    loaded = p.load_portfolio(portfolio_id=result["portfolio_id"])
    assert loaded["cash"] == 95000.0
    assert loaded["holdings"]["AAPL"] == 10.0

    # Verify trades migrated
    trades = p.load_trades(portfolio_id=result["portfolio_id"])
    assert len(trades) == 1
    assert trades[0]["symbol"] == "AAPL"


def test_migrate_skips_when_no_legacy():
    d = tempfile.mkdtemp()
    result = migrate_if_needed(d)
    assert result["migrated"] is False


def test_migrate_skips_when_already_migrated():
    d = tempfile.mkdtemp()
    # Write a portfolio file
    with open(os.path.join(d, "portfolio.json"), "w") as f:
        json.dump({"initial_cash": 100000.0, "cash": 100000.0, "holdings": {},
                    "avg_buy_price": {}, "total_fees_paid": 0.0}, f)

    # First migration
    result1 = migrate_if_needed(d)
    assert result1["migrated"] is True

    # Write another portfolio file to simulate
    with open(os.path.join(d, "portfolio.json"), "w") as f:
        json.dump({"initial_cash": 50000.0}, f)

    # Second migration should skip
    result2 = migrate_if_needed(d)
    assert result2["migrated"] is False


def test_migrate_handles_legacy_commission_min_eur():
    """Legacy files use commission_min_eur which should be mapped to commission_min."""
    d = tempfile.mkdtemp()
    portfolio = {
        "initial_cash": 100000.0,
        "cash": 100000.0,
        "commission_min_eur": 1.0,
        "commission_rate": 0.0025,
        "fee_preset": "revolut_standard",
        "holdings": {},
        "avg_buy_price": {},
        "total_fees_paid": 0.0,
    }
    with open(os.path.join(d, "portfolio.json"), "w") as f:
        json.dump(portfolio, f)

    result = migrate_if_needed(d)
    assert result["migrated"] is True

    from stock_checker.persistence import DataPersistence
    p = DataPersistence(data_dir=d)
    loaded = p.load_portfolio(portfolio_id=result["portfolio_id"])
    assert loaded["commission_min"] == 1.0
