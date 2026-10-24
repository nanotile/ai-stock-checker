# Multi-User Multi-Currency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-user support with JWT auth, multiple portfolios per user, and EUR/USD/CAD currency selection — backed by SQLite instead of flat JSON files.

**Architecture:** SQLite Shim approach — replace `DataPersistence` flat-file backend with SQLite while preserving the existing interface. Portfolio class gains a `currency` field. `commission_min_eur` renamed to `commission_min` throughout. Shared scanner loop iterates over all active portfolios. JWT auth gates the desk UI.

**Tech Stack:** Python 3 stdlib `sqlite3`, `bcrypt` for password hashing, existing FastAPI + Jinja2 desk UI, `pytz` for market hours.

**Design spec:** `docs/superpowers/specs/2026-10-24-multi-currency-multi-user-design.md`

---

## Task 1: Currency Module

**Files:**
- Create: `stock_checker/currency.py`
- Test: `tests/test_currency.py`

**Step 1: Write the test**

```python
# tests/test_currency.py
"""Tests for currency module."""
from stock_checker.currency import (
    SUPPORTED_CURRENCIES,
    CURRENCY_SYMBOL,
    CURRENCY_EXCHANGES,
    CURRENCY_FEE_MINIMUMS,
    currency_symbol,
    exchanges_for_currency,
    fee_minimum_for,
)


def test_supported_currencies():
    assert "EUR" in SUPPORTED_CURRENCIES
    assert "USD" in SUPPORTED_CURRENCIES
    assert "CAD" in SUPPORTED_CURRENCIES


def test_currency_symbol_lookup():
    assert currency_symbol("EUR") == "€"
    assert currency_symbol("USD") == "$"
    assert currency_symbol("CAD") == "C$"
    assert currency_symbol("UNKNOWN") == "?"


def test_exchanges_for_currency():
    assert "XETR" in exchanges_for_currency("EUR")
    assert "US" in exchanges_for_currency("USD")
    assert "TSX" in exchanges_for_currency("CAD")
    assert exchanges_for_currency("UNKNOWN") == []


def test_fee_minimum_for():
    assert fee_minimum_for("revolut_standard", "EUR") == 1.0
    assert fee_minimum_for("revolut_standard", "CAD") == 1.5
    assert fee_minimum_for("binance_like", "USD") == 0.0
    # Unknown currency falls back to EUR
    assert fee_minimum_for("revolut_standard", "GBP") == 1.0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_currency.py -v`
Expected: FAIL — module does not exist yet

**Step 3: Write the implementation**

```python
# stock_checker/currency.py
"""Currency configuration — symbols, exchanges, fee tables."""

from __future__ import annotations

SUPPORTED_CURRENCIES = ("EUR", "USD", "CAD")

CURRENCY_SYMBOL: dict[str, str] = {
    "EUR": "€",
    "USD": "$",
    "CAD": "C$",
}

# Which MIC-lite exchange venues belong to each currency
CURRENCY_EXCHANGES: dict[str, list[str]] = {
    "EUR": ["XETR"],
    "USD": ["US"],
    "CAD": ["TSX"],
}

# Per-currency fee minimums by preset name
CURRENCY_FEE_MINIMUMS: dict[str, dict[str, float]] = {
    "EUR": {
        "revolut_standard": 1.0,
        "revolut_plus": 1.0,
        "revolut_ultra": 1.0,
        "binance_like": 0.0,
    },
    "USD": {
        "revolut_standard": 1.0,
        "revolut_plus": 1.0,
        "revolut_ultra": 1.0,
        "binance_like": 0.0,
    },
    "CAD": {
        "revolut_standard": 1.5,
        "revolut_plus": 1.5,
        "revolut_ultra": 1.5,
        "binance_like": 0.0,
    },
}


def currency_symbol(currency: str) -> str:
    """Return display symbol for a currency code."""
    return CURRENCY_SYMBOL.get(str(currency or "").upper(), "?")


def exchanges_for_currency(currency: str) -> list[str]:
    """Return MIC-lite exchange venues for a currency."""
    return list(CURRENCY_EXCHANGES.get(str(currency or "").upper(), []))


def fee_minimum_for(preset: str, currency: str = "EUR") -> float:
    """Look up fee minimum for a preset + currency. Falls back to EUR."""
    cur = str(currency or "EUR").upper()
    table = CURRENCY_FEE_MINIMUMS.get(cur, CURRENCY_FEE_MINIMUMS["EUR"])
    return float(table.get(str(preset or "revolut_standard"), 1.0))
```

**Step 4: Run test**

Run: `python -m pytest tests/test_currency.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add stock_checker/currency.py tests/test_currency.py
git commit -m "feat: add currency module (EUR/USD/CAD symbols, exchanges, fee tables)"
```

---

## Task 2: Canadian Universe

**Files:**
- Create: `stock_checker/canadian_universe.py`
- Test: `tests/test_canadian_universe.py`

**Step 1: Write the test**

```python
# tests/test_canadian_universe.py
"""Tests for Canadian TSX universe seed."""
from stock_checker.canadian_universe import CANADIAN_TSX_SEED


def test_seed_not_empty():
    assert len(CANADIAN_TSX_SEED) >= 30


def test_all_tickers_end_with_to():
    for symbol in CANADIAN_TSX_SEED:
        assert symbol.endswith(".TO"), f"{symbol} missing .TO suffix"


def test_all_entries_have_exchange_tsx():
    for symbol, info in CANADIAN_TSX_SEED.items():
        assert info["exchange"] == "TSX", f"{symbol} exchange is {info['exchange']}"


def test_all_entries_have_sector():
    for symbol, info in CANADIAN_TSX_SEED.items():
        assert info.get("sector"), f"{symbol} missing sector"


def test_known_names_present():
    assert "RY.TO" in CANADIAN_TSX_SEED   # Royal Bank
    assert "SHOP.TO" in CANADIAN_TSX_SEED  # Shopify
    assert "ENB.TO" in CANADIAN_TSX_SEED   # Enbridge
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_canadian_universe.py -v`
Expected: FAIL — module does not exist

**Step 3: Write the implementation**

```python
# stock_checker/canadian_universe.py
"""Curated Canadian TSX (.TO) seed for the paper scanner."""

from __future__ import annotations

# Liquid TSX 60 / large-cap names on Yahoo Finance (CAD). Not exhaustive.
CANADIAN_TSX_SEED: dict[str, dict[str, str]] = {
    "RY.TO":    {"sector": "banking",    "exchange": "TSX"},
    "TD.TO":    {"sector": "banking",    "exchange": "TSX"},
    "BNS.TO":   {"sector": "banking",    "exchange": "TSX"},
    "BMO.TO":   {"sector": "banking",    "exchange": "TSX"},
    "CM.TO":    {"sector": "banking",    "exchange": "TSX"},
    "NA.TO":    {"sector": "banking",    "exchange": "TSX"},
    "ENB.TO":   {"sector": "energy",     "exchange": "TSX"},
    "CNQ.TO":   {"sector": "energy",     "exchange": "TSX"},
    "SU.TO":    {"sector": "energy",     "exchange": "TSX"},
    "TRP.TO":   {"sector": "energy",     "exchange": "TSX"},
    "CVE.TO":   {"sector": "energy",     "exchange": "TSX"},
    "IMO.TO":   {"sector": "energy",     "exchange": "TSX"},
    "CNR.TO":   {"sector": "transport",  "exchange": "TSX"},
    "CP.TO":    {"sector": "transport",  "exchange": "TSX"},
    "SHOP.TO":  {"sector": "technology", "exchange": "TSX"},
    "CSU.TO":   {"sector": "technology", "exchange": "TSX"},
    "OTEX.TO":  {"sector": "technology", "exchange": "TSX"},
    "MFC.TO":   {"sector": "insurance",  "exchange": "TSX"},
    "SLF.TO":   {"sector": "insurance",  "exchange": "TSX"},
    "GWO.TO":   {"sector": "insurance",  "exchange": "TSX"},
    "IFC.TO":   {"sector": "insurance",  "exchange": "TSX"},
    "BCE.TO":   {"sector": "telecom",    "exchange": "TSX"},
    "T.TO":     {"sector": "telecom",    "exchange": "TSX"},
    "RCI-B.TO": {"sector": "telecom",    "exchange": "TSX"},
    "ABX.TO":   {"sector": "mining",     "exchange": "TSX"},
    "FNV.TO":   {"sector": "mining",     "exchange": "TSX"},
    "WPM.TO":   {"sector": "mining",     "exchange": "TSX"},
    "NTR.TO":   {"sector": "materials",  "exchange": "TSX"},
    "CCL-B.TO": {"sector": "materials",  "exchange": "TSX"},
    "L.TO":     {"sector": "grocery",    "exchange": "TSX"},
    "ATD.TO":   {"sector": "retail",     "exchange": "TSX"},
    "DOL.TO":   {"sector": "retail",     "exchange": "TSX"},
    "BAM.TO":   {"sector": "asset_mgmt", "exchange": "TSX"},
    "BN.TO":    {"sector": "asset_mgmt", "exchange": "TSX"},
    "FFH.TO":   {"sector": "insurance",  "exchange": "TSX"},
    "WCN.TO":   {"sector": "industrial", "exchange": "TSX"},
    "TRI.TO":   {"sector": "technology", "exchange": "TSX"},
    "QSR.TO":   {"sector": "restaurant", "exchange": "TSX"},
    "GIB-A.TO": {"sector": "technology", "exchange": "TSX"},
}
```

**Step 4: Run test**

Run: `python -m pytest tests/test_canadian_universe.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add stock_checker/canadian_universe.py tests/test_canadian_universe.py
git commit -m "feat: add curated Canadian TSX universe (~39 tickers)"
```

---

## Task 3: Market Hours — TSX Support

**Files:**
- Modify: `stock_checker/market_hours.py`
- Modify: `tests/test_market_hours.py`

**Step 1: Add TSX tests to existing test file**

Append to `tests/test_market_hours.py`:

```python
def test_is_canadian_equity():
    from stock_checker.market_hours import is_canadian_equity
    assert is_canadian_equity("RY.TO") is True
    assert is_canadian_equity("shop.to") is True
    assert is_canadian_equity("AAPL") is False
    assert is_canadian_equity("SAP.DE") is False


def test_tsx_session_closed_weekend(monkeypatch):
    from stock_checker.market_hours import is_tsx_session_closed
    from datetime import datetime
    import pytz
    # Saturday noon ET
    sat = pytz.timezone("US/Eastern").localize(datetime(2026, 10, 24, 12, 0))
    assert is_tsx_session_closed(now=sat) is True


def test_tsx_session_open_weekday(monkeypatch):
    from stock_checker.market_hours import is_tsx_session_closed
    from datetime import datetime
    import pytz
    # Monday 10:00 ET — inside session
    mon = pytz.timezone("US/Eastern").localize(datetime(2026, 10, 26, 10, 0))
    assert is_tsx_session_closed(now=mon) is False


def test_equity_session_closed_routes_tsx():
    from stock_checker.market_hours import is_equity_session_closed
    from datetime import datetime
    import pytz
    # Monday 10:00 ET — TSX open
    mon = pytz.timezone("US/Eastern").localize(datetime(2026, 10, 26, 10, 0))
    assert is_equity_session_closed("RY.TO", now=mon) is False
```

**Step 2: Run tests to verify failures**

Run: `python -m pytest tests/test_market_hours.py -v -k "canadian or tsx"`
Expected: FAIL — functions not defined

**Step 3: Modify `stock_checker/market_hours.py`**

Add after the existing US constants (after line 20):

```python
# TSX hours — same wall-clock as US but different exchange holidays.
TSX_OPEN = dt_time(9, 30)
TSX_CLOSE = dt_time(16, 0)
TSX_TZ = "US/Eastern"  # Toronto is Eastern time
```

Add new function after `is_german_equity`:

```python
def is_canadian_equity(symbol: str) -> bool:
    """Yahoo TSX common stocks use the .TO suffix."""
    return str(symbol or "").upper().strip().endswith(".TO")
```

Add session helpers:

```python
def is_tsx_session_closed(*, now: Optional[datetime] = None) -> bool:
    return _session_closed(tz_name=TSX_TZ, open_t=TSX_OPEN, close_t=TSX_CLOSE, now=now)


def last_tsx_session_close(*, now: Optional[datetime] = None) -> datetime:
    return last_session_close_at(tz_name=TSX_TZ, close_t=TSX_CLOSE, now=now)
```

Modify `is_equity_session_closed` (line 100-112) to add `.TO` check before `.DE`:

```python
def is_equity_session_closed(symbol: str, *, now: Optional[datetime] = None) -> bool:
    if is_crypto_symbol(symbol):
        return False
    if is_canadian_equity(symbol):
        return is_tsx_session_closed(now=now)
    if is_german_equity(symbol):
        return is_xetra_session_closed(now=now)
    return is_us_cash_session_closed(now=now)
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_market_hours.py -v`
Expected: ALL PASS (existing + new)

**Step 5: Commit**

```bash
git add stock_checker/market_hours.py tests/test_market_hours.py
git commit -m "feat: add TSX market hours and is_canadian_equity detection"
```

---

## Task 4: Stock Universe Manager — TSX Venue + Canadian Seed

**Files:**
- Modify: `stock_checker/stock_universe_manager.py:13-14,18-51,116-274,283-324`
- Modify: `tests/test_stock_universe_manager.py`

**Step 1: Add TSX venue tests**

Append to `tests/test_stock_universe_manager.py`:

```python
def test_listing_venue_tsx():
    from stock_checker.stock_universe_manager import listing_venue
    assert listing_venue("RY.TO") == "TSX"
    assert listing_venue("SHOP.TO") == "TSX"
    assert listing_venue("RY.TO", "TSX") == "TSX"
    assert listing_venue("RY", "TSX") == "TSX"
    assert listing_venue("RY", "XTSE") == "TSX"
```

**Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_stock_universe_manager.py::test_listing_venue_tsx -v`
Expected: FAIL — TSX not recognized

**Step 3: Modify `stock_checker/stock_universe_manager.py`**

Add import at line 14:
```python
from stock_checker.canadian_universe import CANADIAN_TSX_SEED
```

Add TSX venue set after `_XETR_VENUE_EXCHANGES` (line 32):
```python
_TSX_VENUE_EXCHANGES = frozenset({"TSX", "XTSE", "TO", "TORONTO"})
```

Modify `listing_venue()` — add `.TO` check after `.DE` check (after line 44):
```python
    if sym.endswith(".TO"):
        return "TSX"
```

And add TSX exchange check after Xetra check (after line 47):
```python
    if ex in _TSX_VENUE_EXCHANGES:
        return "TSX"
```

Add `**CANADIAN_TSX_SEED` to `_seed_initial_universe` initial_stocks dict (alongside `**GERMAN_XETRA_SEED` at line 227).

Add `**CANADIAN_TSX_SEED` to `ensure_curated_seed` extras dict (alongside `**GERMAN_XETRA_SEED` at line 322).

**Step 4: Run tests**

Run: `python -m pytest tests/test_stock_universe_manager.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add stock_checker/stock_universe_manager.py tests/test_stock_universe_manager.py
git commit -m "feat: add TSX venue detection and Canadian seed to universe manager"
```

---

## Task 5: Fee Rename — EUR to Currency-Neutral

This is the mechanical rename across the codebase. `commission_min_eur` → `commission_min` everywhere.

**Files:**
- Modify: `stock_checker/fees.py` (constants, FEE_PRESETS, calc_commission, FeeAllowanceLedger)
- Modify: `stock_checker/portfolio.py` (constructor, load, save, set_fee_schedule)
- Modify: `stock_checker/trader_config.py` (~12 references)
- Modify: `stock_checker/intelligent_trader.py` (2 references)
- Modify: `stock_checker/backtester.py` (3 references)
- Modify: `stock_checker/fee_burn.py` (hardcoded `€`)
- Modify: `openbb_backend/desk.py` (~6 references)
- Modify: `openbb_backend/templates/desk_ops.html` (2 references)
- Modify: `scripts/run_experiment.py` (3 references)
- Modify: `scripts/benchmark_buy_hold.py` (1 reference)
- Modify: `scripts/reset_paper_portfolio.py` (1 reference)
- Modify: `tests/test_fees.py`, `tests/test_portfolio.py`, `tests/test_trader_config.py`, `tests/test_backtester.py`, `tests/test_fee_burn.py`

**Strategy:** This is a global find-and-replace. The key renames:

| Old | New |
|-----|-----|
| `REVOLUT_STANDARD_MIN_EUR` | `REVOLUT_STANDARD_MIN` |
| `REVOLUT_ULTRA_MIN_EUR` | `REVOLUT_ULTRA_MIN` |
| `BINANCE_LIKE_MIN_EUR` | `BINANCE_LIKE_MIN` |
| `commission_min_eur` (dict key) | `commission_min` |
| `commission_min_eur` (param/attr) | `commission_min` |
| `min_eur` (param in calc_commission, FeeAllowanceLedger) | `min_amount` |

**Step 1: Run existing tests to confirm green baseline**

Run: `python -m pytest tests/test_fees.py tests/test_portfolio.py tests/test_trader_config.py tests/test_fee_burn.py -v`
Expected: ALL PASS

**Step 2: Rename in `stock_checker/fees.py`**

- Lines 18-22: rename constants (`_MIN_EUR` → `_MIN`)
- Lines 24-48: rename `commission_min_eur` key → `commission_min` in FEE_PRESETS
- Lines 29,35: update labels to use generic format (drop `€1 min` → `1 min`)
- Line 58: rename param `min_eur` → `min_amount` in `calc_commission`
- Line 82: rename `commission_min_eur` → `commission_min` in `rates_for_preset` return source
- Lines 119-132: rename `min_eur` → `min_amount` in `FeeAllowanceLedger.commission_for_leg`

**Step 3: Rename in `stock_checker/portfolio.py`**

- Line 7: update import `REVOLUT_STANDARD_MIN_EUR` → `REVOLUT_STANDARD_MIN`
- Line 22: rename param `commission_min_eur` → `commission_min`
- Lines 31-33: update docstring
- Lines 49-51: rename loaded key
- Line 71: rename attribute
- Line 108: rename kwarg `min_eur` → `min_amount`
- Line 125: rename attribute in `set_fee_schedule`
- Line 326: rename in `_save_state`

**Step 4: Rename in `stock_checker/trader_config.py`**

- Lines 68,86,101-103,147-158,243,253,854,1087: rename all `commission_min_eur` → `commission_min`

**Step 5: Rename in remaining files**

- `stock_checker/intelligent_trader.py:109,1517,1530` — rename references
- `stock_checker/backtester.py:215,222,242` — rename param and attribute
- `stock_checker/fee_burn.py:61` — add `currency` param, use `currency_symbol()` instead of hardcoded `€`
- `openbb_backend/desk.py` — rename ~6 references
- `openbb_backend/templates/desk_ops.html:534,587` — rename template vars
- `scripts/run_experiment.py:62,258,324` — rename
- `scripts/benchmark_buy_hold.py:201` — rename
- `scripts/reset_paper_portfolio.py:188` — rename

**Step 6: Update all tests**

- `tests/test_portfolio.py:11,27,41,52` — rename params
- `tests/test_trader_config.py:26,140,186` — rename keys
- `tests/test_backtester.py:95` — rename param
- `tests/test_fee_burn.py` — update if hardcoded `€` assertions exist

**Step 7: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS — same count as before

**Step 8: Commit**

```bash
git add -u
git commit -m "refactor: rename commission_min_eur to commission_min (currency-neutral)"
```

**Note:** Do NOT rename `commission_min_eur` inside `docs/history/` files — those are historical snapshots and should not be modified.

---

## Task 6: Portfolio — Add Currency Field

**Files:**
- Modify: `stock_checker/portfolio.py`
- Modify: `tests/test_portfolio.py`

**Step 1: Add currency test**

```python
# Append to tests/test_portfolio.py
def test_portfolio_currency_default():
    p = Portfolio(initial_cash=1000, commission_rate=0.0, commission_min=0.0,
                  enable_risk_management=False)
    assert p.currency == "EUR"


def test_portfolio_currency_usd():
    p = Portfolio(initial_cash=1000, commission_rate=0.0, commission_min=0.0,
                  currency="USD", enable_risk_management=False)
    assert p.currency == "USD"
```

**Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_portfolio.py::test_portfolio_currency_default -v`
Expected: FAIL — no `currency` param

**Step 3: Modify `stock_checker/portfolio.py`**

Add `currency: str = "EUR"` param to `__init__`. Store as `self.currency`.
Include `"currency": self.currency` in `_save_state()` dict.
Load from persisted data: `self.currency = loaded.get("currency", "EUR")`.

**Step 4: Run tests**

Run: `python -m pytest tests/test_portfolio.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add stock_checker/portfolio.py tests/test_portfolio.py
git commit -m "feat: add currency field to Portfolio class"
```

---

## Task 7: SQLite Persistence Layer

This is the largest task. Replace `DataPersistence` flat-file backend with SQLite.

**Files:**
- Modify: `stock_checker/persistence.py`
- Create: `tests/test_persistence_sqlite.py`

**Step 1: Write core persistence tests**

```python
# tests/test_persistence_sqlite.py
"""Tests for SQLite-backed DataPersistence."""
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
```

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_persistence_sqlite.py -v`
Expected: FAIL — new methods don't exist

**Step 3: Rewrite `stock_checker/persistence.py`**

Replace the flat-file implementation with SQLite. Preserve the public interface (method names, return shapes). Add new multi-user methods. Key implementation details:

- `__init__`: open `data_dir/stockchecker.db`, set WAL mode, create tables
- All existing methods gain optional `portfolio_id` kwarg (default 1 for backward compat)
- `save_portfolio`: UPSERT portfolios row + DELETE/INSERT holdings rows
- `load_portfolio`: SELECT from portfolios + holdings, return same Dict shape
- `append_trade`: INSERT into trades, map `total_cost`/`net_proceeds` to `net_amount`
- `load_trades`: SELECT with optional limit, reconstruct Dict shape
- New: `create_user`, `get_user_by_username`, `create_portfolio`, `list_portfolios`, `list_active_portfolios`, `get_portfolio_meta`

**Step 4: Run tests**

Run: `python -m pytest tests/test_persistence_sqlite.py -v`
Expected: ALL PASS

**Step 5: Run existing tests to check backward compat**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS — existing code using DataPersistence still works

**Step 6: Commit**

```bash
git add stock_checker/persistence.py tests/test_persistence_sqlite.py
git commit -m "feat: replace flat-file persistence with SQLite backend"
```

---

## Task 8: Migration Script

**Files:**
- Create: `stock_checker/migrate_to_sqlite.py`
- Test: `tests/test_migration.py`

**Step 1: Write migration test**

```python
# tests/test_migration.py
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


def test_migrate_skips_when_no_legacy():
    d = tempfile.mkdtemp()
    result = migrate_if_needed(d)
    assert result["migrated"] is False
```

**Step 2: Implement migration**

```python
# stock_checker/migrate_to_sqlite.py
"""One-time migration from flat JSON files to SQLite."""
```

Migration reads `portfolio.json`, `trades.jsonl`, `findings.jsonl`, `entry_times.json`, `exit_times.json`. Creates a default user (`admin`/`admin@localhost`/placeholder hash). Creates a portfolio from the JSON data. Imports trades and findings. Renames legacy files to `.migrated`.

**Step 3: Run tests, commit**

```bash
git add stock_checker/migrate_to_sqlite.py tests/test_migration.py
git commit -m "feat: add flat-file to SQLite migration script"
```

---

## Task 9: User Provisioning CLI

**Files:**
- Create: `stock_checker/create_user.py`

**Step 1: Write the CLI script**

```python
# stock_checker/create_user.py
"""CLI to create pre-configured user accounts.

Usage: python -m stock_checker.create_user --username kent --email kent@example.com --password <pw>
"""
```

Uses `bcrypt` for password hashing. Writes to SQLite via `DataPersistence.create_user()`. Optionally creates a default portfolio with `--portfolio-name` and `--currency` flags.

**Step 2: Test manually**

Run: `python -m stock_checker.create_user --username testuser --email test@test.com --password test123 --currency USD --portfolio-name "USD Book"`
Expected: prints user ID and portfolio ID

**Step 3: Commit**

```bash
pip install bcrypt  # if not already installed
git add stock_checker/create_user.py
git commit -m "feat: add CLI for user provisioning (create_user.py)"
```

---

## Task 10: Auth Integration — cloudflarekb-add-login

**Files:**
- Modify: `openbb_backend/main.py`
- Create: `openbb_backend/auth.py` (JWT helpers)
- Create: `openbb_backend/static/login.css` (login page styles)
- Create: `openbb_backend/templates/login.html`

**Step 1: Invoke cloudflarekb-add-login skill for JWT scaffolding**

This task uses the `cloudflarekb-add-login` skill to generate the auth middleware.

**Step 2: Create auth module**

`openbb_backend/auth.py` — JWT encode/decode, password verification, FastAPI dependency `get_current_user(request) -> dict`. Reads `JWT_SECRET` from env (with fallback to a generated secret stored in `data/jwt_secret.txt`).

**Step 3: Add login routes to main.py**

- `GET /desk/login` — render login.html template
- `POST /desk/auth/login` — validate credentials via persistence, issue JWT cookie
- `GET /desk/logout` — clear cookie, redirect to login
- Auth dependency on all `/desk/*` routes (except login/logout/static)

**Step 4: Test login flow manually**

Create a user, start desk, navigate to `desk.kentbenson.net`, verify redirect to login, login, verify dashboard loads.

**Step 5: Commit**

```bash
git add openbb_backend/auth.py openbb_backend/templates/login.html openbb_backend/static/login.css openbb_backend/main.py
git commit -m "feat: add JWT auth with login page for desk dashboard"
```

---

## Task 11: Desk UI — Portfolio Selector + Dynamic Currency

**Files:**
- Modify: `openbb_backend/main.py` (portfolio CRUD endpoints, currency formatting)
- Modify: `openbb_backend/desk.py` (snapshot currency, portfolio scoping)
- Modify: `openbb_backend/templates/desk_ops.html` (portfolio dropdown, currency symbols)

**Step 1: Add portfolio API endpoints**

- `GET /desk/api/portfolios` — list current user's portfolios
- `POST /desk/api/portfolios` — create new portfolio (name, currency, initial_cash, fee_preset)
- `DELETE /desk/api/portfolios/{id}` — soft-delete (set is_active=0)

**Step 2: Add portfolio selector to desk header**

Dropdown in the desk HTML. Selected portfolio ID stored as cookie `desk_portfolio_id`. All data endpoints read this cookie to scope queries.

**Step 3: Replace all hardcoded `€` with dynamic currency**

In `openbb_backend/main.py` (portfolio summary ~lines 609-619): replace `€` with `{sym}` where `sym = currency_symbol(portfolio_currency)`.

In `openbb_backend/desk.py`: all `commission_min_eur` references → `commission_min`, all `€` formatting → dynamic.

In `openbb_backend/templates/desk_ops.html`: replace `€` with template variable `{{ currency_sym }}`.

**Step 4: Add "New Portfolio" form**

Simple form: name text input, currency dropdown (EUR/USD/CAD), initial cash number input, fee preset dropdown.

**Step 5: Test manually**

Login → create a USD portfolio → switch to it → verify `$` symbol throughout → create a CAD portfolio → verify `C$`.

**Step 6: Commit**

```bash
git add -u
git add openbb_backend/templates/ openbb_backend/static/
git commit -m "feat: add portfolio selector and dynamic currency display to desk"
```

---

## Task 12: Trader Loop — Multi-Portfolio Iteration

**Files:**
- Modify: `stock_checker/intelligent_trader.py`

**Step 1: Modify `IntelligentTrader.__init__`**

Instead of creating a single `Portfolio`, load all active portfolios from SQLite:

```python
active = self.persistence.list_active_portfolios()
if not active:
    print("⚠️  No active portfolios. Create users/portfolios first.")
    print("   Run: python -m stock_checker.create_user --help")
self.portfolios = {}  # {portfolio_id: Portfolio}
for row in active:
    # Create Portfolio instance from each active portfolio row
    ...
```

**Step 2: Modify scan/trade cycle**

In the main loop (currently processes one portfolio):
1. Run scanner once (shared)
2. For each portfolio in `self.portfolios`:
   a. Filter opportunities to symbols matching portfolio's currency exchanges
   b. Run entry/exit decision logic
   c. Execute trades
3. Refresh portfolio list every 10 cycles

**Step 3: Run existing tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS — existing tests use Portfolio directly, not the multi-portfolio path

**Step 4: Manual integration test**

Create two users with different currencies. Start trader. Verify both portfolios get scanned and show independent decisions in their trade logs.

**Step 5: Commit**

```bash
git add stock_checker/intelligent_trader.py
git commit -m "feat: trader loop iterates over all active portfolios"
```

---

## Task 13: Integration Test + Systemd Update

**Files:**
- Modify: `~/.config/systemd/user/ai-stock-trader.service`
- Modify: `docker-compose.yml`

**Step 1: Create initial user + portfolio**

```bash
python -m stock_checker.create_user --username kent --email kent@example.com --password <pw> --currency EUR --portfolio-name "EUR Book"
```

**Step 2: Run migration**

```bash
python -c "from stock_checker.migrate_to_sqlite import migrate_if_needed; print(migrate_if_needed('data/'))"
```

Verify existing portfolio.json data migrated into SQLite as kent's EUR portfolio.

**Step 3: Restart services**

```bash
systemctl --user restart ai-stock-trader
systemctl --user restart ai-stock-desk
```

**Step 4: Verify end-to-end**

- `desk.kentbenson.net` → login page → login as kent
- Dashboard shows EUR Book with migrated data
- Create a USD portfolio, create a CAD portfolio
- Trader log shows multi-portfolio iteration
- Each portfolio shows correct currency symbol

**Step 5: Commit service changes**

```bash
git add docker-compose.yml
git commit -m "chore: update docker-compose for multi-user (remove hardcoded capital)"
```

---

## Task 14: Final Test Suite Run + Version Bump

**Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: Bump version**

In `stock_checker/__init__.py`: change `__version__` from `"0.5.0"` to `"0.6.0"`.

**Step 3: Final commit**

```bash
git add stock_checker/__init__.py
git commit -m "chore: bump version to 0.6.0 (multi-user + multi-currency)"
```

**Step 4: Push**

```bash
git push origin main
```
