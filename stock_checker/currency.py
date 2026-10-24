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
