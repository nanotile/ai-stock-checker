"""
Module: test_persistence_sqlite
Version: 1.0.0
Iteration: v1
Developer: Kent Benson
UV Environment: uv sync && uv run python

Tests for SQLite-backed DataPersistence.
"""
import os
import tempfile
from stock_checker.persistence import DataPersistence


def _tmp_persistence():
    d = tempfile.mkdtemp()
    return DataPersistence(data_dir=d), d


def test_create_user():
    p, _ = _tmp_persistence()
    uid = p.create_user("alice", "alice@test.com", "hash123")
    assert uid == 1
    user = p.get_user_by_username("alice")
    assert user["email"] == "alice@test.com"


def test_create_portfolio():
    p, _ = _tmp_persistence()
    uid = p.create_user("bob", "bob@test.com", "hash")
    pid = p.create_portfolio(uid, "My EUR Book", "EUR", 100000.0, "revolut_standard")
    assert pid >= 1
    portfolios = p.list_portfolios(uid)
    assert len(portfolios) == 1
    assert portfolios[0]["currency"] == "EUR"


def test_save_load_portfolio_roundtrip():
    p, _ = _tmp_persistence()
    uid = p.create_user("carol", "carol@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "USD", 50000.0, "revolut_standard")
    data = {
        "initial_cash": 50000.0,
        "cash": 49000.0,
        "commission_rate": 0.0025,
        "commission_min": 1.0,
        "fee_preset": "revolut_standard",
        "holdings": {"AAPL": 10.0},
        "avg_buy_price": {"AAPL": 150.0},
        "total_fees_paid": 5.0,
        "fee_allowance_month": "2026-10",
        "fee_allowance_used": 1,
        "free_legs_per_month": 1,
    }
    p.save_portfolio(data, portfolio_id=pid)
    loaded = p.load_portfolio(portfolio_id=pid)
    assert loaded["cash"] == 49000.0
    assert loaded["holdings"]["AAPL"] == 10.0


def test_append_and_load_trades():
    p, _ = _tmp_persistence()
    uid = p.create_user("dave", "dave@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")
    trade = {
        "timestamp": "2026-10-24T12:00:00",
        "type": "BUY",
        "symbol": "AAPL",
        "quantity": 10.0,
        "price": 150.0,
        "cost": 1500.0,
        "commission": 3.75,
        "total_cost": 1503.75,
        "cash_remaining": 98496.25,
    }
    p.append_trade(trade, portfolio_id=pid)
    trades = p.load_trades(portfolio_id=pid)
    assert len(trades) == 1
    assert trades[0]["symbol"] == "AAPL"


def test_list_active_portfolios():
    p, _ = _tmp_persistence()
    u1 = p.create_user("eve", "eve@test.com", "hash")
    u2 = p.create_user("frank", "frank@test.com", "hash")
    p.create_portfolio(u1, "EUR Book", "EUR", 100000.0, "revolut_standard")
    p.create_portfolio(u2, "CAD Book", "CAD", 100000.0, "revolut_standard")
    active = p.list_active_portfolios()
    assert len(active) == 2


def test_entry_exit_times_roundtrip():
    p, _ = _tmp_persistence()
    uid = p.create_user("grace", "grace@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")
    p.save_entry_times({"AAPL": 1729785600.0}, portfolio_id=pid)
    loaded = p.load_entry_times(portfolio_id=pid)
    assert loaded["AAPL"] == 1729785600.0


def test_scanner_state_roundtrip():
    p, _ = _tmp_persistence()
    p.save_state({"scan_count": 42})
    loaded = p.load_state()
    assert loaded["scan_count"] == 42


def test_findings_roundtrip():
    p, _ = _tmp_persistence()
    uid = p.create_user("hank", "hank@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")
    finding = {
        "timestamp": "2026-10-24T12:00:00",
        "symbol": "AAPL",
        "action": "BUY",
        "confidence": "HIGH",
        "score": 35,
        "price": 150.0,
        "reasons": ["Strong momentum", "Near support"],
        "executed": True,
        "ai_validated": False,
    }
    p.append_finding(finding, portfolio_id=pid)
    loaded = p.load_findings(portfolio_id=pid)
    assert len(loaded) == 1
    assert loaded[0]["symbol"] == "AAPL"
    assert "Strong momentum" in loaded[0]["reasons"]


def test_scanned_symbols():
    p, _ = _tmp_persistence()
    p.track_scanned_symbol("AAPL", "paper")
    p.track_scanned_symbol("BTC-USD", "crypto")
    symbols = p.load_scanned_symbols()
    assert "AAPL" in symbols
    assert symbols["AAPL"]["source"] == "paper"
    assert p.get_symbol_source("AAPL") == "paper"
    assert p.get_symbol_source("UNKNOWN") is None


def test_backward_compat_no_portfolio_id():
    """Existing code that calls methods without portfolio_id should still work."""
    p, _ = _tmp_persistence()
    # Create a default user and portfolio so portfolio_id=1 exists
    uid = p.create_user("default", "default@test.com", "hash")
    p.create_portfolio(uid, "Default", "EUR", 100000.0, "revolut_standard")

    # Old-style calls without portfolio_id
    data = {
        "initial_cash": 100000.0,
        "cash": 100000.0,
        "commission_rate": 0.0025,
        "commission_min": 1.0,
        "fee_preset": "revolut_standard",
        "holdings": {},
        "avg_buy_price": {},
        "total_fees_paid": 0.0,
        "fee_allowance_month": "",
        "fee_allowance_used": 0,
        "free_legs_per_month": 1,
    }
    p.save_portfolio(data)
    loaded = p.load_portfolio()
    assert loaded is not None
    assert loaded["cash"] == 100000.0


def test_get_portfolio_meta():
    p, _ = _tmp_persistence()
    uid = p.create_user("ivan", "ivan@test.com", "hash")
    pid = p.create_portfolio(uid, "Test Book", "CAD", 50000.0, "revolut_standard")
    meta = p.get_portfolio_meta(pid)
    assert meta["currency"] == "CAD"
    assert meta["name"] == "Test Book"
    assert meta["initial_cash"] == 50000.0


def test_sell_trade_with_profit():
    """Test SELL trade with profit/loss tracking."""
    p, _ = _tmp_persistence()
    uid = p.create_user("jane", "jane@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")

    # Append a SELL trade
    sell_trade = {
        "timestamp": "2026-10-24T14:00:00",
        "type": "SELL",
        "symbol": "AAPL",
        "quantity": 10.0,
        "price": 160.0,
        "proceeds": 1600.0,
        "commission": 4.0,
        "net_proceeds": 1596.0,
        "cash_remaining": 101596.0,
        "buy_price": 150.0,
        "profit_loss": 96.0,
        "profit_loss_pct": 6.4,
    }
    p.append_trade(sell_trade, portfolio_id=pid)

    trades = p.load_trades(portfolio_id=pid)
    assert len(trades) == 1
    assert trades[0]["type"] == "SELL"
    assert trades[0]["profit_loss"] == 96.0
    assert trades[0]["net_proceeds"] == 1596.0


def test_trade_limit():
    """Test loading trades with limit."""
    p, _ = _tmp_persistence()
    uid = p.create_user("kate", "kate@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")

    # Add 5 trades
    for i in range(5):
        trade = {
            "timestamp": f"2026-10-24T12:{i:02d}:00",
            "type": "BUY",
            "symbol": "AAPL",
            "quantity": 1.0,
            "price": 150.0 + i,
            "cost": 150.0 + i,
            "commission": 1.0,
            "total_cost": 151.0 + i,
            "cash_remaining": 100000.0 - (151.0 + i) * (i + 1),
        }
        p.append_trade(trade, portfolio_id=pid)

    # Load last 2 trades
    last_2 = p.load_trades(limit=2, portfolio_id=pid)
    assert len(last_2) == 2
    assert last_2[-1]["price"] == 154.0  # Last trade


def test_findings_with_filters():
    """Test loading findings with symbol and action filters."""
    p, _ = _tmp_persistence()
    uid = p.create_user("luke", "luke@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")

    # Add findings for different symbols and actions
    findings = [
        {"symbol": "AAPL", "action": "BUY", "price": 150.0, "reasons": ["Test 1"]},
        {"symbol": "AAPL", "action": "SELL", "price": 160.0, "reasons": ["Test 2"]},
        {"symbol": "MSFT", "action": "BUY", "price": 300.0, "reasons": ["Test 3"]},
    ]

    for f in findings:
        p.append_finding(f, portfolio_id=pid)

    # Filter by symbol
    aapl_findings = p.load_findings(symbol="AAPL", portfolio_id=pid)
    assert len(aapl_findings) == 2

    # Filter by action
    buy_findings = p.load_findings(action="BUY", portfolio_id=pid)
    assert len(buy_findings) == 2

    # Filter by both
    aapl_buy = p.load_findings(symbol="AAPL", action="BUY", portfolio_id=pid)
    assert len(aapl_buy) == 1
    assert aapl_buy[0]["price"] == 150.0


def test_position_times_upsert():
    """Test that entry/exit times correctly upsert."""
    p, _ = _tmp_persistence()
    uid = p.create_user("mary", "mary@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")

    # Save initial entry time
    p.save_entry_times({"AAPL": 1000.0}, portfolio_id=pid)
    assert p.load_entry_times(portfolio_id=pid)["AAPL"] == 1000.0

    # Update entry time (upsert)
    p.save_entry_times({"AAPL": 2000.0}, portfolio_id=pid)
    assert p.load_entry_times(portfolio_id=pid)["AAPL"] == 2000.0

    # Save exit time for same symbol
    p.save_exit_times({"AAPL": 3000.0}, portfolio_id=pid)
    assert p.load_exit_times(portfolio_id=pid)["AAPL"] == 3000.0

    # Entry time should still be there
    assert p.load_entry_times(portfolio_id=pid)["AAPL"] == 2000.0


def test_scanned_symbols_batch():
    """Test batch symbol tracking."""
    p, _ = _tmp_persistence()

    symbols = ["AAPL", "MSFT", "GOOGL"]
    p.track_scanned_symbols_batch(symbols, "paper")

    loaded = p.load_scanned_symbols()
    assert len(loaded) == 3
    assert all(s in loaded for s in symbols)
    assert all(loaded[s]["source"] == "paper" for s in symbols)


def test_get_summary():
    """Test summary method."""
    p, _ = _tmp_persistence()
    uid = p.create_user("nancy", "nancy@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")

    # Add some data
    p.append_trade({
        "type": "BUY",
        "symbol": "AAPL",
        "quantity": 10.0,
        "price": 150.0,
        "commission": 1.0,
        "total_cost": 1501.0,
        "cash_remaining": 98499.0,
    }, portfolio_id=pid)

    p.append_finding({
        "symbol": "AAPL",
        "action": "BUY",
        "price": 150.0,
        "reasons": ["Test"],
    }, portfolio_id=pid)

    summary = p.get_summary()
    assert summary["total_users"] == 1
    assert summary["total_portfolios"] == 1
    assert summary["total_trades"] == 1
    assert summary["total_findings"] == 1


def test_export_csv():
    """Test CSV export."""
    p, data_dir = _tmp_persistence()
    uid = p.create_user("oscar", "oscar@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")

    # Add some data
    p.append_trade({
        "type": "BUY",
        "symbol": "AAPL",
        "quantity": 10.0,
        "price": 150.0,
        "commission": 1.0,
        "total_cost": 1501.0,
        "cash_remaining": 98499.0,
    }, portfolio_id=pid)

    p.append_finding({
        "symbol": "AAPL",
        "action": "BUY",
        "price": 150.0,
        "reasons": ["Test reason"],
    }, portfolio_id=pid)

    result = p.export_csv()
    assert result["trades_csv"] is not None
    assert result["findings_csv"] is not None

    # Verify files exist
    import os
    assert os.path.exists(result["trades_csv"])
    assert os.path.exists(result["findings_csv"])


def test_trade_context_fields():
    """Test that extra trade context fields are preserved."""
    p, _ = _tmp_persistence()
    uid = p.create_user("paul", "paul@test.com", "hash")
    pid = p.create_portfolio(uid, "Test", "EUR", 100000.0, "revolut_standard")

    trade = {
        "type": "BUY",
        "symbol": "AAPL",
        "quantity": 10.0,
        "price": 150.0,
        "commission": 1.0,
        "total_cost": 1501.0,
        "cash_remaining": 98499.0,
        "strategy": "momentum",
        "note": "Strong breakout",
        "score": 85,
        "confidence": "HIGH",
    }

    p.append_trade(trade, portfolio_id=pid)
    trades = p.load_trades(portfolio_id=pid)

    assert trades[0]["strategy"] == "momentum"
    assert trades[0]["note"] == "Strong breakout"
    assert trades[0]["score"] == 85
    assert trades[0]["confidence"] == "HIGH"
