# Multi-User Multi-Currency Design — SQLite Shim

**Date:** 2026-10-24
**Approach:** SQLite Shim (minimal-change persistence swap)
**Author:** Kent Benson + Claude Code

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data store | SQLite (stdlib) | No new infrastructure, WAL mode handles 2-5 concurrent users |
| Trader loop | Shared scanner, per-user portfolios | One scan cycle, each portfolio decides independently |
| Canadian universe | Curated TSX tickers (.TO suffix) | Follows german_universe.py pattern |
| Auth | JWT via cloudflarekb-add-login skill | Dashboard-only auth gate |
| User scale | 2-5 pre-configured accounts | No self-registration |
| FX conversion | None in v1 | Each portfolio trades assets priced in its own currency |

---

## Option Analysis (retained for reference)

### Option 1: SQLite Shim (CHOSEN)

**Summary:** Replace flat-file DataPersistence with SQLite. Add user/portfolio tables. Portfolio class gains a currency field. Trader iterates over active portfolios. Auth is thin middleware.

**Strengths:**
- Lowest risk — buy/sell/fee logic barely changes, just parameterized
- Migration path clear: existing portfolio.json becomes one SQLite row
- SQLite is stdlib — no new infrastructure
- Currency is a portfolio attribute, not system-wide

**Weaknesses:**
- Some legacy field names may linger in old serialized trade records
- SQLite concurrent writes need WAL mode
- No FX conversion — mixed-currency display is face-value only
- EUR→currency-neutral rename is tedious but mechanical

**Effort:** Medium

### Option 2: Domain-First Rebuild (runner-up)

**Summary:** Redesign core domain model with User, Portfolio, Currency as first-class entities. Repository layer, orchestrator pattern.

**Strengths:** Clean domain model, future extensibility, testable
**Weaknesses:** Higher risk, more code, rewrites battle-tested Portfolio class
**Effort:** High
**When to reconsider:** If shimming a third major feature on top of Option 1

### Option 3: Micro Split (rejected)

**Summary:** Separate auth/portfolio/scanner into independent services.
**Rejected because:** Massively over-engineered for 2-5 users on one VM. 3x operational burden.

---

## 1. Database Schema

File: `data/stockchecker.db` (SQLite, WAL mode)

```sql
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    pw_hash     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE portfolios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    name            TEXT NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'EUR',
    initial_cash    REAL NOT NULL DEFAULT 100000.0,
    cash            REAL NOT NULL DEFAULT 100000.0,
    commission_rate REAL NOT NULL DEFAULT 0.0025,
    commission_min  REAL NOT NULL DEFAULT 1.0,
    fee_preset      TEXT NOT NULL DEFAULT 'revolut_standard',
    free_legs_month TEXT NOT NULL DEFAULT '',
    free_legs_used  INTEGER NOT NULL DEFAULT 0,
    free_legs_per_month INTEGER NOT NULL DEFAULT 1,
    total_fees_paid REAL NOT NULL DEFAULT 0.0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE holdings (
    portfolio_id  INTEGER NOT NULL REFERENCES portfolios(id),
    symbol        TEXT NOT NULL,
    quantity      REAL NOT NULL,
    avg_buy_price REAL NOT NULL,
    PRIMARY KEY (portfolio_id, symbol)
);

CREATE TABLE trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
    timestamp    TEXT NOT NULL,
    type         TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    quantity     REAL NOT NULL,
    price        REAL NOT NULL,
    cost         REAL,
    proceeds     REAL,
    commission   REAL NOT NULL,
    net_amount   REAL NOT NULL,
    buy_price    REAL,
    profit_loss  REAL,
    profit_loss_pct REAL,
    cash_after   REAL NOT NULL,
    context_json TEXT
);

CREATE TABLE findings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER,
    timestamp    TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    action       TEXT NOT NULL,
    confidence   TEXT,
    score        REAL,
    price        REAL,
    reasons_json TEXT,
    executed     INTEGER DEFAULT 0,
    ai_validated INTEGER DEFAULT 0
);

CREATE TABLE position_times (
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
    symbol       TEXT NOT NULL,
    entry_time   REAL,
    exit_time    REAL,
    PRIMARY KEY (portfolio_id, symbol)
);

CREATE TABLE scanner_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

**Design notes:**
- Holdings normalized into own table (not JSON blob) for cross-user queries
- Trades use `context_json` TEXT for variable strategy/note/score fields
- `commission_min` is currency-neutral — denominated in portfolio's currency
- Fee allowance state lives on portfolio row directly
- Scanner findings: NULL portfolio_id = shared scanner output

---

## 2. Currency Module

New file: `stock_checker/currency.py`

```python
SUPPORTED_CURRENCIES = ("EUR", "USD", "CAD")

CURRENCY_SYMBOL = {
    "EUR": "€",
    "USD": "$",
    "CAD": "C$",
}

CURRENCY_EXCHANGES = {
    "EUR": ["XETR"],
    "USD": ["US"],
    "CAD": ["TSX"],
}

CURRENCY_FEE_MINIMUMS = {
    "EUR": {"revolut_standard": 1.0, "revolut_plus": 1.0,
            "revolut_ultra": 1.0, "binance_like": 0.0},
    "USD": {"revolut_standard": 1.0, "revolut_plus": 1.0,
            "revolut_ultra": 1.0, "binance_like": 0.0},
    "CAD": {"revolut_standard": 1.5, "revolut_plus": 1.5,
            "revolut_ultra": 1.5, "binance_like": 0.0},
}
```

**Integration points:**
- `fees.py` — `rates_for_preset(preset, currency="EUR")` gains currency param
- `fee_burn.py` — uses `CURRENCY_SYMBOL[currency]` instead of hardcoded `€`
- `stock_universe_manager.py` — `exchanges_for_currency(currency)` filters scanner results
- `openbb_backend/main.py` — all `€` formatting uses `CURRENCY_SYMBOL[portfolio.currency]`

**Scope boundary:** No FX conversion in v1. Each portfolio trades assets priced in its own currency. Crypto (BTC-USD, ETH-USD) available to all currencies at face value.

---

## 3. Canadian Universe + Market Hours

### canadian_universe.py

New file: `stock_checker/canadian_universe.py`
Pattern: identical to `german_universe.py`

~40 curated TSX/S&P TSX 60 names:

```python
CANADIAN_TSX_SEED: dict[str, dict[str, str]] = {
    "RY.TO":   {"sector": "banking",     "exchange": "TSX"},
    "TD.TO":   {"sector": "banking",     "exchange": "TSX"},
    "BNS.TO":  {"sector": "banking",     "exchange": "TSX"},
    "BMO.TO":  {"sector": "banking",     "exchange": "TSX"},
    "CM.TO":   {"sector": "banking",     "exchange": "TSX"},
    "NA.TO":   {"sector": "banking",     "exchange": "TSX"},
    "ENB.TO":  {"sector": "energy",      "exchange": "TSX"},
    "CNQ.TO":  {"sector": "energy",      "exchange": "TSX"},
    "SU.TO":   {"sector": "energy",      "exchange": "TSX"},
    "TRP.TO":  {"sector": "energy",      "exchange": "TSX"},
    "CVE.TO":  {"sector": "energy",      "exchange": "TSX"},
    "IMO.TO":  {"sector": "energy",      "exchange": "TSX"},
    "CNR.TO":  {"sector": "transport",   "exchange": "TSX"},
    "CP.TO":   {"sector": "transport",   "exchange": "TSX"},
    "SHOP.TO": {"sector": "technology",  "exchange": "TSX"},
    "CSU.TO":  {"sector": "technology",  "exchange": "TSX"},
    "OTEX.TO": {"sector": "technology",  "exchange": "TSX"},
    "MFC.TO":  {"sector": "insurance",   "exchange": "TSX"},
    "SLF.TO":  {"sector": "insurance",   "exchange": "TSX"},
    "GWO.TO":  {"sector": "insurance",   "exchange": "TSX"},
    "IFC.TO":  {"sector": "insurance",   "exchange": "TSX"},
    "BCE.TO":  {"sector": "telecom",     "exchange": "TSX"},
    "T.TO":    {"sector": "telecom",     "exchange": "TSX"},
    "RCI-B.TO":{"sector": "telecom",     "exchange": "TSX"},
    "ABX.TO":  {"sector": "mining",      "exchange": "TSX"},
    "FNV.TO":  {"sector": "mining",      "exchange": "TSX"},
    "WPM.TO":  {"sector": "mining",      "exchange": "TSX"},
    "NTR.TO":  {"sector": "materials",   "exchange": "TSX"},
    "CCL-B.TO":{"sector": "materials",   "exchange": "TSX"},
    "L.TO":    {"sector": "grocery",     "exchange": "TSX"},
    "ATD.TO":  {"sector": "retail",      "exchange": "TSX"},
    "DOL.TO":  {"sector": "retail",      "exchange": "TSX"},
    "BAM.TO":  {"sector": "asset_mgmt",  "exchange": "TSX"},
    "BN.TO":   {"sector": "asset_mgmt",  "exchange": "TSX"},
    "FFH.TO":  {"sector": "insurance",   "exchange": "TSX"},
    "WCN.TO":  {"sector": "industrial",  "exchange": "TSX"},
    "TRI.TO":  {"sector": "technology",  "exchange": "TSX"},
    "QSR.TO":  {"sector": "restaurant",  "exchange": "TSX"},
    "GIB-A.TO":{"sector": "technology",  "exchange": "TSX"},
}
```

### Market Hours Changes

File: `stock_checker/market_hours.py`

Add TSX session constants and detection:

```python
# TSX hours — same wall-clock as US but different exchange holidays
TSX_OPEN  = dt_time(9, 30)
TSX_CLOSE = dt_time(16, 0)
TSX_TZ    = "US/Eastern"    # Toronto is Eastern time
```

Add `is_canadian_equity(symbol)` — checks `.TO` suffix.

Extend `is_equity_session_closed(symbol)`:
- `.TO` suffix → TSX session check
- `.DE` suffix → Xetra session check (existing)
- else → US session check (existing)

Note: TSX and US share the same hours (9:30-16:00 ET) but have different holiday calendars. For v1, we don't model holidays (same as current Xetra behavior).

### stock_universe_manager.py Changes

- Add TSX to venue detection: `.TO` suffix → `"TSX"`
- Add `_TSX_VENUE_EXCHANGES = {"TSX", "XTSE", "TO", "TORONTO"}`
- `listing_venue()` extended with TSX check before US fallback
- New function `exchanges_for_currency(currency: str) -> list[str]` — returns exchanges from `CURRENCY_EXCHANGES`
- Seed universe loader includes `CANADIAN_TSX_SEED` alongside existing US and German seeds

---

## 4. Persistence Layer — SQLite Backend

File: `stock_checker/persistence.py` (modified in-place)

**Strategy:** The existing `DataPersistence` class interface is preserved but the implementation switches from flat JSON files to SQLite. This minimizes changes in all calling code (Portfolio, IntelligentTrader, desk API).

**Key changes:**
- Constructor: `__init__(data_dir)` now opens/creates `data_dir/stockchecker.db` with WAL mode
- Schema auto-created on first run (CREATE TABLE IF NOT EXISTS)
- `save_portfolio(data, portfolio_id)` — UPSERTs into portfolios + holdings tables
- `load_portfolio(portfolio_id)` — returns same Dict shape as today (for Portfolio class compatibility)
- `append_trade(trade, portfolio_id)` — INSERTs into trades table
- `load_trades(portfolio_id, limit)` — SELECTs from trades table
- `append_finding(finding, portfolio_id)` — INSERTs into findings table
- `load_findings(portfolio_id, limit, symbol, action)` — SELECTs with filters
- `save_entry_times(times, portfolio_id)` / `load_entry_times(portfolio_id)` — uses position_times table
- `save_exit_times(times, portfolio_id)` / `load_exit_times(portfolio_id)` — uses position_times table
- `save_state(state)` / `load_state()` — uses scanner_state key-value table

**New methods for multi-user:**
- `create_user(username, email, pw_hash) -> int` — returns user ID
- `get_user_by_username(username) -> dict | None`
- `create_portfolio(user_id, name, currency, initial_cash, fee_preset) -> int` — returns portfolio ID
- `list_portfolios(user_id) -> list[dict]` — all portfolios for a user
- `list_active_portfolios() -> list[dict]` — all active portfolios (for trader loop)
- `get_portfolio_meta(portfolio_id) -> dict` — portfolio row without holdings

**Connection management:**
- Single `sqlite3.Connection` per `DataPersistence` instance
- WAL mode enabled at connection time: `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000` for concurrent access from trader + desk

**Backward compatibility:**
- The old flat-file methods still work if called without portfolio_id (default to portfolio 1)
- A migration function converts existing `data/portfolio.json` + `data/trades.jsonl` into SQLite rows on first startup
- If the trader starts with zero users/portfolios in the DB (fresh install, no legacy files), it logs a warning and sleeps until at least one active portfolio exists. It does not create a default portfolio automatically — users must be provisioned via the CLI script first.

---

## 5. Auth Integration

Skill: `cloudflarekb-add-login`

**What it provides:**
- JWT middleware for FastAPI
- Login endpoint (`POST /auth/login`)
- Token verification dependency
- Password hashing (bcrypt)

**Integration into openbb_backend/main.py:**
- Login page served at `/desk/login` (HTML form)
- `POST /desk/auth/login` — validates credentials, returns JWT cookie
- All `/desk/*` routes require valid JWT (FastAPI dependency)
- JWT payload includes `user_id` and `username`
- `/desk/api/*` endpoints extract `user_id` from JWT to scope portfolio access

**User provisioning:**
- No self-registration
- CLI script `stock_checker/create_user.py` to add users:
  `python -m stock_checker.create_user --username kent --email kent@example.com --password <pw>`
- Passwords stored as bcrypt hashes in users table

**Session management:**
- JWT stored as HTTP-only cookie (not localStorage)
- Token expiry: 24 hours
- Logout: clear cookie client-side

---

## 6. Portfolio & Fee Changes

### portfolio.py

- Constructor gains `currency: str = "EUR"` and `portfolio_id: int = 0`
- `commission_min_eur` renamed to `commission_min` throughout
- `_save_state()` includes `currency` and `portfolio_id` in persisted dict
- `buy()` / `sell()` unchanged in logic — they operate on raw numbers, currency is just metadata
- `get_summary()` unchanged — caller formats with correct currency symbol

### fees.py

- Constants renamed:
  - `REVOLUT_STANDARD_MIN_EUR` → `REVOLUT_STANDARD_MIN`
  - `REVOLUT_ULTRA_MIN_EUR` → `REVOLUT_ULTRA_MIN`
  - `BINANCE_LIKE_MIN_EUR` → `BINANCE_LIKE_MIN`
- `FEE_PRESETS` dict: `commission_min_eur` key → `commission_min`
- `FEE_PRESETS` labels: `€1 min` → currency-neutral or parameterized
- `rates_for_preset(preset, currency="EUR")` — looks up min from `CURRENCY_FEE_MINIMUMS` if currency differs from EUR
- `calc_commission(notional, *, rate, min_amount)` — param renamed from `min_eur`
- `FeeAllowanceLedger.commission_for_leg()` — `min_eur` param renamed to `min_amount`

### fee_burn.py

- `CURRENCY_SYMBOL[currency]` replaces hardcoded `€` in warning string
- Currency passed as parameter from caller (trader or desk)

### trader_config.py

- Schema gains `"currency"` field (default `"EUR"`, validated against `SUPPORTED_CURRENCIES`)
- `"commission_min_eur"` key renamed to `"commission_min"` in config dict
- Hot-reload respects new field names

---

## 7. Trader Loop Changes

### intelligent_trader.py

**Current:** Single Portfolio instance, single scan cycle, single set of entry/exit decisions.

**New:** On each cycle:
1. Load all active portfolios from SQLite via `persistence.list_active_portfolios()`
2. Run scanner once (shared — all exchanges scanned)
3. For each active portfolio:
   a. Filter opportunities to symbols matching the portfolio's currency exchanges
   b. Run entry/exit decision logic against that portfolio's state
   c. Execute trades against that portfolio
   d. Persist via `persistence.save_portfolio(data, portfolio_id)`

**Implementation approach:**
- `IntelligentTrader.__init__()` loads all active portfolios into a dict `{portfolio_id: Portfolio}`
- The main loop in `run_one_cycle()` is wrapped: scan once, then iterate portfolios
- Each portfolio carries its own `DataPersistence` reference scoped to its `portfolio_id`
- Portfolio list refreshed every N cycles (e.g., every 10 scan cycles) to pick up newly created portfolios

**Concurrency:** Sequential per-portfolio within the same process. No threading. For 2-5 portfolios this adds negligible latency.

---

## 8. Desk UI Changes

### openbb_backend/main.py

**Login flow:**
- `/desk` redirects to `/desk/login` if no valid JWT cookie
- `/desk/login` — login page (username + password form)
- `POST /desk/auth/login` — authenticate, set JWT cookie, redirect to `/desk`
- `/desk/logout` — clear cookie, redirect to login

**Portfolio selector:**
- Dropdown in desk header showing user's portfolios (name + currency)
- Selected portfolio stored in cookie or URL query param (`?portfolio=3`)
- All dashboard data (positions, trades, P&L, fees) scoped to selected portfolio
- Currency symbol in all monetary displays pulled from selected portfolio's currency

**Portfolio management:**
- "New Portfolio" form: name, currency (dropdown: EUR/USD/CAD), initial cash, fee preset
- Portfolio rename/delete (soft delete via is_active=0)

**Dynamic currency formatting:**
- All `€` in HTML/markdown templates replaced with `{symbol}` variable
- `symbol` resolved from `CURRENCY_SYMBOL[portfolio.currency]`
- Fee preset labels rendered with correct currency symbol

---

## 9. Migration

**On first startup with SQLite:**
1. Check if `data/stockchecker.db` exists
2. If not, create schema
3. Check if `data/portfolio.json` exists (legacy data)
4. If yes, create default user (from env or config), create portfolio from JSON data, import trades from `data/trades.jsonl`, import findings, entry/exit times
5. Rename legacy files to `data/portfolio.json.migrated` etc. (not deleted)
6. Log migration summary

**Migration is automatic and one-time.** The trader loop and desk API both check for the migration on startup.

**Rollback:** Legacy files are renamed, not deleted. To rollback, rename them back and switch `DataPersistence` back to the flat-file implementation.

---

## 10. File Change Summary

### New files
| File | Purpose |
|------|---------|
| `stock_checker/currency.py` | Currency enum, symbol map, fee tables, exchange mapping |
| `stock_checker/canadian_universe.py` | ~40 curated TSX tickers |
| `stock_checker/create_user.py` | CLI script to provision users |
| `stock_checker/migrate_to_sqlite.py` | One-time migration from flat files |

### Modified files
| File | Changes |
|------|---------|
| `stock_checker/persistence.py` | SQLite backend, new multi-user methods |
| `stock_checker/portfolio.py` | `currency` param, rename `commission_min_eur` → `commission_min` |
| `stock_checker/fees.py` | Rename EUR constants, currency-parameterized `rates_for_preset()` |
| `stock_checker/fee_burn.py` | Dynamic currency symbol |
| `stock_checker/trader_config.py` | `currency` field in schema, rename `commission_min_eur` |
| `stock_checker/intelligent_trader.py` | Multi-portfolio loop |
| `stock_checker/market_hours.py` | TSX session, `is_canadian_equity()` |
| `stock_checker/stock_universe_manager.py` | TSX venue, `exchanges_for_currency()`, Canadian seed |
| `stock_checker/listed_funds.py` | Canadian ETF seeds (optional) |
| `openbb_backend/main.py` | Auth middleware, portfolio selector, dynamic currency display |
| `openbb_backend/symbol_names.py` | Canadian stock name mappings |
| `docker-compose.yml` | Remove hardcoded `--capital`, add user provisioning env vars |

### Unchanged (no modifications needed)
| File | Why unchanged |
|------|---------------|
| `stock_checker/risk_manager.py` | Operates on raw numbers, currency-agnostic |
| `stock_checker/market_scanner.py` | Scanner is currency-agnostic, scans all exchanges |
| `stock_checker/entry_gates.py` | Gate logic is price-ratio based, not currency-dependent |
| `stock_checker/exit_policy.py` | Same — thresholds are percentages |
| `stock_checker/market_regime.py` | Benchmark-relative, currency-agnostic |

---

## 11. Known Limitations (v1)

1. **No FX conversion** — crypto priced in USD shown at face value in EUR/CAD portfolios
2. **No holiday calendars** — TSX/US/Xetra holidays not modeled (weekends only)
3. **No per-portfolio custom universes** — each currency gets its default universe
4. **No portfolio sharing** — portfolios are strictly user-scoped
5. **Sequential portfolio processing** — trader loop handles portfolios one at a time
6. **CAD fee minimums are estimated** — Revolut CAD trading fees may differ; adjust in currency.py as needed
