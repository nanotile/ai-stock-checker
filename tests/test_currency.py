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
