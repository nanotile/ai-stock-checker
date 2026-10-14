"""US RTH vs Xetra equity-hours honesty glance (display only)."""

from __future__ import annotations

from datetime import datetime

import pytz

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_equity_hours_glance, load_desk_snapshot


def test_equity_hours_glance_both_open_us_morning() -> None:
    # Wednesday 10:00 ET ≈ both US RTH and Xetra open (Xetra until 17:30 Berlin).
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 9, 10, 0))
    g = build_equity_hours_glance(now=now)
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["us_open"] is True
    assert g["xetra_open"] is True
    # Silent open hid confirm — speak cash open (crypto out of denom).
    assert g["line"] == "active · US · Xetra · crypto · cash open"
    assert g["cash_open"] is True
    assert g["attention_line"] == ""
    assert g["attention_all_cash"] is False
    assert g["attention_half_cash"] is False
    assert g["attention_cash_share_pct"] is None
    assert g["inactive_line"] == ""
    assert g["inactive_count"] == 0
    assert g["active_markets"] == ["US", "Xetra", "crypto"]
    assert g["inactive_markets"] == []


def test_equity_hours_glance_both_closed_weekend() -> None:
    sat = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 12, 12, 0))
    g = build_equity_hours_glance(now=sat)
    assert g["ready"] is True
    assert g["tone"] == "closed"
    assert g["us_open"] is False
    assert g["xetra_open"] is False
    # Venue names alone hid total cash dark; all cash owns the clip.
    assert g["line"] == "active · crypto · attention · US · Xetra · all cash"
    assert g["attention_line"] == "attention · US · Xetra · all cash"
    assert g["attention_all_cash"] is True
    assert g["attention_half_cash"] is False
    assert g["attention_cash_share_pct"] == 100
    assert g["cash_open"] is False
    assert g["inactive_line"] == "Inactive markets (2): US · Xetra"
    assert g["inactive_count"] == 2
    assert g["active_markets"] == ["crypto"]
    assert g["inactive_markets"] == ["US", "Xetra"]


def test_equity_hours_glance_split_xetra_only() -> None:
    # 10:00 Berlin weekday: Xetra open; US still closed (04:00 ET).
    now = pytz.timezone("Europe/Berlin").localize(datetime(2026, 9, 9, 10, 0))
    g = build_equity_hours_glance(now=now)
    assert g["ready"] is True
    assert g["tone"] == "split"
    assert g["xetra_open"] is True
    assert g["us_open"] is False
    # Bare venue hid 50% cash dark; half cash owns the clip.
    assert g["line"] == "active · Xetra · crypto · attention · US · half cash"
    assert g["attention_line"] == "attention · US · half cash"
    assert g["attention_all_cash"] is False
    assert g["attention_half_cash"] is True
    assert g["attention_cash_share_pct"] == 50
    assert g["cash_open"] is False
    assert g["inactive_line"] == "Inactive markets (1): US"
    assert g["inactive_count"] == 1
    assert g["active_markets"] == ["Xetra", "crypto"]
    assert g["inactive_markets"] == ["US"]


def test_equity_hours_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["equity_hours_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"open", "closed", "split"}
    assert g["line"].startswith("active · ")
    assert "crypto" in g["line"]
    assert "inactive_line" in g
    assert "inactive_count" in g
    assert "attention_all_cash" in g
    assert "attention_half_cash" in g
    assert "cash_open" in g


def test_equity_hours_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["equity_hours_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"open", "closed", "split"}
    assert g["line"].startswith("active · ")
    assert "crypto" in g["line"]
    assert "inactive_line" in g
    assert "attention_all_cash" in g
    assert "attention_half_cash" in g
    assert "cash_open" in g
