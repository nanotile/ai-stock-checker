"""Offline tests for Ops audit-before-act (xang1234 #613/#628)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from stock_checker.ops_audit import (
    append_ops_action,
    audited_ops_action,
    format_last_ops_action_bit,
    last_ops_action,
    load_ops_actions,
    ops_actions_path,
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
    bit = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "requested",
            "at": "2026-10-13T20:00:00Z",
        }
    )
    assert bit == "last config · pending · 2026-10-13T20:00:00Z"
    assert "requested" not in bit
    accepted = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "accepted",
            "at": "2026-10-13T20:00:01Z",
        }
    )
    assert accepted == "last config · accepted · 2026-10-13T20:00:01Z"
