"""Offline tests for Ops audit-before-act (xang1234 #613/#628)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from stock_checker.ops_audit import (
    OPS_OUTCOME_AGING_HOURS,
    OPS_OUTCOME_FRESH_HOURS,
    OPS_PENDING_REFUSE_SECONDS,
    append_ops_action,
    audited_ops_action,
    format_last_ops_action_bit,
    last_ops_action,
    load_ops_actions,
    ops_actions_path,
    ops_error_reason_from_exc,
    ops_error_reason_label,
    ops_file_freshness_band,
    ops_outcome_age_band,
    ops_outcome_age_line,
    ops_outcome_vs_file_clash,
    ops_pending_freshness_band,
    ops_pending_no_outcome,
    ops_skip_reason_label,
    pending_ops_in_flight,
    record_ops_skipped,
    trader_config_mtime_utc,
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
    assert bit.startswith("last config · accepted ·")
    assert "fresh" in bit or "aging" in bit or "stale" in bit
    assert "T" not in bit.split(" · ")[-1]  # age band, not raw ISO


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
    # xang1234 #621: compact why persists (message text stays out of the row).
    assert events[1].get("reason") == "act-fail"
    assert "disk" not in json.dumps(events[1])
    bit = format_last_ops_action_bit(events[1])
    assert bit.startswith("last config · error · act-fail ·")
    assert "fresh" in bit or "aging" in bit or "stale" in bit


def test_ops_error_reason_from_exc_families():
    assert ops_error_reason_from_exc(OSError("EIO")) == "write-fail"
    assert ops_error_reason_from_exc(PermissionError("denied")) == "write-fail"
    assert ops_error_reason_from_exc(ValueError("bad")) == "bad-value"
    assert ops_error_reason_from_exc(TypeError("bad")) == "bad-value"
    assert ops_error_reason_from_exc(KeyError("k")) == "bad-value"
    assert ops_error_reason_from_exc(RuntimeError("x")) == "act-fail"


def test_format_last_ops_action_bit_accepted_speaks_changed_impact():
    """xang1234 #636: bare accepted hid which knobs the Save moved."""
    from stock_checker.ops_audit import (
        ops_changed_impact_bit,
        ops_changed_impact_warn,
        ops_changed_session_bit,
    )

    now = datetime(2026, 10, 15, 6, 0, 0, tzinfo=timezone.utc)
    row = {
        "kind": "config",
        "outcome": "accepted",
        "at": "2026-10-15T05:00:00Z",
        "detail": {"changed": ["ai_mode", "min_hold_hours"], "ai_mode": "off"},
    }
    assert ops_changed_impact_bit(row) == "Δ hot · AI · hold"
    assert ops_changed_impact_warn(row) is True
    bit = format_last_ops_action_bit(row, now=now)
    assert bit.startswith("last config · accepted · Δ hot · AI · hold ·")
    assert "1h fresh" in bit
    # Mid-session after hot Δ when open_cash was recorded at Save time.
    mid_row = {
        "kind": "config",
        "outcome": "accepted",
        "at": "2026-10-15T05:00:00Z",
        "detail": {
            "changed": ["min_hold_hours"],
            "open_cash": ["US", "Xetra"],
        },
    }
    assert ops_changed_session_bit(mid_row) == (
        "mid session · US · Xetra open · all cash · vs 0 closed · thin · 0%"
    )
    mid_bit = format_last_ops_action_bit(mid_row, now=now)
    assert (
        "Δ hot · hold · mid session · US · Xetra open · all cash · "
        "vs 0 closed · thin · 0% ·" in mid_bit
    )
    half_row = {
        "kind": "config",
        "outcome": "accepted",
        "at": "2026-10-15T05:00:00Z",
        "detail": {
            "changed": ["min_hold_hours"],
            "open_cash": ["US"],
        },
    }
    assert ops_changed_session_bit(half_row) == (
        "mid session · US open · half cash · vs 1 closed · 50%"
    )
    quiet = {
        "kind": "config",
        "outcome": "accepted",
        "at": "2026-10-15T05:00:00Z",
        "detail": {
            "changed": ["ai_mode"],
            "ai_mode": "off",
            "open_cash": ["US"],  # quiet Save ignores mid-session
        },
    }
    assert ops_changed_impact_bit(quiet) == "Δ quiet · AI"
    assert ops_changed_impact_warn(quiet) is False
    assert ops_changed_session_bit(quiet) == ""
    # Legacy accepted without changed stays silent on Δ.
    bare = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "accepted",
            "at": "2026-10-15T05:00:00Z",
            "detail": {"ai_mode": "off"},
        },
        now=now,
    )
    assert "Δ" not in bare
    assert bare.startswith("last config · accepted ·")
    assert ops_changed_impact_warn(
        {
            "kind": "config",
            "outcome": "accepted",
            "at": "2026-10-15T05:00:00Z",
            "detail": {"ai_mode": "off"},
        }
    ) is False
    assert ops_changed_impact_warn(None) is False


def test_safe_detail_keeps_changed_key_list(tmp_path: Path):
    """xang1234 #636: persist detail.changed for glance Δ after reload."""
    _, meta = audited_ops_action(
        tmp_path,
        kind="config",
        detail={"ai_mode": "off", "changed": ["ai_mode", "rs_gate"]},
        act=lambda: {"ok": True},
    )
    assert meta["blocked"] is False
    events = load_ops_actions(tmp_path)
    accepted = [e for e in events if e.get("outcome") == "accepted"][-1]
    assert accepted["detail"]["changed"] == ["ai_mode", "rs_gate"]
    bit = format_last_ops_action_bit(accepted)
    assert "Δ quiet · AI · RS" in bit


def test_format_last_ops_action_bit_error_says_why():
    """xang1234 #621: bare error hid write-fail vs act-fail after reload."""
    now = datetime(2026, 10, 14, 5, 0, 0, tzinfo=timezone.utc)
    bit = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "error",
            "reason": "write_fail",
            "at": "2026-10-14T04:00:00Z",
        },
        now=now,
    )
    assert bit == "last config · error · write-fail · 1h fresh"
    assert ops_error_reason_label(
        {"outcome": "error", "reason": "write_fail"}
    ) == "write-fail"
    # Legacy rows without reason stay bare error (fail-open; do not invent why).
    bare = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "error",
            "at": "2026-10-14T04:00:00Z",
        },
        now=now,
    )
    assert bare == "last config · error · 1h fresh"
    assert "write-fail" not in bare
    assert ops_error_reason_label({"outcome": "accepted", "reason": "act-fail"}) == ""


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
    assert bit == "last config · pending · 30s fresh"
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
    assert accepted == "last config · accepted · 29s fresh"


def test_ops_outcome_age_line_fresh_aging_stale():
    """RyanJHamby/xang1234 + saved-row parity: ISO alone hid Save recency."""
    now = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    assert ops_outcome_age_line(
        {"at": (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        now=now,
    ) == "3h fresh"
    assert OPS_OUTCOME_FRESH_HOURS == 24
    aging_stamp = now - timedelta(hours=OPS_OUTCOME_FRESH_HOURS + 2)
    assert ops_outcome_age_line(
        {"at": aging_stamp.strftime("%Y-%m-%dT%H:%M:%SZ")},
        now=now,
    ) == "26h aging"
    stale_stamp = now - timedelta(hours=OPS_OUTCOME_AGING_HOURS + 24)
    assert ops_outcome_age_line(
        {"at": stale_stamp.strftime("%Y-%m-%dT%H:%M:%SZ")},
        now=now,
    ) == "8d stale"
    assert ops_outcome_age_line({"at": "not-a-time"}, now=now) == ""
    assert (
        format_last_ops_action_bit(
            {
                "kind": "config",
                "outcome": "accepted",
                "at": stale_stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            now=now,
        )
        == "last config · accepted · 8d stale"
    )


def test_ops_outcome_vs_file_clash_when_bands_disagree():
    """Audit age alone hid stamp ≠ Ops file mtime across freshness bands."""
    from stock_checker.ops_audit import ops_outcome_vs_file_warn

    now = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    accepted = {
        "kind": "config",
        "outcome": "accepted",
        "at": (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    assert ops_outcome_age_band(accepted, now=now) == "fresh"
    # Same band → agree (speak-both-sides; silent match hid confirm).
    same = now - timedelta(hours=2)
    assert ops_file_freshness_band(same, now=now) == "fresh"
    assert (
        ops_outcome_vs_file_clash(accepted, config_mtime=same, now=now)
        == "agree · file fresh"
    )
    assert not ops_outcome_vs_file_warn("agree · file fresh")
    assert (
        format_last_ops_action_bit(accepted, now=now, config_mtime=same)
        == "last config · accepted · 3h fresh · agree · file fresh"
    )
    # File stale while audit fresh → dual-clock clash + … + share Δ + share vs Δ align.
    stale_file = now - timedelta(hours=OPS_OUTCOME_AGING_HOURS + 24)
    assert ops_file_freshness_band(stale_file, now=now) == "stale"
    # 3h vs 8d → audit ~2% · file ~98% · share Δ −96pp · age Δ wide ≡ share Δ wide → align.
    assert (
        ops_outcome_vs_file_clash(accepted, config_mtime=stale_file, now=now)
        == "clash · audit fresh · file stale · audit newer · wide · sides · 3h · 8d · sides Δ wide · 7d · audit 2% · file 98% · sides share Δ wide · -96pp · sides share vs Δ align · wide"
    )
    assert ops_outcome_vs_file_warn(
        "clash · audit fresh · file stale · audit newer · wide · sides · 3h · 8d · sides Δ wide · 7d · audit 2% · file 98% · sides share Δ wide · -96pp · sides share vs Δ align · wide"
    )
    assert (
        format_last_ops_action_bit(accepted, now=now, config_mtime=stale_file)
        == "last config · accepted · 3h fresh · clash · audit fresh · file stale · audit newer · wide · sides · 3h · 8d · sides Δ wide · 7d · audit 2% · file 98% · sides share Δ wide · -96pp · sides share vs Δ align · wide"
    )
    # Aging file vs fresh audit — thin age Δ + wide share Δ (crossed) stays silent on share vs Δ.
    aging_file = now - timedelta(hours=OPS_OUTCOME_FRESH_HOURS + 2)
    assert ops_file_freshness_band(aging_file, now=now) == "aging"
    # 3h vs 26h → audit ~10% · file ~90% · share Δ −80pp; age thin ≠ share wide.
    assert (
        ops_outcome_vs_file_clash(accepted, config_mtime=aging_file, now=now)
        == "clash · audit fresh · file aging · audit newer · thin · sides · 3h · 26h · sides Δ thin · 23h · audit 10% · file 90% · sides share Δ wide · -80pp"
    )
    assert ops_outcome_vs_file_warn(
        "clash · audit fresh · file aging · audit newer · thin · sides · 3h · 26h · sides Δ thin · 23h · audit 10% · file 90% · sides share Δ wide · -80pp"
    )
    assert (
        format_last_ops_action_bit(accepted, now=now, config_mtime=aging_file)
        == "last config · accepted · 3h fresh · clash · audit fresh · file aging · audit newer · thin · sides · 3h · 26h · sides Δ thin · 23h · audit 10% · file 90% · sides share Δ wide · -80pp"
    )
    # Mid age-|Δ| (24h..7d) keeps sides + share + share Δ — no sides Δ; share vs Δ clash × mid.
    mid_file = now - timedelta(hours=OPS_OUTCOME_FRESH_HOURS + 48)
    assert ops_file_freshness_band(mid_file, now=now) == "aging"
    # 3h vs 3d (72h) → audit 4% · file 96% · share Δ −92pp · age mid · share wide → clash.
    assert (
        ops_outcome_vs_file_clash(accepted, config_mtime=mid_file, now=now)
        == "clash · audit fresh · file aging · audit newer · thin · sides · 3h · 3d · audit 4% · file 96% · sides share Δ wide · -92pp · sides share vs Δ clash · × mid · % wide"
    )
    # Near-equal ages across adjacent bands → thin share Δ + thin age Δ → align.
    near_equal_audit = {
        "kind": "config",
        "outcome": "accepted",
        "at": (now - timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    near_equal_file = now - timedelta(hours=25)
    assert ops_outcome_age_band(near_equal_audit, now=now) == "fresh"
    assert ops_file_freshness_band(near_equal_file, now=now) == "aging"
    # 23h vs 25h → audit 48% · file 52% · share Δ -4pp thin; age Δ thin · 2h → align.
    assert (
        ops_outcome_vs_file_clash(
            near_equal_audit, config_mtime=near_equal_file, now=now
        )
        == "clash · audit fresh · file aging · audit newer · thin · sides · 23h · 25h · sides Δ thin · 2h · audit 48% · file 52% · sides share Δ thin · -4pp · sides share vs Δ align · thin"
    )
    # Mid share-|Δ| (10..20pp) keeps share — no share Δ; age thin → clash × thin · % mid.
    mid_share_audit = {
        "kind": "config",
        "outcome": "accepted",
        "at": (now - timedelta(hours=22)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    mid_share_file = now - timedelta(hours=28)
    assert ops_outcome_age_band(mid_share_audit, now=now) == "fresh"
    assert ops_file_freshness_band(mid_share_file, now=now) == "aging"
    # 22h vs 28h → audit 44% · file 56% · |Δ|=12pp mid silent; age Δ thin · 6h.
    assert (
        ops_outcome_vs_file_clash(
            mid_share_audit, config_mtime=mid_share_file, now=now
        )
        == "clash · audit fresh · file aging · audit newer · thin · sides · 22h · 28h · sides Δ thin · 6h · audit 44% · file 56% · sides share vs Δ clash · × thin · % mid"
    )
    # File fresh while audit stale → file newer · wide + … + share Δ + share vs Δ align.
    stale_stamp_early = now - timedelta(hours=OPS_OUTCOME_AGING_HOURS + 24)
    stale_vs_fresh = {
        "kind": "config",
        "outcome": "accepted",
        "at": stale_stamp_early.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    fresh_file = now - timedelta(hours=2)
    assert ops_outcome_age_band(stale_vs_fresh, now=now) == "stale"
    assert ops_file_freshness_band(fresh_file, now=now) == "fresh"
    assert (
        ops_outcome_vs_file_clash(
            stale_vs_fresh, config_mtime=fresh_file, now=now
        )
        == "clash · audit stale · file fresh · file newer · wide · sides · 8d · 2h · sides Δ wide · 7d · audit 99% · file 1% · sides share Δ wide · +98pp · sides share vs Δ align · wide"
    )
    assert ops_outcome_vs_file_warn(
        "clash · audit stale · file fresh · file newer · wide · sides · 8d · 2h · sides Δ wide · 7d · audit 99% · file 1% · sides share Δ wide · +98pp · sides share vs Δ align · wide"
    )
    # Dual-stale agree warns (stale confirm ≠ quiet); aging agree stays calm.
    stale_stamp = now - timedelta(hours=OPS_OUTCOME_AGING_HOURS + 24)
    stale_accepted = {
        "kind": "config",
        "outcome": "accepted",
        "at": stale_stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    assert ops_outcome_age_band(stale_accepted, now=now) == "stale"
    assert (
        ops_outcome_vs_file_clash(stale_accepted, config_mtime=stale_file, now=now)
        == "agree · file stale"
    )
    assert ops_outcome_vs_file_warn("agree · file stale")
    assert not ops_outcome_vs_file_warn("agree · file aging")
    assert not ops_outcome_vs_file_warn("agree · file fresh")
    assert (
        format_last_ops_action_bit(
            stale_accepted, now=now, config_mtime=stale_file
        )
        == "last config · accepted · 8d stale · agree · file stale"
    )
    # Hanging requested never speaks file clash (refuse / no-outcome cover it).
    pending = {
        "kind": "config",
        "outcome": "requested",
        "at": (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    assert ops_outcome_vs_file_clash(pending, config_mtime=stale_file, now=now) == ""
    assert (
        format_last_ops_action_bit(pending, now=now, config_mtime=stale_file)
        == "last config · pending · 30s fresh"
    )
    # Missing mtime / unparseable stay silent (fail-open).
    assert ops_outcome_vs_file_clash(accepted, config_mtime=None, now=now) == ""
    assert ops_file_freshness_band(None, now=now) == ""


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
    # Refuse-window stale ≠ wall-clock stale (2m is still fresh on the 24h scale).
    assert bit == "last config · stale pending · 2m fresh"
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
    assert bit.startswith("last config · skipped · no-op ·")
    assert "fresh" in bit or "aging" in bit or "stale" in bit
    events = load_ops_actions(tmp_path)
    assert len(events) == 1
    assert events[0]["outcome"] == "skipped"


def test_format_last_ops_action_bit_skipped_says_why():
    """xang1234 #599/#623: bare skipped hid intentional no-op vs other preflight."""
    now = datetime(2026, 10, 14, 2, 0, 0, tzinfo=timezone.utc)
    bit = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "skipped",
            "reason": "no_change",
            "at": "2026-10-14T01:00:00Z",
        },
        now=now,
    )
    assert bit == "last config · skipped · no-op · 1h fresh"
    # Legacy rows without reason stay bare skipped (fail-open; do not invent why).
    bare = format_last_ops_action_bit(
        {
            "kind": "config",
            "outcome": "skipped",
            "at": "2026-10-14T01:00:00Z",
        },
        now=now,
    )
    assert bare == "last config · skipped · 1h fresh"
    assert "no-op" not in bare
    assert ops_skip_reason_label({"outcome": "accepted", "reason": "no-op"}) == ""


def test_format_last_ops_action_bit_pending_no_outcome_when_file_newer():
    """xang1234 #630: hanging request + newer Ops file ≠ wait forever for accepted."""
    now = datetime(2026, 10, 14, 3, 0, 0, tzinfo=timezone.utc)
    stamp = now - timedelta(seconds=OPS_PENDING_REFUSE_SECONDS + 30)
    row = {
        "kind": "config",
        "outcome": "requested",
        "at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    newer = stamp + timedelta(seconds=5)
    older = stamp - timedelta(seconds=5)
    same_second = stamp + timedelta(milliseconds=800)
    assert ops_pending_no_outcome(row, config_mtime=newer) is True
    assert ops_pending_no_outcome(row, config_mtime=older) is False
    assert ops_pending_no_outcome(row, config_mtime=None) is False
    # Fractional mtime in the same second must not count as newer.
    assert ops_pending_no_outcome(row, config_mtime=same_second) is False
    bit = format_last_ops_action_bit(row, now=now, config_mtime=newer)
    # 150s → 2m wall age; refuse-window stale; no outcome when file newer.
    assert bit == "last config · stale pending · no outcome · 2m fresh"
    # Older / missing file stays bare stale pending (fail-open; do not invent orphan).
    bare = format_last_ops_action_bit(row, now=now, config_mtime=older)
    assert bare == "last config · stale pending · 2m fresh"
    assert "no outcome" not in bare
    # Fresh in-flight with file already newer still speaks (outcome writer dead mid-flight).
    fresh_stamp = now - timedelta(seconds=30)
    fresh_row = {
        "kind": "config",
        "outcome": "requested",
        "at": fresh_stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    fresh_bit = format_last_ops_action_bit(
        fresh_row, now=now, config_mtime=fresh_stamp + timedelta(seconds=1)
    )
    assert fresh_bit == "last config · pending · no outcome · 30s fresh"


def test_trader_config_mtime_utc_roundtrip(tmp_path: Path):
    from stock_checker.trader_config import config_path

    assert trader_config_mtime_utc(tmp_path) is None
    path = config_path(tmp_path)
    path.write_text('{"ai_mode": "off"}\n', encoding="utf-8")
    mtime = trader_config_mtime_utc(tmp_path)
    assert mtime is not None
    assert mtime.tzinfo is not None


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


def test_fresh_pending_no_outcome_does_not_block_save(tmp_path: Path):
    """xang1234 #630: hanging request + newer Ops file must not brick Save.

    Speak still shows pending · no outcome; refuse window fail-opens so friends
    can retry without waiting for an accepted stamp that will not arrive.
    """
    from stock_checker.trader_config import config_path

    now = datetime(2026, 10, 14, 4, 0, 0, tzinfo=timezone.utc)
    stamp = now - timedelta(seconds=30)
    assert append_ops_action(
        tmp_path,
        {
            "id": "orphan-1",
            "action_id": "act-orphan",
            "at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": "config",
            "outcome": "requested",
            "detail": {},
        },
    )
    path = config_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"ai_mode": "off"}\n', encoding="utf-8")
    # File mtime must be at least one full second after the hanging request
    # (second-precision compare in ops_pending_no_outcome).
    newer = stamp.timestamp() + 2
    os.utime(path, (newer, newer))
    assert ops_pending_no_outcome(
        last_ops_action(tmp_path, kind="config"),
        config_mtime=trader_config_mtime_utc(tmp_path),
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
