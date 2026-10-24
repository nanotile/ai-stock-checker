"""CLI to create pre-configured user accounts.

Usage:
    python -m stock_checker.create_user --username kent --email kent@example.com --password <pw>
    python -m stock_checker.create_user --username kent --email kent@example.com --password <pw> \
        --portfolio-name "EUR Book" --currency EUR --initial-cash 100000
"""

from __future__ import annotations

import argparse
import os
import sys

import bcrypt

from stock_checker.persistence import DataPersistence


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a user account for the stock checker desk."
    )
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument(
        "--data-dir",
        default=os.getenv("DATA_DIR", "data"),
        help="Data directory (default: $DATA_DIR or 'data')",
    )
    parser.add_argument("--portfolio-name", help="Create a portfolio with this name")
    parser.add_argument(
        "--currency",
        default="EUR",
        choices=["EUR", "USD", "CAD"],
        help="Portfolio currency (default: EUR)",
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=100000.0,
        help="Portfolio initial cash (default: 100000)",
    )
    parser.add_argument(
        "--fee-preset",
        default="revolut_standard",
        help="Fee preset (default: revolut_standard)",
    )

    args = parser.parse_args(argv)

    persistence = DataPersistence(data_dir=args.data_dir)

    # Check if user already exists
    existing = persistence.get_user_by_username(args.username)
    if existing:
        print(f"Error: User '{args.username}' already exists (id={existing['id']})")
        return 1

    # Create user
    pw_hash = hash_password(args.password)
    user_id = persistence.create_user(args.username, args.email, pw_hash)
    print(f"Created user '{args.username}' (id={user_id})")

    # Optionally create portfolio
    if args.portfolio_name:
        portfolio_id = persistence.create_portfolio(
            user_id,
            args.portfolio_name,
            args.currency,
            args.initial_cash,
            args.fee_preset,
        )
        print(
            f"Created portfolio '{args.portfolio_name}' "
            f"(id={portfolio_id}, currency={args.currency}, "
            f"cash={args.initial_cash:,.2f})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
