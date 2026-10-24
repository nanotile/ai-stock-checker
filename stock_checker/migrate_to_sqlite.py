"""One-time migration from flat JSON files to SQLite.

Reads legacy flat files (portfolio.json, trades.jsonl, findings.jsonl,
entry_times.json, exit_times.json) and imports them into the SQLite database.
Legacy files are renamed to .migrated (not deleted) for rollback safety.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from stock_checker.persistence import DataPersistence


def migrate_if_needed(
    data_dir: str = os.getenv("DATA_DIR", "/data"),
    *,
    default_username: str = "admin",
    default_email: str = "admin@localhost",
    default_pw_hash: str = "placeholder_change_me",
    default_currency: str = "EUR",
) -> dict[str, Any]:
    """Migrate legacy flat files to SQLite if they exist.

    Returns a dict with migration status:
        {"migrated": bool, "portfolio_id": int | None, "details": str}
    """
    data_path = Path(data_dir)
    portfolio_file = data_path / "portfolio.json"
    trades_file = data_path / "trades.jsonl"
    findings_file = data_path / "findings.jsonl"
    entry_times_file = data_path / "entry_times.json"
    exit_times_file = data_path / "exit_times.json"

    # Nothing to migrate if no legacy portfolio file
    if not portfolio_file.exists():
        return {"migrated": False, "portfolio_id": None, "details": "No legacy files found"}

    persistence = DataPersistence(data_dir=data_dir)

    # Check if migration already happened (user exists)
    existing = persistence.get_user_by_username(default_username)
    if existing:
        return {"migrated": False, "portfolio_id": None, "details": "Already migrated (user exists)"}

    # Read legacy portfolio
    try:
        portfolio_data = json.loads(portfolio_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {"migrated": False, "portfolio_id": None, "details": f"Failed to read portfolio.json: {e}"}

    # Create default user
    user_id = persistence.create_user(default_username, default_email, default_pw_hash)

    # Create portfolio from legacy data
    initial_cash = float(portfolio_data.get("initial_cash", 100000.0))
    fee_preset = str(portfolio_data.get("fee_preset", "revolut_standard"))
    portfolio_id = persistence.create_portfolio(
        user_id, "Migrated Portfolio", default_currency, initial_cash, fee_preset
    )

    # Save portfolio state (holdings, cash, fees, etc.)
    # Rename commission_min_eur to commission_min if present (legacy key)
    if "commission_min_eur" in portfolio_data and "commission_min" not in portfolio_data:
        portfolio_data["commission_min"] = portfolio_data.pop("commission_min_eur")

    persistence.save_portfolio(portfolio_data, portfolio_id=portfolio_id)

    # Import trades
    trade_count = 0
    if trades_file.exists():
        try:
            with open(trades_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        trade = json.loads(line)
                        persistence.append_trade(trade, portfolio_id=portfolio_id)
                        trade_count += 1
        except (json.JSONDecodeError, OSError):
            pass  # Best-effort import

    # Import findings
    finding_count = 0
    if findings_file.exists():
        try:
            with open(findings_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        finding = json.loads(line)
                        persistence.append_finding(finding, portfolio_id=portfolio_id)
                        finding_count += 1
        except (json.JSONDecodeError, OSError):
            pass

    # Import entry times
    if entry_times_file.exists():
        try:
            entry_times = json.loads(entry_times_file.read_text())
            if isinstance(entry_times, dict):
                persistence.save_entry_times(entry_times, portfolio_id=portfolio_id)
        except (json.JSONDecodeError, OSError):
            pass

    # Import exit times
    if exit_times_file.exists():
        try:
            exit_times = json.loads(exit_times_file.read_text())
            if isinstance(exit_times, dict):
                persistence.save_exit_times(exit_times, portfolio_id=portfolio_id)
        except (json.JSONDecodeError, OSError):
            pass

    # Rename legacy files to .migrated
    for f in [portfolio_file, trades_file, findings_file, entry_times_file, exit_times_file]:
        if f.exists():
            migrated_path = f.with_suffix(f.suffix + ".migrated")
            f.rename(migrated_path)

    details = (
        f"Migrated: user={default_username}, portfolio_id={portfolio_id}, "
        f"{trade_count} trades, {finding_count} findings"
    )
    return {"migrated": True, "portfolio_id": portfolio_id, "details": details}


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DATA_DIR", "/data")
    result = migrate_if_needed(data_dir)
    print(f"Migration result: {result}")
