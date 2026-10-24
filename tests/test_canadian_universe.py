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
