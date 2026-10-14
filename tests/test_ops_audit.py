"""Offline tests for Ops audit-before-act (xang1234 #613/#628)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from datetime import datetime, timedelta, timezone

from stock_checker.ops_audit import (
    OPS_PENDING_REFUSE_SECONDS,
    append_ops_action,
    audited_ops_action,
    format_last_ops_action_bit,
    last_ops_action,
    load_ops_actions,
    ops_actions_path,
    ops_pending_freshness_band,
    ops_skip_reason_label,
    pending_ops_in_flight,
    record_ops_skipped,
)


def test_append_and_load_roundtrip(tmp_path: Path):
    assert append_ops_action(
        tmp_path,
        {
            "id": "a1",
            "action_id": "act-1",
            "at": "2026-10-13T12:00:00Z",
            "kind": "config",
            "outcome": "requested",
            "detail": {"ai_mode": "validate"},
        },
    )
    assert append_ops_action(
        tmp_path,
        {
            "id": "a2",
            "action_id": "act-1",
            "at": "2026-10-13T12:00:01Z",
            "kind": "config",
            "outcome": "accepted",
            "detail": {"ai_mode": "validate"},
        },
    )
    events = load_ops_actions(tmp_path)
    assert len(events) == 2
    assert events[0]["outcome"] == "requested"
    assert events[1]["outcome"] == "accepted"
    assert ops_actions_path(tmp_path).is_file()
    last = last_ops_action(tmp_path, kind="config")
    assert last is not None
    assert last["outcome"] == "accepted"
    bit = format_last_ops_action_bit(last)
    assert "last config · accepted ·" in bit


def test_audited_blocks_when_request_write_fails(tmp_path: Path):
    called = {"n": 0}

    def act():
        called["n"] += 1
        return {"ok": True}

    with patch(
        "stock_checker.ops_audit.append_ops_action",
        return_value=False,
    ):
        result, meta = audited_ops_action(
            tmp_path,
            kind="config",
            detail={"rs_gate": False},
            act=act,
        )
    assert result is None
    assert meta["blocked"] is True
    assert meta["reason"] == "audit_request_failed"
    assert called["n"] == 0


def test_audited_writes_request_then_accepted(tmp_path: Path):
    result, meta = audited_ops_action(
        tmp_path,
        kind="config",
        detail={"promote_experiment_strategy": False},
        act=lambda: {"saved": True},
    )
    assert result == {"saved": True}
    assert meta["blocked"] is False
    assert meta["outcome"] == "accepted"
    assert meta["outcome_recorded"] is True
    events = load_ops_actions(tmp_path)
    assert [e["outcome"] for e in events] == ["requested", "accepted"]
    assert events[0]["action_id"] == events[1]["action_id"] == meta["action_id"]


def test_audited_records_error_and_reraises(tmp_path: Path):
    def boom():
        raise RuntimeError("disk full mid-save")

    with pytest.raises(RuntimeError, match="disk full"):
        audited_ops_action(
            tmp_path,
            kind="config",
            detail={"ai_mode": "off"},
            act=boom,
        )
    events = load_ops_actions(tmp_path)
    assert [e["outcome"] for e in events] == ["requested", "error"]
    assert events[0]["action_id"] == events[1]["action_id"]


def test_safe_detail_strips_secret_keys(tmp_path: Path):
    _, meta = audited_ops_action(
        tmp_path,
        kind="config",
        detail={"ai_mode": "off", "api_key": "should-not-land", "token": "x"},
        act=lambda: True,
    )
    assert meta["blocked"] is False
    events = load_ops_actions(tmp_path)
    detail = events[0].get("detail") or {}
    assert "api_key" not in detail
    assert "token" not in detail
    assert detail.get("ai_mode") == "off"


def test_malformed_ops_actions_file_fail_open(tmp_path: Path):
    path = ops_actions_path(tmp_path)
    path.write_text("[1,2,3]\n", encoding="utf-8")
    assert load_ops_actions(tmp_path) == []
    path.write_text('{"events": null}\n', encoding="utf-8")
    assert load_ops_actions(tmp_path) == []


def test_format_last_ops_action_bit_pending_for_hanging_requested():
    now = datetime(2026, 10, 13, 20, 0, 30, tzinfo=timezone.utc)
    bit = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "requested",
            "at": "2026-10-13T20:00:00Z",
        },
        now=now,
    )
    assert bit == "last config · pending · 2026-10-13T20:00:00Z"
    assert "requested" not in bit
    assert "stale" not in bit
    accepted = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "accepted",
            "at": "2026-10-13T20:00:01Z",
        },
        now=now,
    )
    assert accepted == "last config · accepted · 2026-10-13T20:00:01Z"


def test_format_last_ops_action_bit_stale_pending_for_aged_hanging():
    """Aged crash leftover ≠ in-flight pending (xang1234 + RyanJHamby age triad)."""
    now = datetime(2026, 10, 13, 21, 5, 0, tzinfo=timezone.utc)
    stamp = now - timedelta(seconds=OPS_PENDING_REFUSE_SECONDS + 5)
    row = {
        "kind": "config",
        "outcome": "requested",
        "at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    assert ops_pending_freshness_band(row, now=now) == "stale"
    bit = format_last_ops_action_bit(row, now=now)
    assert bit == f"last config · stale pending · {row['at']}"
    assert "requested" not in bit
    # Unparseable stamp stays plain pending (fail-open; do not invent stale).
    plain = format_last_ops_action_bit(
        {"kind": "config", "outcome": "requested", "at": "not-a-time"},
        now=now,
    )
    assert plain == "last config · pending · not-a-time"
    assert ops_pending_freshness_band(
        {"kind": "config", "outcome": "requested", "at": "not-a-time"},
        now=now,
    ) is None


def test_audited_refuses_fresh_pending_in_flight(tmp_path: Path):
    """xang1234 #606/#613: double-click / overlapping Save while requested hangs."""
    now = datetime(2026, 10, 13, 21, 0, 0, tzinfo=timezone.utc)
    assert append_ops_action(
        tmp_path,
        {
            "id": "hang-1",
            "action_id": "act-hang",
            "at": "2026-10-13T20:59:30Z",
            "kind": "config",
            "outcome": "requested",
            "detail": {},
        },
    )
    assert pending_ops_in_flight(tmp_path, kind="config", now=now) is not None
    called = {"n": 0}

    def act():
        called["n"] += 1
        return {"ok": True}

    with patch(
        "stock_checker.ops_audit.pending_ops_in_flight",
        return_value={
            "action_id": "act-hang",
            "at": "2026-10-13T20:59:30Z",
            "outcome": "requested",
        },
    ):
        result, meta = audited_ops_action(
            tmp_path,
            kind="config",
            detail={"ai_mode": "off"},
            act=act,
        )
    assert result is None
    assert meta["blocked"] is True
    assert meta["reason"] == "pending_in_flight"
    assert meta["action_id"] == "act-hang"
    assert called["n"] == 0
    # No new audit row from the refused call.
    assert [e["id"] for e in load_ops_actions(tmp_path)] == ["hang-1"]


def test_record_ops_skipped_speaks_on_glance(tmp_path: Path):
    """No-op refuse leaves a skipped row (not requested/accepted)."""
    assert record_ops_skipped(
        tmp_path, kind="config", reason="no-op", detail={"ai_mode": "validate"}
    )
    last = last_ops_action(tmp_path, kind="config")
    assert last is not None
    assert last["outcome"] == "skipped"
    assert last.get("reason") == "no-op"
    assert ops_skip_reason_label(last) == "no-op"
    bit = format_last_ops_action_bit(last)
    assert "last config · skipped · no-op ·" in bit
    events = load_ops_actions(tmp_path)
    assert len(events) == 1
    assert events[0]["outcome"] == "skipped"


def test_format_last_ops_action_bit_skipped_says_why():
    """xang1234 #599/#623: bare skipped hid intentional no-op vs other preflight."""
    bit = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "skipped",
            "reason": "no_change",
            "at": "2026-10-14T01:00:00Z",
        }
    )
    assert bit == "last config · skipped · no-op · 2026-10-14T01:00:00Z"
    # Legacy rows without reason stay bare skipped (fail-open; do not invent why).
    bare = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "skipped",
            "at": "2026-10-14T01:00:00Z",
        }
    )
    assert bare == "last config · skipped · 2026-10-14T01:00:00Z"
    assert "no-op" not in bare
    assert ops_skip_reason_label({"outcome": "accepted", "reason": "no-op"}) == ""


def test_aged_pending_does_not_block_forever(tmp_path: Path):
    now = datetime(2026, 10, 13, 21, 5, 0, tzinfo=timezone.utc)
    stamp = now - timedelta(seconds=OPS_PENDING_REFUSE_SECONDS + 5)
    assert append_ops_action(
        tmp_path,
        {
            "id": "stale-hang",
            "action_id": "act-old",
            "at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": "config",
            "outcome": "requested",
            "detail": {},
        },
    )
    assert pending_ops_in_flight(tmp_path, kind="config", now=now) is None
    result, meta = audited_ops_action(
        tmp_path,
        kind="config",
        detail={"ai_mode": "validate"},
        act=lambda: {"saved": True},
    )
    assert result == {"saved": True}
    assert meta["blocked"] is False
    assert [e["outcome"] for e in load_ops_actions(tmp_path)][-2:] == [
        "requested",
        "accepted",
    ]
