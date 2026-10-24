#!/usr/bin/env python3
"""
Module: DataPersistence (SQLite backend)
Version: 2.0.0
Iteration: v1
Developer: Kent Benson
UV Environment: uv sync && uv run python

SQLite-backed persistence layer for ai-stock-checker.
Replaces flat-file storage with relational database while preserving
backward compatibility with existing callers.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DataPersistence:
    """Handle persistent storage of portfolio, trades, and findings using SQLite."""

    def __init__(self, data_dir: str = os.getenv("DATA_DIR", "/data")):
        """
        Initialize persistence layer with SQLite backend.

        Args:
            data_dir: Directory to store database file (default: /data for container volume)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "stockchecker.db"

        # Initialize database schema
        self._init_db()

    def _init_db(self):
        """Initialize database schema with all required tables."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                email       TEXT UNIQUE NOT NULL,
                pw_hash     TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                is_active   INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Portfolios table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
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
            )
        """)

        # Holdings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                portfolio_id  INTEGER NOT NULL REFERENCES portfolios(id),
                symbol        TEXT NOT NULL,
                quantity      REAL NOT NULL,
                avg_buy_price REAL NOT NULL,
                PRIMARY KEY (portfolio_id, symbol)
            )
        """)

        # Trades table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
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
            )
        """)

        # Findings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS findings (
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
            )
        """)

        # Position times table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS position_times (
                portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
                symbol       TEXT NOT NULL,
                entry_time   REAL,
                exit_time    REAL,
                PRIMARY KEY (portfolio_id, symbol)
            )
        """)

        # Scanner state table (key-value store)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scanner_state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Scanned symbols table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scanned_symbols (
                symbol        TEXT PRIMARY KEY,
                source        TEXT NOT NULL,
                first_scanned TEXT NOT NULL,
                last_scanned  TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    # ========================================================================
    # USER MANAGEMENT (new multi-user methods)
    # ========================================================================

    def create_user(self, username: str, email: str, pw_hash: str) -> int:
        """
        Create a new user.

        Args:
            username: Unique username
            email: Unique email
            pw_hash: Password hash (bcrypt recommended)

        Returns:
            User ID
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO users (username, email, pw_hash) VALUES (?, ?, ?)",
            (username, email, pw_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        Get user by username.

        Returns:
            Dict with id, username, email, pw_hash, is_active or None
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, username, email, pw_hash, is_active FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    # ========================================================================
    # PORTFOLIO MANAGEMENT (new multi-user methods + backward compat)
    # ========================================================================

    def create_portfolio(
        self,
        user_id: int,
        name: str,
        currency: str,
        initial_cash: float,
        fee_preset: str
    ) -> int:
        """
        Create a new portfolio for a user.

        Args:
            user_id: User ID
            name: Portfolio name
            currency: Currency code (EUR, USD, CAD, etc.)
            initial_cash: Starting cash
            fee_preset: Fee preset name

        Returns:
            Portfolio ID
        """
        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO portfolios
            (user_id, name, currency, initial_cash, cash, fee_preset)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, currency, initial_cash, initial_cash, fee_preset)
        )
        portfolio_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return portfolio_id

    def list_portfolios(self, user_id: int) -> List[Dict]:
        """
        List all portfolios for a user.

        Returns:
            List of portfolio dicts with metadata
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT id, user_id, name, currency, initial_cash, cash,
                   commission_rate, commission_min, fee_preset,
                   free_legs_month, free_legs_used, free_legs_per_month,
                   total_fees_paid, is_active, created_at, updated_at
            FROM portfolios
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        ).fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def list_active_portfolios(self) -> List[Dict]:
        """
        List all active portfolios (for trader loop).

        Returns:
            List of active portfolio dicts
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT id, user_id, name, currency, initial_cash, cash,
                   commission_rate, commission_min, fee_preset,
                   free_legs_month, free_legs_used, free_legs_per_month,
                   total_fees_paid, is_active, created_at, updated_at
            FROM portfolios
            WHERE is_active = 1
            ORDER BY id
            """,
        ).fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_portfolio_meta(self, portfolio_id: int) -> Optional[Dict]:
        """
        Get portfolio metadata without holdings.

        Returns:
            Portfolio dict or None if not found
        """
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT id, user_id, name, currency, initial_cash, cash,
                   commission_rate, commission_min, fee_preset,
                   free_legs_month, free_legs_used, free_legs_per_month,
                   total_fees_paid, is_active, created_at, updated_at
            FROM portfolios
            WHERE id = ?
            """,
            (portfolio_id,)
        ).fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def save_portfolio(self, portfolio_data: Dict, *, portfolio_id: int = 1):
        """
        Save portfolio state (backward compatible).

        Args:
            portfolio_data: Portfolio dict with cash, holdings, fees, etc.
            portfolio_id: Portfolio ID (default 1 for backward compat)
        """
        conn = self._get_conn()

        # Update portfolio metadata
        conn.execute(
            """
            UPDATE portfolios
            SET cash = ?,
                commission_rate = ?,
                commission_min = ?,
                fee_preset = ?,
                free_legs_month = ?,
                free_legs_used = ?,
                free_legs_per_month = ?,
                total_fees_paid = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                portfolio_data.get("cash", 0.0),
                portfolio_data.get("commission_rate", 0.0025),
                portfolio_data.get("commission_min", 1.0),
                portfolio_data.get("fee_preset", "revolut_standard"),
                portfolio_data.get("fee_allowance_month", ""),
                portfolio_data.get("fee_allowance_used", 0),
                portfolio_data.get("free_legs_per_month", 1),
                portfolio_data.get("total_fees_paid", 0.0),
                portfolio_id
            )
        )

        # Clear existing holdings
        conn.execute("DELETE FROM holdings WHERE portfolio_id = ?", (portfolio_id,))

        # Insert new holdings
        holdings = portfolio_data.get("holdings", {})
        avg_buy_prices = portfolio_data.get("avg_buy_price", {})

        for symbol, quantity in holdings.items():
            if quantity > 0:  # Only save non-zero holdings
                avg_price = avg_buy_prices.get(symbol, 0.0)
                conn.execute(
                    """
                    INSERT INTO holdings (portfolio_id, symbol, quantity, avg_buy_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (portfolio_id, symbol, quantity, avg_price)
                )

        conn.commit()
        conn.close()

    def load_portfolio(self, *, portfolio_id: int = 1) -> Optional[Dict]:
        """
        Load portfolio state (backward compatible).

        Args:
            portfolio_id: Portfolio ID (default 1 for backward compat)

        Returns:
            Portfolio dict in legacy format or None if not found
        """
        conn = self._get_conn()

        # Load portfolio metadata
        row = conn.execute(
            """
            SELECT initial_cash, cash, commission_rate, commission_min,
                   fee_preset, free_legs_month, free_legs_used,
                   free_legs_per_month, total_fees_paid, currency, updated_at
            FROM portfolios
            WHERE id = ?
            """,
            (portfolio_id,)
        ).fetchone()

        if not row:
            conn.close()
            return None

        # Load holdings
        holdings_rows = conn.execute(
            "SELECT symbol, quantity, avg_buy_price FROM holdings WHERE portfolio_id = ?",
            (portfolio_id,)
        ).fetchall()

        conn.close()

        # Build legacy format
        holdings = {}
        avg_buy_price = {}

        for h_row in holdings_rows:
            symbol = h_row["symbol"]
            holdings[symbol] = h_row["quantity"]
            avg_buy_price[symbol] = h_row["avg_buy_price"]

        return {
            "initial_cash": row["initial_cash"],
            "cash": row["cash"],
            "commission_rate": row["commission_rate"],
            "commission_min": row["commission_min"],
            "fee_preset": row["fee_preset"],
            "holdings": holdings,
            "avg_buy_price": avg_buy_price,
            "total_fees_paid": row["total_fees_paid"],
            "fee_allowance_month": row["free_legs_month"],
            "fee_allowance_used": row["free_legs_used"],
            "free_legs_per_month": row["free_legs_per_month"],
            "currency": row["currency"],
            "last_updated": row["updated_at"]
        }

    # ========================================================================
    # TRADES (backward compatible with portfolio_id kwarg)
    # ========================================================================

    def append_trade(self, trade: Dict, *, portfolio_id: int = 1):
        """
        Append a trade to the trades log.

        Args:
            trade: Trade dict
            portfolio_id: Portfolio ID (default 1 for backward compat)
        """
        timestamp = trade.get("timestamp", datetime.now().isoformat())
        trade_type = trade["type"]

        # Map legacy field names to database schema
        # BUY trades have total_cost, SELL trades have net_proceeds
        if trade_type == "BUY":
            net_amount = trade.get("total_cost", 0.0)
        else:  # SELL
            net_amount = trade.get("net_proceeds", 0.0)

        # Extract context fields (strategy, note, score, confidence, source, exit_reason)
        context_fields = {}
        for key in ["strategy", "note", "score", "confidence", "source", "exit_reason"]:
            if key in trade:
                context_fields[key] = trade[key]

        context_json = json.dumps(context_fields) if context_fields else None

        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO trades
            (portfolio_id, timestamp, type, symbol, quantity, price,
             cost, proceeds, commission, net_amount, buy_price,
             profit_loss, profit_loss_pct, cash_after, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                portfolio_id,
                timestamp,
                trade_type,
                trade["symbol"],
                trade["quantity"],
                trade["price"],
                trade.get("cost"),
                trade.get("proceeds"),
                trade.get("commission", 0.0),
                net_amount,
                trade.get("buy_price"),
                trade.get("profit_loss"),
                trade.get("profit_loss_pct"),
                trade.get("cash_remaining", 0.0),
                context_json
            )
        )
        conn.commit()
        conn.close()

    def load_trades(self, limit: Optional[int] = None, *, portfolio_id: int = 1) -> List[Dict]:
        """
        Load trades from database.

        Args:
            limit: Optional limit (returns last N trades)
            portfolio_id: Portfolio ID (default 1 for backward compat)

        Returns:
            List of trade dicts in legacy format
        """
        conn = self._get_conn()

        query = """
            SELECT timestamp, type, symbol, quantity, price, cost, proceeds,
                   commission, net_amount, buy_price, profit_loss, profit_loss_pct,
                   cash_after, context_json
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY id
        """

        if limit:
            # SQLite doesn't support LIMIT with offset for "last N", so we fetch all and slice
            query += f" DESC LIMIT {limit}"
            rows = conn.execute(query, (portfolio_id,)).fetchall()
            rows = list(reversed(rows))  # Reverse to get chronological order
        else:
            rows = conn.execute(query, (portfolio_id,)).fetchall()

        conn.close()

        # Reconstruct legacy format
        trades = []
        for row in rows:
            trade = {
                "timestamp": row["timestamp"],
                "type": row["type"],
                "symbol": row["symbol"],
                "quantity": row["quantity"],
                "price": row["price"],
                "commission": row["commission"],
                "cash_remaining": row["cash_after"]
            }

            # Add type-specific fields
            if row["type"] == "BUY":
                trade["cost"] = row["cost"]
                trade["total_cost"] = row["net_amount"]
            else:  # SELL
                trade["proceeds"] = row["proceeds"]
                trade["net_proceeds"] = row["net_amount"]
                trade["buy_price"] = row["buy_price"]
                trade["profit_loss"] = row["profit_loss"]
                trade["profit_loss_pct"] = row["profit_loss_pct"]

            # Add context fields
            if row["context_json"]:
                context = json.loads(row["context_json"])
                trade.update(context)

            trades.append(trade)

        return trades

    # ========================================================================
    # FINDINGS (backward compatible with portfolio_id kwarg)
    # ========================================================================

    def append_finding(self, finding: Dict, *, portfolio_id: Optional[int] = None):
        """
        Append a market finding/signal.

        Args:
            finding: Finding dict
            portfolio_id: Optional portfolio ID
        """
        timestamp = finding.get("timestamp", datetime.now().isoformat())
        reasons_json = json.dumps(finding.get("reasons", []))

        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO findings
            (portfolio_id, timestamp, symbol, action, confidence, score,
             price, reasons_json, executed, ai_validated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                portfolio_id,
                timestamp,
                finding["symbol"],
                finding["action"],
                finding.get("confidence"),
                finding.get("score"),
                finding.get("price"),
                reasons_json,
                1 if finding.get("executed", False) else 0,
                1 if finding.get("ai_validated", False) else 0
            )
        )
        conn.commit()
        conn.close()

    def load_findings(
        self,
        limit: Optional[int] = None,
        symbol: Optional[str] = None,
        action: Optional[str] = None,
        *,
        portfolio_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Load findings with optional filters.

        Args:
            limit: Optional limit (returns last N)
            symbol: Optional symbol filter
            action: Optional action filter (BUY/SELL)
            portfolio_id: Optional portfolio ID filter

        Returns:
            List of finding dicts
        """
        conn = self._get_conn()

        # Build query with filters
        query = """
            SELECT timestamp, symbol, action, confidence, score, price,
                   reasons_json, executed, ai_validated
            FROM findings
            WHERE 1=1
        """
        params = []

        if portfolio_id is not None:
            query += " AND portfolio_id = ?"
            params.append(portfolio_id)

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if action:
            query += " AND action = ?"
            params.append(action)

        query += " ORDER BY id"

        if limit:
            query += f" DESC LIMIT {limit}"
            rows = conn.execute(query, params).fetchall()
            rows = list(reversed(rows))
        else:
            rows = conn.execute(query, params).fetchall()

        conn.close()

        # Reconstruct format
        findings = []
        for row in rows:
            finding = {
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "action": row["action"],
                "confidence": row["confidence"],
                "score": row["score"],
                "price": row["price"],
                "reasons": json.loads(row["reasons_json"]),
                "executed": bool(row["executed"]),
                "ai_validated": bool(row["ai_validated"])
            }
            findings.append(finding)

        return findings

    # ========================================================================
    # SCANNER STATE (global, no portfolio_id)
    # ========================================================================

    def save_state(self, state: Dict):
        """Save general application state as key-value pairs."""
        conn = self._get_conn()

        # Clear existing state
        conn.execute("DELETE FROM scanner_state")

        # Insert new state
        for key, value in state.items():
            if key != "last_updated":  # Skip metadata
                conn.execute(
                    "INSERT INTO scanner_state (key, value) VALUES (?, ?)",
                    (key, json.dumps(value))
                )

        conn.commit()
        conn.close()

    def load_state(self) -> Optional[Dict]:
        """Load application state."""
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM scanner_state").fetchall()
        conn.close()

        if not rows:
            return None

        state = {}
        for row in rows:
            state[row["key"]] = json.loads(row["value"])

        state["last_updated"] = datetime.now().isoformat()
        return state

    # ========================================================================
    # POSITION TIMES (backward compatible with portfolio_id kwarg)
    # ========================================================================

    def save_entry_times(self, entry_times: Dict[str, float], *, portfolio_id: int = 1):
        """Save position entry times."""
        conn = self._get_conn()

        for symbol, timestamp in entry_times.items():
            # UPSERT: update if exists, insert if not
            conn.execute(
                """
                INSERT INTO position_times (portfolio_id, symbol, entry_time)
                VALUES (?, ?, ?)
                ON CONFLICT(portfolio_id, symbol)
                DO UPDATE SET entry_time = excluded.entry_time
                """,
                (portfolio_id, symbol, timestamp)
            )

        conn.commit()
        conn.close()

    def load_entry_times(self, *, portfolio_id: int = 1) -> Dict[str, float]:
        """Load position entry times."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT symbol, entry_time
            FROM position_times
            WHERE portfolio_id = ? AND entry_time IS NOT NULL
            """,
            (portfolio_id,)
        ).fetchall()
        conn.close()

        return {row["symbol"]: row["entry_time"] for row in rows}

    def save_exit_times(self, exit_times: Dict[str, float], *, portfolio_id: int = 1):
        """Save last exit timestamps (anti rebuy cooldown)."""
        conn = self._get_conn()

        for symbol, timestamp in exit_times.items():
            # UPSERT: update if exists, insert if not
            conn.execute(
                """
                INSERT INTO position_times (portfolio_id, symbol, exit_time)
                VALUES (?, ?, ?)
                ON CONFLICT(portfolio_id, symbol)
                DO UPDATE SET exit_time = excluded.exit_time
                """,
                (portfolio_id, symbol, timestamp)
            )

        conn.commit()
        conn.close()

    def load_exit_times(self, *, portfolio_id: int = 1) -> Dict[str, float]:
        """Load last exit timestamps."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT symbol, exit_time
            FROM position_times
            WHERE portfolio_id = ? AND exit_time IS NOT NULL
            """,
            (portfolio_id,)
        ).fetchall()
        conn.close()

        return {row["symbol"]: row["exit_time"] for row in rows}

    # ========================================================================
    # SCANNED SYMBOLS (global, no portfolio_id)
    # ========================================================================

    def track_scanned_symbol(self, symbol: str, source: str):
        """
        Track a scanned symbol with its source.

        Args:
            symbol: Symbol like 'BTC-USD' or 'AAPL'
            source: 'crypto' or 'paper'
        """
        now = datetime.now().isoformat()
        conn = self._get_conn()

        # UPSERT: update last_scanned if exists, insert if not
        conn.execute(
            """
            INSERT INTO scanned_symbols (symbol, source, first_scanned, last_scanned)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol)
            DO UPDATE SET last_scanned = excluded.last_scanned
            """,
            (symbol, source, now, now)
        )

        conn.commit()
        conn.close()

    def track_scanned_symbols_batch(self, symbols: List[str], source: str):
        """
        Track multiple symbols at once (more efficient for batch scans).

        Args:
            symbols: List of symbols
            source: 'crypto' or 'paper'
        """
        now = datetime.now().isoformat()
        conn = self._get_conn()

        for symbol in symbols:
            conn.execute(
                """
                INSERT INTO scanned_symbols (symbol, source, first_scanned, last_scanned)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol)
                DO UPDATE SET last_scanned = excluded.last_scanned
                """,
                (symbol, source, now, now)
            )

        conn.commit()
        conn.close()

    def load_scanned_symbols(self) -> Dict[str, Dict]:
        """
        Load all scanned symbols with their source information.

        Returns:
            Dict mapping symbol -> {
                "source": "crypto" | "paper",
                "last_scanned": "2025-11-30T15:00:00",
                "first_scanned": "2025-11-30T10:00:00"
            }
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT symbol, source, first_scanned, last_scanned FROM scanned_symbols"
        ).fetchall()
        conn.close()

        result = {}
        for row in rows:
            result[row["symbol"]] = {
                "source": row["source"],
                "first_scanned": row["first_scanned"],
                "last_scanned": row["last_scanned"]
            }

        return result

    def get_symbol_source(self, symbol: str) -> Optional[str]:
        """
        Get the source (crypto/paper) for a symbol.

        Returns:
            'crypto', 'paper', or None if not found
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT source FROM scanned_symbols WHERE symbol = ?",
            (symbol,)
        ).fetchone()
        conn.close()

        return row["source"] if row else None

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def get_summary(self) -> Dict:
        """Get a summary of all stored data."""
        conn = self._get_conn()

        trade_count = conn.execute("SELECT COUNT(*) as cnt FROM trades").fetchone()["cnt"]
        finding_count = conn.execute("SELECT COUNT(*) as cnt FROM findings").fetchone()["cnt"]
        portfolio_count = conn.execute("SELECT COUNT(*) as cnt FROM portfolios").fetchone()["cnt"]
        user_count = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]

        conn.close()

        return {
            "data_directory": str(self.data_dir),
            "database_file": str(self.db_path),
            "total_trades": trade_count,
            "total_findings": finding_count,
            "total_portfolios": portfolio_count,
            "total_users": user_count,
        }

    def export_csv(self, output_dir: Optional[str] = None):
        """Export data to CSV files for analysis."""
        import csv

        output_dir = Path(output_dir or self.data_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        conn = self._get_conn()

        # Export trades
        trades_rows = conn.execute(
            """
            SELECT timestamp, type, symbol, quantity, price, commission,
                   net_amount, cash_after
            FROM trades
            ORDER BY id
            """
        ).fetchall()

        if trades_rows:
            trades_csv = output_dir / "trades.csv"
            with open(trades_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=trades_rows[0].keys())
                writer.writeheader()
                writer.writerows([dict(row) for row in trades_rows])

        # Export findings
        findings_rows = conn.execute(
            """
            SELECT timestamp, symbol, action, confidence, score, price,
                   reasons_json, executed, ai_validated
            FROM findings
            ORDER BY id
            """
        ).fetchall()

        if findings_rows:
            findings_csv = output_dir / "findings.csv"
            with open(findings_csv, "w", newline="") as f:
                flattened = []
                for row in findings_rows:
                    flat = dict(row)
                    # Flatten reasons JSON
                    reasons = json.loads(flat["reasons_json"])
                    flat["reasons"] = "; ".join(reasons) if reasons else ""
                    del flat["reasons_json"]
                    flattened.append(flat)

                writer = csv.DictWriter(f, fieldnames=flattened[0].keys())
                writer.writeheader()
                writer.writerows(flattened)

        conn.close()

        return {
            "trades_csv": str(output_dir / "trades.csv") if trades_rows else None,
            "findings_csv": str(output_dir / "findings.csv") if findings_rows else None,
        }
