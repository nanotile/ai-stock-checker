"""Fail-open soft-allow glance (display only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from openbb_backend.desk import build_soft_allow_glance, soft_allow_lean_meta
from stock_checker.gate_audit import (
    soft_allow_last_lead_vs_config,
    soft_allow_last_lead_vs_config_freshness,
    soft_allow_last_vs_lead,
    soft_allow_last_vs_lead_freshness,
    soft_allow_lead_vs_config,
    soft_allow_lead_vs_config_freshness,
)


def test_soft_allow_last_vs_lead_helper() -> None:
    assert soft_allow_last_vs_lead("rs", "breadth") == "last vs lead · breadth"
    assert soft_allow_last_vs_lead("rs", "RS") == "agree"
    assert soft_allow_last_vs_lead("", "breadth") == ""
    assert soft_allow_last_vs_lead("rs", "") == ""


def test_soft_allow_lead_vs_config_helper() -> None:
    """tradermonty #576 same-run: lead ring vs Ops toggle clash|agree."""
    assert soft_allow_lead_vs_config("rs", None) == ""
    assert soft_allow_lead_vs_config("rs", {}) == ""
    assert (
        soft_allow_lead_vs_config("rs", {"rs_gate": True})
        == "agree · lead rs · RS on"
    )
    assert (
        soft_allow_lead_vs_config(
            "rs", {"rs_gate": True}, lead_count=2, lead_share_pct=66.7
        )
        == "agree · lead rs · ×2 · 67% · RS on"
    )
    assert (
        soft_allow_lead_vs_config("rs", {"rs_gate": False})
        == "clash · lead rs · RS off"
    )
    assert (
        soft_allow_lead_vs_config(
            "rs", {"rs_gate": False}, lead_count=2, lead_share_pct=66.7
        )
        == "clash · lead rs · ×2 · 67% · RS off"
    )
    assert (
        soft_allow_lead_vs_config("regime", {"regime_gate": False})
        == "clash · lead regime · regime off"
    )
    assert (
        soft_allow_lead_vs_config("regime", {"regime_gate": True})
        == "agree · lead regime · regime on"
    )
    assert soft_allow_lead_vs_config("earnings", {"rs_gate": False}) == ""


def test_soft_allow_last_lead_vs_config_helper() -> None:
    """last≠lead vs lead↔Ops — share/lean meta polarity."""
    assert soft_allow_last_lead_vs_config("", "agree · lead rs · RS on") == (
        "",
        False,
    )
    assert soft_allow_last_lead_vs_config("agree · last rs · lead rs", "") == (
        "",
        False,
    )
    assert soft_allow_last_lead_vs_config(
        "agree · last rs · lead rs", "agree · lead rs · RS on"
    ) == ("last/config align · both agree", False)
    assert soft_allow_last_lead_vs_config(
        "last vs lead · breadth", "clash · lead rs · RS off"
    ) == ("last/config align · both clash", True)
    assert soft_allow_last_lead_vs_config(
        "agree · last rs · lead rs", "clash · lead rs · RS off"
    ) == ("last/config clash · last agree · config clash", True)
    assert soft_allow_last_lead_vs_config(
        "last vs lead · breadth", "agree · lead rs · RS on"
    ) == ("last/config clash · last clash · config agree", True)
    assert soft_allow_last_lead_vs_config(
        "agree · last rs · lead rs",
        "agree · lead rs · ×2 · 67% · RS on",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/config align · both agree · ×2 · 67%", False)
    assert soft_allow_last_lead_vs_config(
        "last vs lead · breadth",
        "clash · lead rs · ×2 · 67% · RS off",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/config align · both clash · ×2 · 67%", True)


def test_soft_allow_last_vs_lead_freshness_helper() -> None:
    """Gate last≠lead vs newest age — gap last/lead freshness parity."""
    assert soft_allow_last_vs_lead_freshness("", "fresh") == ("", False)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs", "aging"
    ) == ("", False)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs", "fresh"
    ) == ("last/lead align · fresh · agree", False)
    assert soft_allow_last_vs_lead_freshness(
        "last vs lead · breadth", "expired"
    ) == ("last/lead align · expired · vs breadth", False)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs", "expired"
    ) == ("last/lead clash · expired · agree", True)
    assert soft_allow_last_vs_lead_freshness(
        "last vs lead · breadth", "fresh"
    ) == ("last/lead clash · fresh · vs breadth", True)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs",
        "fresh",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/lead align · fresh · agree · ×2 · 67%", False)


def test_soft_allow_lead_vs_config_freshness_helper() -> None:
    """Lead↔Ops vs newest age — last/lead freshness parity."""
    assert soft_allow_lead_vs_config_freshness("", "fresh") == ("", False)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · RS on", "aging"
    ) == ("", False)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · RS on", "fresh"
    ) == ("lead/config align · fresh · on", False)
    assert soft_allow_lead_vs_config_freshness(
        "clash · lead rs · RS off", "expired"
    ) == ("lead/config align · expired · off", False)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · RS on", "expired"
    ) == ("lead/config clash · expired · on", True)
    assert soft_allow_lead_vs_config_freshness(
        "clash · lead rs · RS off", "fresh"
    ) == ("lead/config clash · fresh · off", True)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · ×2 · 67% · RS on",
        "expired",
        lead_count=2,
        lead_share_pct=100,
    ) == ("lead/config clash · expired · on · ×2 · 100%", True)


def test_soft_allow_last_lead_vs_config_freshness_helper() -> None:
    """Age↔gate vs age↔Ops — share/lean meta polarity."""
    assert soft_allow_last_lead_vs_config_freshness(
        "", "lead/config align · fresh · on"
    ) == ("", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree", ""
    ) == ("", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree",
        "lead/config align · fresh · on",
    ) == ("last/config age align · both align · fresh", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead clash · expired · agree",
        "lead/config clash · expired · on",
    ) == ("last/config age align · both clash · expired", True)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree",
        "lead/config clash · fresh · off",
    ) == (
        "last/config age clash · last/lead align · lead/config clash · fresh",
        True,
    )
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead clash · fresh · vs breadth",
        "lead/config align · fresh · on",
    ) == (
        "last/config age clash · last/lead clash · lead/config align · fresh",
        True,
    )
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree",
        "lead/config align · expired · on",
    ) == ("last/config age align · both align · mixed", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree · ×2 · 67%",
        "lead/config align · fresh · on · ×2 · 67%",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/config age align · both align · fresh · ×2 · 67%", False)


def test_soft_allow_lean_meta_names_spoken_sleeves() -> None:
    """Quiet chip names gen/gap sleeves; hot appends stages after clash|hot."""
    assert soft_allow_lean_meta("") == "quiet"
    # lead↔Ops toggle (tradermonty #576) — gate + on|off ride with the stage.
    assert (
        soft_allow_lean_meta("agree · lead rs · RS on")
        == "quiet · 1 fold · lead/config rs on"
    )
    assert (
        soft_allow_lean_meta("agree · lead rs · ×2 · 67% · RS on")
        == "quiet · 1 fold · lead/config rs ×2 67% on"
    )
    assert (
        soft_allow_lean_meta("clash · lead rs · ×2 · 67% · RS off", warn=True)
        == "clash · lead/config rs ×2 67% off"
    )
    assert (
        soft_allow_lean_meta("clash · lead rs · RS off", warn=True)
        == "clash · lead/config rs off"
    )
    assert (
        soft_allow_lean_meta(
            "clash · lead rs · RS off · clash · scan stale",
            warn=True,
        )
        == "clash · lead/config rs off · scan"
    )
    # Newest print vs band lead (FinRobot last≠tilt) — gate rides.
    assert (
        soft_allow_lean_meta("agree · last rs · lead rs")
        == "quiet · 1 fold · last/lead rs"
    )
    assert (
        soft_allow_lean_meta("last vs lead · breadth", warn=True)
        == "clash · last/lead breadth"
    )
    assert (
        soft_allow_lean_meta(
            "agree · last rs · lead rs · ×2 · 67%"
        )
        == "quiet · 1 fold · last/lead rs ×2 67%"
    )
    assert (
        soft_allow_lean_meta(
            "last vs lead · breadth · ×2 · 67%", warn=True
        )
        == "clash · last/lead breadth ×2 67%"
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · agree · last rs · lead rs"
        )
        == "quiet · 2 folds · lead/config rs on · last/lead rs"
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · agree · last rs · lead rs · "
            "last/config align · both agree · ×2 · 67%"
        )
        == (
            "quiet · 3 folds · lead/config rs on · last/lead rs · "
            "last/config align both agree ×2 67%"
        )
    )
    # Gate last/lead age (gap freshness parity) — verb + age + agree|vs.
    assert (
        soft_allow_lean_meta(
            "agree · last rs · lead rs · last/lead align · fresh · agree"
        )
        == (
            "quiet · 2 folds · last/lead rs · "
            "last/lead align fresh agree"
        )
    )
    assert (
        soft_allow_lean_meta(
            "agree · last rs · lead rs · "
            "last/lead clash · expired · agree",
            warn=True,
        )
        == (
            "clash · last/lead rs · last/lead clash expired agree"
        )
    )
    # Lead↔Ops age (#576 + last/lead freshness parity) — on|off rides.
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · lead/config align · fresh · on"
        )
        == (
            "quiet · 2 folds · lead/config rs on · "
            "lead/config align fresh on"
        )
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · "
            "lead/config clash · expired · on",
            warn=True,
        )
        == (
            "clash · lead/config rs on · lead/config clash expired on"
        )
    )
    assert (
        soft_allow_lean_meta(
            "clash · lead rs · RS off · last vs lead · breadth · "
            "last/config align · both clash",
            warn=True,
        )
        == (
            "clash · last/config align both clash · lead/config rs off · "
            "last/lead breadth"
        )
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · last vs lead · breadth · "
            "last/config clash · last clash · config agree",
            warn=True,
        )
        == (
            "clash · lead/config rs on · last/lead breadth · "
            "last/config clash last clash config agree"
        )
    )
    assert (
        soft_allow_lean_meta(
            "last vs lead · breadth · clash · scan stale",
            warn=True,
        )
        == "clash · last/lead breadth · scan"
    )
    assert soft_allow_lean_meta("clash · scan fresh") == "quiet · 1 fold · scan"
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · clash · soft fresh · gap expired · "
            "2 gap · last AAPL · fresh"
        )
        == "quiet · 3 folds · scan · soft/gap · gap AAPL fresh"
    )
    # gap↔scan / cash / memory were silent on the chip (N gap alone ≠ generation).
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only · scan-only"
        )
        == "quiet · 1 fold · gap/scan gap-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only · scan-only · US-only"
        )
        == "quiet · 1 fold · gap/scan gap-only scan-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only"
        )
        == "quiet · 1 fold · gap/scan gap-only"
    )
    assert (
        soft_allow_lean_meta("clash · gap aging · cash stale")
        == "quiet · 1 fold · gap/cash"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · US · 50%"
        )
        == "quiet · 1 fold · gap/cash gap-only US 50%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · US-only"
        )
        == "quiet · 1 fold · gap/cash gap-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · US-only · scan-only"
        )
        == "quiet · 1 fold · gap/cash gap-only US-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · ×2 · 100%"
        )
        == "quiet · 1 fold · gap/cash gap-only ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · laya fresh · debate fresh · "
            "gap-only · ×2 · 100%"
        )
        == "quiet · 1 fold · gap/memory gap-only ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · laya fresh · debate fresh · "
            "gap-only · ×2 · 100% · scan-only"
        )
        == "quiet · 1 fold · gap/memory gap-only ×2 100% scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · debate stale · gap-only · debate-only · "
            "US-only"
        )
        == "quiet · 1 fold · gap/memory gap-only debate-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · debate stale · gap-only · debate-only"
        )
        == "quiet · 1 fold · gap/memory gap-only debate-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · laya fresh · gap-only · laya · 50%"
        )
        == "quiet · 1 fold · gap/memory gap-only laya 50%"
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · clash · gap expired · scan stale",
            warn=True,
        )
        == "clash · gap AAPL fresh · gap/scan"
    )
    # soft≠gap must not greedily eat a later gap↔scan on the same lean line.
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · 2 gap · last AAPL · fresh · "
            "clash · gap expired · scan stale"
        )
        == "quiet · 3 folds · soft/gap · gap AAPL fresh · gap/scan"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · soft-only · gap-only"
        )
        == "quiet · 1 fold · soft/gap soft-only gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · soft-only · gap-only · scan-only"
        )
        == "quiet · 1 fold · soft/gap soft-only gap-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · gap-only"
        )
        == "quiet · 1 fold · soft/gap gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · US-only"
        )
        == "quiet · 1 fold · soft/cash soft-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · US-only · scan-only"
        )
        == "quiet · 1 fold · soft/cash soft-only US-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · US-only · "
            "scan-only · gap-only"
        )
        == "quiet · 1 fold · soft/cash soft-only US-only scan-only gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · soft-only · scan-only · US-only · gap-only"
        )
        == "quiet · 1 fold · scan soft-only scan-only US-only gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · debate stale · soft-only · debate-only · US-only · "
            "gap-only"
        )
        == "quiet · 1 fold · memory soft-only debate-only US-only gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · US-only"
        )
        == "quiet · 1 fold · soft/cash US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · Xetra · 50%"
        )
        == "quiet · 1 fold · soft/cash soft-only Xetra 50%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · ×2 · 100%"
        )
        == "quiet · 1 fold · soft/cash ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · soft-only · scan-only"
        )
        == "quiet · 1 fold · scan soft-only scan-only"
    )
    assert (
        soft_allow_lean_meta("clash · scan fresh · scan-only")
        == "quiet · 1 fold · scan scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · debate stale · soft-only · debate-only"
        )
        == "quiet · 1 fold · memory soft-only debate-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · debate stale · soft-only · debate-only · scan-only"
        )
        == "quiet · 1 fold · memory soft-only debate-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · laya stale · debate aging · soft-only · ×2 · 100%"
        )
        == "quiet · 1 fold · memory soft-only ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · laya stale · debate aging · ×2 · 100%"
        )
        == "quiet · 1 fold · memory ×2 100%"
    )
    assert (
        soft_allow_lean_meta("clash · debate stale · debate-only")
        == "quiet · 1 fold · memory debate-only"
    )
    assert (
        soft_allow_lean_meta("clash · laya stale · laya · 50%")
        == "quiet · 1 fold · memory laya 50%"
    )
    assert (
        soft_allow_lean_meta("clash · scan stale", warn=True)
        == "clash · scan"
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · hot · 66.7%", warn=True
        )
        == "hot · gap AAPL fresh hot 66.7%"
    )
    # Bare N gap hid age↔share / gap-vs-other / share↔lean on the chip.
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · hot · 66.7% · "
            "last/share clash · expired · hot · "
            "vs 1 other · thin · 33.3% · "
            "gap vs other clash · gap hot · other ok · "
            "last/lean clash · expired · gap hot · other ok · "
            "share/lean clash · share clash · lean clash"
        )
        == (
            "quiet · 5 folds · gap AAPL fresh hot 66.7% · "
            "last/share clash expired hot vs 1 other thin 33.3% · "
            "gap/other clash gap hot · other ok · "
            "last/lean clash expired gap hot · other ok · +1"
        )
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · hot · 66.7% · "
            "last/share clash · expired · hot · "
            "gap vs other clash · gap hot · other ok",
            warn=True,
        )
        == (
            "clash · gap AAPL fresh hot 66.7% · last/share clash expired hot · "
            "gap/other clash gap hot · other ok"
        )
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last MSFT · expired · lead MSFT · 2 · 60% · agree · "
            "last/lead clash · expired · agree · "
            "last/share clash · expired · hot · "
            "lead/share clash · lead clash · share align"
        )
        == (
            "quiet · 5 folds · gap MSFT expired · lead MSFT 2 60% agree · "
            "last/lead clash expired agree · last/share clash expired hot · +1"
        )
    )
    # Cursor name ≠ sample: tied / sole / other owner stay on the chip.
    assert (
        soft_allow_lean_meta("1 gap · last AAPL · fresh · n=1")
        == "quiet · 2 folds · gap AAPL fresh · n=1"
    )
    assert (
        soft_allow_lean_meta("2 gap · last AAPL · fresh · tied · hot · 50%")
        == "quiet · 2 folds · gap AAPL fresh · tied hot 50%"
    )
    assert (
        soft_allow_lean_meta(
            "3 gap · last MSFT · fresh · lead AAPL · 2 · 67% · "
            "last vs lead · MSFT"
        )
        == "quiet · 2 folds · gap MSFT fresh · lead AAPL 2 67% vs lead · MSFT"
    )
    # Owner % alone hid margin and the #2 name. Sole 100% stays silent.
    assert (
        soft_allow_lean_meta(
            "3 gap · last MSFT · fresh · lead AAPL · 2 · 67% · "
            "last vs lead · MSFT · ahead thin · +1 · vs MSFT · 1 · 33%"
        )
        == (
            "quiet · 3 folds · gap MSFT fresh · "
            "lead AAPL 2 67% vs lead · MSFT · ahead thin +1 vs MSFT 1 33%"
        )
    )
    assert (
        soft_allow_lean_meta(
            "4 gap · last MSFT · fresh · lead AAPL · 3 · 75% · "
            "last vs lead · MSFT · ahead wide · +2 · vs MSFT · 1 · 25%",
            warn=True,
        )
        == (
            "warn · gap MSFT fresh · lead AAPL 3 75% vs lead · MSFT · "
            "ahead wide +2 vs MSFT 1 25%"
        )
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · lead AAPL · 2 · 100% · agree"
        )
        == "quiet · 2 folds · gap AAPL fresh · lead AAPL 2 100% agree"
    )


def test_soft_allow_glance_empty() -> None:
    assert build_soft_allow_glance(None)["ready"] is False
    assert build_soft_allow_glance([])["ready"] is False
    empty = build_soft_allow_glance(None)
    assert empty["line_core"] == ""
    assert empty["soft_lean"] == ""
    assert empty["soft_lean_warn"] is False
    assert empty["soft_lean_meta"] == "quiet"


def test_soft_allow_glance_one() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-09-23T11:00:00Z",
                "gate": "regime",
                "reason": "unknown — no SPY bars",
            }
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["severity"] == "hot"
    assert g["count"] == 1
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["aging_hours"] == 12.0
    assert g["last_gate"] == "regime"
    assert g["anchor_gap_count"] == 0
    assert g["anchor_gap_last"] == ""
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_lead_name"] == ""
    assert g["anchor_gap_symbol_lead_share"] is None
    assert g["anchor_gap_symbol_lead_margin"] is None
    assert g["anchor_gap_symbol_lead_margin_severity"] == ""
    assert g["anchor_gap_symbol_lead_margin_bit"] == ""
    assert g["anchor_gap_symbol_lead_runner"] == ""
    assert g["anchor_gap_symbol_lead_runner_count"] == 0
    assert g["anchor_gap_symbol_lead_runner_share"] is None
    assert g["anchor_gap_symbol_lead_sides"] == ""
    assert g["anchor_gap_symbol_last_vs_lead"] == ""
    assert g["anchor_gap_last_vs_lead_freshness"] == ""
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is False
    assert g["anchor_gap_symbol_sample_gap"] == ""
    assert g["anchor_gap_share_pct"] is None
    assert g["anchor_gap_share_severity"] == ""
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_last_lead_vs_share"] == ""
    assert g["anchor_gap_last_lead_vs_share_warn"] is False
    assert g["anchor_gap_other_count"] == 0
    assert g["anchor_gap_other_share_pct"] is None
    assert g["anchor_gap_other_share_severity"] == ""
    assert g["anchor_gap_vs_other"] == ""
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_lead_vs_lean"] == ""
    assert g["anchor_gap_last_lead_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_vs_scan_clash"] == ""
    assert g["anchor_gap_vs_scan_clash_warn"] is False
    assert g["anchor_gap_vs_cash_clock_clash"] == ""
    assert g["anchor_gap_vs_cash_clock_clash_warn"] is False
    assert g["anchor_gap_vs_memory_clock_clash"] == ""
    assert g["anchor_gap_vs_memory_clock_clash_warn"] is False
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["soft_vs_gap_clock_clash_warn"] is False
    assert g["soft_vs_cash_clock_clash"] == ""
    assert g["soft_vs_cash_clock_clash_warn"] is False
    assert g["soft_vs_memory_clock_clash"] == ""
    assert g["soft_vs_memory_clock_clash_warn"] is False
    assert g["laya_freshness"] == ""
    assert g["debate_freshness"] == ""
    assert g["anchor_gap_bit"] == ""
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == ""
    assert g["scan_vs_soft_allow_clash"] == ""
    assert g["line"].startswith("hot · ")
    assert "1 recent soft-allow" in g["line"]
    assert "[regime]" in g["line"]
    assert "no SPY bars" in g["line"]
    assert " gap" not in g["line"]
    assert "clash" not in g["line"]
    assert g["line_core"] == g["line"]
    assert g["soft_lean"] == ""
    assert g["soft_lean_warn"] is False
    assert g["soft_lean_meta"] == "quiet"


def test_soft_allow_glance_short_history_count() -> None:
    """xang1234 #668: rs×N alone ≠ young/short-series fail-open count."""
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-21T11:00:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-21T10:30:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-21T10:00:00Z",
                "gate": "rs",
                "reason": "NEW RS unknown — short history — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 2
    assert g["short_history_last"] == "IPO"
    # Two distinct short names → no strict lead (gap sample-gap parity).
    assert g["short_history_symbol_lead"] == ""
    assert g["short_history_symbol_sample_gap"] == "tied"
    assert g["short_history_symbol_last_vs_lead"] == ""
    # Absolute N short · N gap ≠ pair ownership (1÷3 = 33%).
    assert g["short_history_vs_gap"] == "vs gap · 1 · 33%"
    assert g["short_history_vs_gap_count"] == 1
    assert g["short_history_vs_gap_share"] == 33
    assert g["short_history_bit"] == (
        "2 short · last IPO · tied · vs gap · 1 · 33%"
    )
    assert "2 short · last IPO · tied · vs gap · 1 · 33%" in g["line"]
    assert g["anchor_gap_count"] == 1
    # Short before gap so the young-listing count is not clipped by gap lean.
    assert g["line"].index("2 short") < g["line"].index("1 gap")
    # Lean fold chip must name short — ``2 short · …`` used to leave
    # soft_lean_meta bare ``quiet`` because only ``N gap`` had a stage.
    # Cursor ticker rides on the short stage (#546 after #668); tied is
    # its own stage so last ≠ ring ownership is visible on the chip.
    # ``vs gap`` must match or the inventory stalls before ``1 gap``.
    # Gap still owns soft_lean; the 4-name meta clip may spill it to +N
    # when short + tied + vs gap already fill the inventory.
    assert "2 short · last IPO" in g["soft_lean"]
    assert "tied" in g["soft_lean"]
    assert "vs gap · 1 · 33%" in g["soft_lean"]
    assert "1 gap" in g["soft_lean"]
    assert "short IPO" in g["soft_lean_meta"]
    assert "tied" in g["soft_lean_meta"]
    assert soft_allow_lean_meta("2 short") == "quiet · 1 fold · short"
    assert soft_allow_lean_meta("2 short · last IPO") == (
        "quiet · 1 fold · short IPO"
    )
    assert soft_allow_lean_meta(
        "2 short · last IPO · 1 gap · last AAPL · fresh"
    ) == ("quiet · 2 folds · short IPO · gap AAPL fresh")
    assert soft_allow_lean_meta(
        "2 short · last IPO · tied · 1 gap · last AAPL · fresh"
    ) == ("quiet · 3 folds · short IPO · tied · gap AAPL fresh")
    assert soft_allow_lean_meta(
        "2 short · last IPO · tied · vs gap · 1 · 33% · "
        "1 gap · last AAPL · fresh"
    ) == (
        "quiet · 4 folds · short IPO · tied · vs gap 1 33% · gap AAPL fresh"
    )


def test_soft_allow_glance_short_history_symbol_lead() -> None:
    """last SYM alone ≠ which young/short name owns the fail-open ring."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-22T11:00:00Z",
                "gate": "rs",
                "reason": "NEW RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:45:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:30:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 3
    assert g["short_history_last"] == "NEW"
    assert g["short_history_symbol_lead"] == "lead IPO · 2 · 67%"
    assert g["short_history_symbol_lead_name"] == "IPO"
    assert g["short_history_symbol_lead_share"] == 67
    assert g["short_history_symbol_sample_gap"] == ""
    assert g["short_history_symbol_last_vs_lead"] == "last vs lead · NEW"
    assert g["short_history_symbol_lead_margin"] == 1
    assert g["short_history_symbol_lead_margin_severity"] == "thin"
    assert g["short_history_symbol_lead_margin_bit"] == "ahead thin · +1"
    assert g["short_history_symbol_lead_runner"] == "NEW"
    assert g["short_history_symbol_lead_runner_count"] == 1
    assert g["short_history_symbol_lead_runner_share"] == 33
    assert g["short_history_symbol_lead_sides"] == "vs NEW · 1 · 33%"
    # 3 short + 1 gap → gap owns 25% of the RS fail-open pair.
    assert g["short_history_vs_gap"] == "vs gap · 1 · 25%"
    assert g["short_history_vs_gap_count"] == 1
    assert g["short_history_vs_gap_share"] == 25
    assert g["short_history_bit"] == (
        "3 short · last NEW · lead IPO · 2 · 67% · last vs lead · NEW · "
        "ahead thin · +1 · vs NEW · 1 · 33% · vs gap · 1 · 25%"
    )
    assert "lead IPO · 2 · 67%" in g["line"]
    assert "last vs lead · NEW" in g["line"]
    assert "ahead thin · +1" in g["line"]
    assert "vs NEW · 1 · 33%" in g["line"]
    assert "vs gap · 1 · 25%" in g["line"]
    assert "short NEW" in g["soft_lean_meta"]
    assert "lead IPO" in g["soft_lean_meta"]


def test_soft_allow_glance_anchor_gap_count() -> None:
    """xang1234 #539: rs×N alone ≠ gappy-anchor fail-open count + share."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 0
    assert g["short_history_bit"] == ""
    assert g["anchor_gap_count"] == 2
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_last_vs_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "tied"
    assert g["anchor_gap_share_pct"] == 66.7
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot · ×2 · 67%"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_other_count"] == 1
    assert g["anchor_gap_other_share_pct"] == 33.3
    assert g["anchor_gap_other_share_severity"] == "thin"
    assert g["anchor_gap_vs_other"] == "align · hot|thin"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "align · fresh · hot|thin · ×2 · 67%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "align · both align · ×2 · 67%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_bit"] == (
        "2 gap · last AAPL · fresh · tied · hot · 66.7% · "
        "last/share align · fresh · hot · ×2 · 67% · vs 1 other · thin · "
        "33.3% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · ×2 · 67% · "
        "share/lean align · both align · ×2 · 67%"
    )
    assert (
        "2 gap · last AAPL · fresh · tied · hot · 66.7% · "
        "last/share align · fresh · hot · ×2 · 67% · vs 1 other · thin · "
        "33.3% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · ×2 · 67% · "
        "share/lean align · both align · ×2 · 67%"
    ) in g["line"]
    # Gate last=lead agree + fresh age ride the lean fold beside RS-gap.
    assert g["last_vs_lead"] == "agree · last rs · lead rs · ×3 · 100%"
    assert g["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×3 · 100%"
    )
    assert g["soft_lean"].startswith(
        "agree · last rs · lead rs · ×3 · 100% · "
        "last/lead align · fresh · agree · ×3 · 100% · "
    )
    assert g["soft_lean"].endswith(g["anchor_gap_bit"])
    assert g["soft_lean_warn"] is True
    assert g["soft_lean_meta"] == (
        "hot · last/lead rs ×3 100% · last/lead align fresh agree ×3 100% · "
        "gap AAPL fresh · tied hot 66.7% · +4"
    )
    assert g["anchor_gap_bit"] not in g["line_core"]
    assert "soft-allow" in g["line_core"]
    assert "last/share" not in g["line_core"]
    assert "last [rs]" in g["line"]
    assert "anchor gap" in g["line"]


def test_soft_allow_glance_anchor_gap_symbol_lead() -> None:
    """last SYM ≠ ring ownership: strict gap-symbol lead speaks %."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:45:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_count"] == 3
    assert g["anchor_gap_last"] == "MSFT"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == "lead AAPL · 2 · 67%"
    assert g["anchor_gap_symbol_lead_name"] == "AAPL"
    assert g["anchor_gap_symbol_lead_share"] == 67
    assert g["anchor_gap_symbol_lead_margin"] == 1
    assert g["anchor_gap_symbol_lead_margin_severity"] == "thin"
    assert g["anchor_gap_symbol_lead_margin_bit"] == "ahead thin · +1"
    assert g["anchor_gap_symbol_lead_runner"] == "MSFT"
    assert g["anchor_gap_symbol_lead_runner_count"] == 1
    assert g["anchor_gap_symbol_lead_runner_share"] == 33
    assert g["anchor_gap_symbol_lead_sides"] == "vs MSFT · 1 · 33%"
    assert g["anchor_gap_symbol_last_vs_lead"] == "last vs lead · MSFT"
    assert g["anchor_gap_last_vs_lead_freshness"] == (
        "clash · fresh · vs MSFT · ×3 · 75%"
    )
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is True
    assert g["anchor_gap_symbol_sample_gap"] == ""
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot · ×3 · 75%"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_last_lead_vs_share"] == (
        "clash · lead clash · share align · ×3 · 75%"
    )
    assert g["anchor_gap_last_lead_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "align · fresh · hot|thin · ×3 · 75%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_lead_vs_lean"] == (
        "clash · lead clash · lean align · ×3 · 75%"
    )
    assert g["anchor_gap_last_lead_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "align · both align · ×3 · 75%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_bit"] == (
        "3 gap · last MSFT · fresh · lead AAPL · 2 · 67% · last vs lead · MSFT · "
        "last/lead clash · fresh · vs MSFT · ×3 · 75% · "
        "ahead thin · +1 · vs MSFT · 1 · 33% · hot · 75% · "
        "last/share align · fresh · hot · ×3 · 75% · "
        "lead/share clash · lead clash · share align · ×3 · 75% · "
        "vs 1 other · thin · 25% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · ×3 · 75% · "
        "lead/lean clash · lead clash · lean align · ×3 · 75% · "
        "share/lean align · both align · ×3 · 75%"
    )
    assert "lead AAPL · 2 · 67%" in g["line"]
    assert "last vs lead · MSFT" in g["line"]
    assert "last/lead clash · fresh · vs MSFT" in g["line"]
    assert "ahead thin · +1" in g["line"]
    assert "vs MSFT · 1 · 33%" in g["line"]
    # Gate last=lead agree + age align take chip slots; gap last/lead +
    # ahead may sit in +N.
    assert g["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×4 · 100%"
    )
    assert "last/lead rs" in g["soft_lean_meta"]
    assert "last/lead align fresh agree ×4 100%" in g["soft_lean_meta"]
    assert "last/lead clash · fresh · vs MSFT" in g["soft_lean"]
    assert "ahead thin · +1 · vs MSFT · 1 · 33%" in g["soft_lean"]
    assert "last/share align · fresh · hot" in g["line"]
    assert "lead/share clash · lead clash · share align" in g["line"]
    assert "last/lean align · fresh · hot|thin" in g["line"]
    assert "lead/lean clash · lead clash · lean align" in g["line"]
    assert "share/lean align · both align" in g["line"]


def test_soft_allow_glance_anchor_gap_last_vs_lead_freshness_stale_agree() -> None:
    """Bare agree ≠ live owner: expired + agree clashes and warns."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_symbol_last_vs_lead"] == "agree"
    assert g["anchor_gap_last_vs_lead_freshness"] == (
        "clash · expired · agree · ×2 · 100%"
    )
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is True
    assert g["anchor_gap_last_vs_share"] == (
        "clash · expired · hot · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_share"] == (
        "align · both clash · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · expired · hot|thin · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_lean"] == (
        "align · both clash · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_lean_warn"] is True
    assert g["tone"] == "warn"
    assert "last/lead clash · expired · agree" in g["anchor_gap_bit"]
    assert "lead/share align · both clash" in g["anchor_gap_bit"]
    assert "lead/lean align · both clash" in g["anchor_gap_bit"]
    assert "last/lead clash · expired · agree" in g["line"]
    assert "lead/share align · both clash" in g["line"]
    assert "lead/lean align · both clash" in g["line"]


def test_soft_allow_lean_meta_keeps_relationship_payload() -> None:
    """Verb alone ≠ the print: age, heat, and crossed pairs stay on the chip."""
    from openbb_backend.desk import soft_allow_lean_meta

    crossed = soft_allow_lean_meta(
        "lead/share clash · lead clash · share align",
        warn=True,
    )
    assert crossed == "clash · lead/share clash lead clash share align"
    gap_other = soft_allow_lean_meta(
        "gap vs other clash · gap hot · other ok",
        warn=True,
    )
    assert gap_other == "clash · gap/other clash gap hot · other ok"
    calm = soft_allow_lean_meta(
        "2 gap · last AAPL · fresh · last/share align · fresh · hot",
        warn=False,
    )
    assert calm == "quiet · 2 folds · gap AAPL fresh · last/share align fresh hot"


def test_soft_allow_glance_anchor_gap_share_lean_both_clash_warns() -> None:
    """Dual-clash agreement ≠ calm: align · both clash warns + tone."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == (
        "clash · expired · hot · ×2 · 67%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_vs_other"] == "align · hot|thin"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · expired · hot|thin · ×2 · 67%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "align · both clash · ×2 · 67%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "share/lean align · both clash" in g["anchor_gap_bit"]
    assert "share/lean align · both clash" in g["line"]
    assert g["soft_lean_meta"].startswith(
        "clash · share/lean align both clash"
    )
    assert "last/lead rs" in g["soft_lean_meta"]
    assert "last/share clash · expired · hot" in g["soft_lean"]


def test_soft_allow_glance_anchor_gap_share_quiet() -> None:
    """portfolio AI: low gap ownership speaks quiet · % + vs other strong."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:45:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "regime",
                "reason": "unknown — no SPY bars",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "breadth",
                "reason": "unknown scan",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_count"] == 1
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "n=1"
    assert g["anchor_gap_share_pct"] == 25.0
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == (
        "clash · fresh · quiet · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_other_count"] == 3
    assert g["anchor_gap_other_share_pct"] == 75.0
    assert g["anchor_gap_other_share_severity"] == "strong"
    assert g["anchor_gap_vs_other"] == "align · quiet|strong"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "align · fresh · quiet|strong · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share clash · lean align · ×1 · 25%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["anchor_gap_bit"] == (
        "1 gap · last AAPL · fresh · n=1 · quiet · 25% · "
        "last/share clash · fresh · quiet · ×1 · 25% · vs 3 other · strong · "
        "75% · gap vs other align · quiet|strong · "
        "last/lean align · fresh · quiet|strong · ×1 · 25% · "
        "share/lean clash · share clash · lean align · ×1 · 25%"
    )
    assert (
        "1 gap · last AAPL · fresh · n=1 · quiet · 25% · "
        "last/share clash · fresh · quiet · ×1 · 25% · vs 3 other · strong · "
        "75% · gap vs other align · quiet|strong · "
        "last/lean align · fresh · quiet|strong · ×1 · 25% · "
        "share/lean clash · share clash · lean align · ×1 · 25%"
    ) in g["line"]
    assert g["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 50%"
    )
    assert "last/lead rs" in g["soft_lean_meta"]
    assert "last/lead align fresh agree ×2 50%" in g["soft_lean_meta"]
    assert "n=1 quiet 25%" in g["soft_lean_meta"]
    # last/share may sit in +N once gate age takes a chip slot.
    assert "last/share clash · fresh · quiet" in g["soft_lean"]
    # gap/other may sit in +N once last/lead takes a chip slot.
    assert "gap vs other align · quiet|strong" in g["soft_lean"]


def test_soft_allow_glance_anchor_gap_vs_other_clash() -> None:
    """Sides alone ≠ lean: gap hot + other mid speaks clash (junk_vs_ok)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot · ×1 · 50%"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "n=1"
    assert g["anchor_gap_other_share_severity"] == "ok"
    assert g["anchor_gap_vs_other"] == "clash · gap hot · other ok"
    assert g["anchor_gap_vs_other_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · fresh · gap hot · other ok · ×1 · 50%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share align · lean clash · ×1 · 50%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert "1 gap · last AAPL · fresh · n=1 · hot · 50%" in g["anchor_gap_bit"]
    assert "last/share align · fresh · hot" in g["anchor_gap_bit"]
    assert "gap vs other clash · gap hot · other ok" in g["anchor_gap_bit"]
    assert "last/lean clash · fresh · gap hot · other ok" in g["anchor_gap_bit"]
    assert (
        "share/lean clash · share align · lean clash" in g["anchor_gap_bit"]
    )
    assert "gap vs other clash · gap hot · other ok" in g["line"]


def test_soft_allow_glance_anchor_gap_last_freshness_aging() -> None:
    """Cursor name ≠ live fail-open: aging/expired speak after last SYM."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": aging,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    # Hot share / lean clash escalate tone; severity stays aging (not hot).
    assert g["severity"] == "aging"
    assert g["tone"] == "warn"
    assert g["anchor_gap_bit"].startswith("1 gap · last AAPL · aging · n=1")
    assert "n=1 hot 50% vs 1 other 50%" in g["soft_lean_meta"]
    assert "last AAPL · aging" in g["line"]
    assert "last/share" not in g["anchor_gap_bit"]
    assert "last/lean" not in g["anchor_gap_bit"]
    assert "share/lean" not in g["anchor_gap_bit"]


def test_soft_allow_glance_anchor_gap_expired_tone_warn() -> None:
    """RyanJHamby age≠severity: expired gap cursor warns; cool-off stays cool."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    other = {
        "at": stale,
        "gate": "rs",
        "reason": "SPY RS unknown — allow",
    }
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            other,
            {**other, "reason": "MSFT RS unknown — allow"},
            {**other, "reason": "NVDA RS unknown — allow"},
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == (
        "align · expired · quiet · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · expired · quiet|strong · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share align · lean clash · ×1 · 25%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "last AAPL · expired" in g["anchor_gap_bit"]
    assert "last/share align · expired · quiet" in g["anchor_gap_bit"]
    assert "last/lean clash · expired · quiet|strong" in g["anchor_gap_bit"]
    assert (
        "share/lean clash · share align · lean clash" in g["anchor_gap_bit"]
    )


def test_soft_allow_glance_anchor_gap_last_vs_share_clash_tone() -> None:
    """Cursor age ≠ ownership heat: expired·hot clash warns (cool-off cool)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == (
        "clash · expired · hot · ×1 · 50%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "align · expired · gap hot · other ok · ×1 · 50%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share clash · lean align · ×1 · 50%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "last/share clash · expired · hot" in g["anchor_gap_bit"]
    assert "last/share clash · expired · hot" in g["line"]
    assert "last/lean align · expired · gap hot · other ok" in g["line"]
    assert "share/lean clash · share clash · lean align" in g["line"]


def test_soft_allow_glance_anchor_gap_aging_quiet_stays_flat() -> None:
    """Aging quiet gap label alone does not escalate (expired/hot/clash do)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    other = {
        "at": aging,
        "gate": "rs",
        "reason": "SPY RS unknown — allow",
    }
    g = build_soft_allow_glance(
        [
            {
                "at": aging,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            other,
            {**other, "reason": "MSFT RS unknown — allow"},
            {**other, "reason": "NVDA RS unknown — allow"},
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["severity"] == "aging"
    assert g["tone"] == "flat"


def test_soft_allow_glance_truncates_reason() -> None:
    long = "x" * 100
    g = build_soft_allow_glance([{"at": "t", "gate": "rs", "reason": long}])
    assert g["ready"] is True
    assert g["last_reason"].endswith("…")
    assert len(g["last_reason"]) <= 72


def test_soft_allow_glance_speaks_aging() -> None:
    """xang1234 / RyanJHamby: aging (>12h) speaks before expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["count"] == 2
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == ""
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "2 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "expired" not in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_consolidates_expired() -> None:
    """tradermonty #437: expired soft-allows speak count + gate tally."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": stale, "gate": "regime", "reason": "unknown — no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "unknown — no BTC bars"},
        ],
        now=now,
        fresh_hours=24.0,
    )
    assert g["count"] == 4
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 2
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == "regime×2"
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "4 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "2 expired" in g["line"]
    assert "regime×2" in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_aging_tally_only() -> None:
    """Aging-only ledger consolidates gates like the expired all-expired path."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert g["aging_count"] == 3
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == ""
    assert g["aging_tally"] == "breadth×2 · rs×1"
    assert g["severity"] == "aging"
    assert g["tone"] == "flat"
    assert g["lead_bit"] == (
        "breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_runner_gate"] == "rs"
    assert g["lead_runner_count"] == 1
    assert g["lead_runner_share_pct"] == 33.3
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == ""
    assert g["line"].startswith(
        "aging · breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · "
        "share Δ wide · +33pp · "
    )
    assert "3 soft-allows" in g["line"]
    assert "3 aging" in g["line"]
    assert "breadth×2" in g["line"]
    assert "rs×1" in g["line"]
    assert "fresh" not in g["line"]
    assert "expired" not in g["line"]


def test_soft_allow_glance_fresh_tally_mixed() -> None:
    """portfolio AI + xang1234: fresh gate tally beside aging/expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "regime", "reason": "no SPY bars"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 2
    assert g["aging_count"] == 1
    assert g["fresh_tally"] == "regime×1 · rs×1"
    assert "2 fresh" in g["line"]
    assert "regime×1" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]


def test_soft_allow_glance_fresh_tally_multi_recent() -> None:
    """All-fresh multi-gate ledger consolidates without aging noise."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 3
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×2 · breadth×1"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp"
    )
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert "3 recent soft-allows" in g["line"]
    assert "rs×2" in g["line"]
    assert "breadth×1" in g["line"]
    assert "aging" not in g["line"]
    assert "expired" not in g["line"]


def test_soft_allow_glance_all_expired() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": stale, "gate": "promote", "reason": "ABC: skip_no_bars"},
            {"at": stale, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["expired_count"] == 2
    assert g["fresh_count"] == 0
    assert g["aging_count"] == 0
    assert g["severity"] == "cool"
    assert g["tone"] == "flat"
    assert g["line"].startswith("cool · ")
    assert "2 expired soft-allows" in g["line"]
    assert "breadth×1" in g["line"]
    assert "promote×1" in g["line"]


def test_soft_allow_glance_cool_off_severity_triad() -> None:
    """portfolio AI + xang1234: hot / aging / cool — expired is not warn."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hot = build_soft_allow_glance(
        [{"at": fresh, "gate": "rs", "reason": "insufficient"}],
        now=now,
    )
    cooling = build_soft_allow_glance(
        [{"at": aging, "gate": "breadth", "reason": "unknown scan"}],
        now=now,
    )
    cool = build_soft_allow_glance(
        [{"at": stale, "gate": "regime", "reason": "no SPY bars"}],
        now=now,
    )
    assert (hot["severity"], hot["tone"]) == ("hot", "warn")
    assert (cooling["severity"], cooling["tone"]) == ("aging", "flat")
    assert (cool["severity"], cool["tone"]) == ("cool", "flat")
    assert hot["lead_bit"] == ""
    assert cooling["lead_bit"] == ""
    assert cool["lead_bit"] == ""


def test_soft_allow_glance_lead_gate_hot() -> None:
    """portfolio AI concentration: dominant fresh gate after severity."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["severity"] == "hot"
    assert g["lead_gate"] == "rs"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "fresh"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == ""
    assert g["lead_vs_config"] == ""
    assert g["line"].startswith(
        "hot · rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp · "
    )
    assert "rs×2" in g["line"]


def test_soft_allow_glance_lead_vs_config_off() -> None:
    """tradermonty #576: lead rs vs RS toggle speaks clash|agree."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [
        {"at": fresh, "gate": "rs", "reason": "insufficient a"},
        {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
    ]
    on = build_soft_allow_glance(
        rows, now=now, runtime={"rs_gate": True, "breadth_gate": True}
    )
    assert on["lead_vs_config"] == "agree · lead rs · ×2 · 67% · RS on"
    assert "agree · lead rs · ×2 · 67% · RS on" in on["line"]
    assert "agree · lead rs · ×2 · 67% · RS on" in on["soft_lean"]
    # Newest row matches lead → last/lead agree rides the lean chip.
    assert on["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 67%"
    assert on["last_lead_vs_config"] == (
        "last/config align · both agree · ×2 · 67%"
    )
    assert on["last_lead_vs_config_warn"] is False
    # Fresh + agree → last/lead + lead/config age align (calm).
    assert on["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 67%"
    )
    assert on["last_vs_lead_freshness_warn"] is False
    assert on["lead_vs_config_freshness"] == (
        "lead/config align · fresh · on · ×2 · 67%"
    )
    assert on["lead_vs_config_freshness_warn"] is False
    assert on["last_lead_vs_config_freshness"] == (
        "last/config age align · both align · fresh · ×2 · 67%"
    )
    assert on["last_lead_vs_config_freshness_warn"] is False
    assert on["soft_lean_warn"] is False
    assert on["soft_lean_meta"] == (
        "quiet · 6 folds · lead/config rs ×2 67% on · last/lead rs ×2 67% · "
        "last/config align both agree ×2 67% · "
        "last/lead align fresh agree ×2 67% · +2"
    )
    assert on["line"].index("rs leads") < on["line"].index(
        "agree · lead rs · ×2 · 67% · RS on"
    )
    assert on["tone"] == "warn"  # hot severity already warns; agree does not escalate
    off = build_soft_allow_glance(
        rows, now=now, runtime={"rs_gate": False, "breadth_gate": True}
    )
    assert off["lead_gate"] == "rs"
    assert off["lead_vs_config"] == "clash · lead rs · ×2 · 67% · RS off"
    assert "clash · lead rs · ×2 · 67% · RS off" in off["line"]
    assert "clash · lead rs · ×2 · 67% · RS off" in off["soft_lean"]
    # last matches lead + config off → crossed (last agree · config clash).
    assert off["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 67%"
    assert off["last_lead_vs_config"] == (
        "last/config clash · last agree · config clash · ×2 · 67%"
    )
    assert off["last_lead_vs_config_warn"] is True
    assert off["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 67%"
    )
    # Fresh + config off → lead/config age clash (live knob disagree).
    assert off["lead_vs_config_freshness"] == (
        "lead/config clash · fresh · off · ×2 · 67%"
    )
    assert off["lead_vs_config_freshness_warn"] is True
    assert off["last_lead_vs_config_freshness"] == (
        "last/config age clash · last/lead align · lead/config clash · "
        "fresh · ×2 · 67%"
    )
    assert off["last_lead_vs_config_freshness_warn"] is True
    assert off["soft_lean_warn"] is True
    assert off["soft_lean_meta"] == (
        "clash · lead/config rs ×2 67% off · last/lead rs ×2 67% · "
        "last/config clash last agree config clash ×2 67% · "
        "last/lead align fresh agree ×2 67% · +2"
    )
    assert off["line"].index("rs leads") < off["line"].index(
        "clash · lead rs · ×2 · 67% · RS off"
    )
    assert off["tone"] == "warn"
    # Aging-only ring stays flat until config clash escalates.
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cooling = build_soft_allow_glance(
        [
            {"at": aging, "gate": "rs", "reason": "insufficient a"},
            {"at": aging, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": False},
    )
    assert cooling["severity"] == "aging"
    assert cooling["lead_vs_config"] == "clash · lead rs · ×2 · 100% · RS off"
    assert cooling["tone"] == "warn"
    # Config clash alone opens the lean fold (no gen-clash / RS-gap).
    # Aging extremes stay silent on last/lead freshness.
    assert cooling["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 100%"
    assert cooling["last_vs_lead_freshness"] == ""
    assert cooling["lead_vs_config_freshness"] == ""
    assert cooling["last_lead_vs_config_freshness"] == ""
    assert cooling["last_lead_vs_config"] == (
        "last/config clash · last agree · config clash · ×2 · 100%"
    )
    assert cooling["soft_lean"] == (
        "clash · lead rs · ×2 · 100% · RS off · "
        "agree · last rs · lead rs · ×2 · 100% · "
        "last/config clash · last agree · config clash · ×2 · 100%"
    )
    assert cooling["soft_lean_warn"] is True
    assert cooling["soft_lean_meta"] == (
        "clash · lead/config rs ×2 100% off · last/lead rs ×2 100% · "
        "last/config clash last agree config clash ×2 100%"
    )
    # Agree on aging does not escalate flat → warn.
    cooling_on = build_soft_allow_glance(
        [
            {"at": aging, "gate": "rs", "reason": "insufficient a"},
            {"at": aging, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": True},
    )
    assert cooling_on["severity"] == "aging"
    assert cooling_on["lead_vs_config"] == "agree · lead rs · ×2 · 100% · RS on"
    assert cooling_on["tone"] == "flat"
    assert cooling_on["last_lead_vs_config"] == (
        "last/config align · both agree · ×2 · 100%"
    )
    assert cooling_on["soft_lean"] == (
        "agree · lead rs · ×2 · 100% · RS on · "
        "agree · last rs · lead rs · ×2 · 100% · "
        "last/config align · both agree · ×2 · 100%"
    )
    assert cooling_on["soft_lean_warn"] is False
    assert cooling_on["soft_lean_meta"] == (
        "quiet · 3 folds · lead/config rs ×2 100% on · last/lead rs ×2 100% · "
        "last/config align both agree ×2 100%"
    )
    # Expired + RS on → stale knob agree warns (last/lead freshness parity).
    expired = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_on = build_soft_allow_glance(
        [
            {"at": expired, "gate": "rs", "reason": "insufficient a"},
            {"at": expired, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": True},
    )
    assert stale_on["lead_vs_config"] == "agree · lead rs · ×2 · 100% · RS on"
    assert stale_on["lead_vs_config_freshness"] == (
        "lead/config clash · expired · on · ×2 · 100%"
    )
    assert stale_on["lead_vs_config_freshness_warn"] is True
    assert stale_on["last_vs_lead_freshness"] == (
        "last/lead clash · expired · agree · ×2 · 100%"
    )
    assert stale_on["last_lead_vs_config_freshness"] == (
        "last/config age align · both clash · expired · ×2 · 100%"
    )
    assert stale_on["last_lead_vs_config_freshness_warn"] is True
    assert stale_on["tone"] == "warn"
    assert "lead/config clash · expired · on" in stale_on["soft_lean"]
    assert stale_on["soft_lean_warn"] is True
    # Stale both-clash pins the clock so expired agree ≠ a live off.
    assert stale_on["soft_lean_meta"].startswith(
        "clash · last/config age align both clash expired ×2 100%"
    )
    # Dual clash: newest ≠ lead + Ops off — both-clash pins on the chip.
    dual = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": False, "breadth_gate": True},
    )
    assert dual["last_vs_lead"] == "last vs lead · breadth · ×2 · 67%"
    assert dual["lead_vs_config"] == "clash · lead rs · ×2 · 67% · RS off"
    assert dual["last_lead_vs_config"] == (
        "last/config align · both clash · ×2 · 67%"
    )
    assert dual["last_lead_vs_config_warn"] is True
    assert dual["last_vs_lead_freshness"] == (
        "last/lead clash · fresh · vs breadth · ×2 · 67%"
    )
    assert dual["last_vs_lead_freshness_warn"] is True
    assert dual["lead_vs_config_freshness"] == (
        "lead/config clash · fresh · off · ×2 · 67%"
    )
    assert dual["lead_vs_config_freshness_warn"] is True
    assert dual["last_lead_vs_config_freshness"] == (
        "last/config age align · both clash · fresh · ×2 · 67%"
    )
    assert dual["last_lead_vs_config_freshness_warn"] is True
    assert dual["soft_lean_warn"] is True
    assert dual["soft_lean_meta"] == (
        "clash · last/config align both clash ×2 67% · "
        "last/config age align both clash fresh ×2 67% · "
        "lead/config rs ×2 67% off · "
        "last/lead breadth ×2 67% · +2"
    )


def test_soft_allow_glance_lead_gate_aging() -> None:
    """Aging severity drives lead from the aging band (not expired)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert g["severity"] == "aging"
    assert g["lead_gate"] == "breadth"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "rs"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "aging"
    assert g["lead_bit"] == (
        "breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["line"].startswith(
        "aging · breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · "
        "share Δ wide · +33pp · "
    )


def test_soft_allow_glance_lead_gate_tie_silent() -> None:
    """Tied top gates stay silent — no false concentration."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "regime", "reason": "no SPY a"},
            {"at": fresh, "gate": "regime", "reason": "no SPY b"},
        ],
        now=now,
    )
    assert g["fresh_tally"] == "regime×2 · rs×2"
    assert g["lead_bit"] == ""
    assert g["lead_gate"] == ""
    assert g["lead_share_pct"] is None
    assert g["lead_margin"] is None
    assert g["lead_margin_severity"] == ""
    assert g["lead_runner_gate"] == ""
    assert g["lead_runner_count"] == 0
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert "leads" not in g["line"]


def test_soft_allow_glance_lead_gate_cool_expired() -> None:
    """Cool severity drives lead from the expired band."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": stale, "gate": "regime", "reason": "no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "no BTC bars"},
            {"at": stale, "gate": "promote", "reason": "ABC: skip_no_bars"},
        ],
        now=now,
    )
    assert g["severity"] == "cool"
    assert g["lead_gate"] == "regime"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "promote"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "expired"
    assert g["lead_bit"] == (
        "regime leads · expired · ×2 · 67% · ahead thin · +1 · vs promote ×1 · 33% · "
        "share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["line"].startswith(
        "cool · regime leads · expired · ×2 · 67% · ahead thin · +1 · vs promote ×1 · 33% · "
        "share Δ wide · +33pp · "
    )


def test_soft_allow_glance_lead_margin_wide() -> None:
    """Wide ahead when lead clears #2 by ≥2 (share ≠ margin)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "rs", "reason": "insufficient c"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["lead_margin"] == 2
    assert g["lead_margin_severity"] == "wide"
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_runner_share_pct"] == 25.0
    assert g["lead_share_delta_pp"] == 50.0
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == "align"
    assert g["lead_share_vs_delta_ahead"] == "wide"
    assert g["lead_share_vs_delta_share"] == "wide"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×3 · 75% · ahead wide · +2 · vs breadth ×1 · 25% · "
        "share Δ wide · +50pp · share vs Δ align · wide"
    )
    assert g["line"].startswith(
        "hot · rs leads · fresh · ×3 · 75% · ahead wide · +2 · vs breadth ×1 · 25% · "
        "share Δ wide · +50pp · share vs Δ align · wide · "
    )


def test_soft_allow_glance_lead_sole_no_ahead() -> None:
    """Sole-gate 100% share still omits ahead (no runner-up)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert g["lead_share_pct"] == 100.0
    assert g["lead_margin"] is None
    assert g["lead_margin_severity"] == ""
    assert g["lead_runner_gate"] == ""
    assert g["lead_runner_count"] == 0
    assert g["lead_bit"] == "rs leads · fresh · ×2 · 100%"
    assert "ahead" not in g["lead_bit"]
    assert "vs " not in g["lead_bit"]
    assert g["lead_runner_share_pct"] is None
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert g["lead_share_vs_delta"] == ""
    assert "share Δ" not in g["lead_bit"]


def test_soft_allow_glance_lead_share_delta_mid_clash() -> None:
    """Mid ownership spread: share Δ silent; share vs Δ clash speaks."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "a"},
            {"at": fresh, "gate": "rs", "reason": "b"},
            {"at": fresh, "gate": "rs", "reason": "c"},
            {"at": fresh, "gate": "rs", "reason": "d"},
            {"at": fresh, "gate": "regime", "reason": "e"},
            {"at": fresh, "gate": "regime", "reason": "f"},
            {"at": fresh, "gate": "regime", "reason": "g"},
        ],
        now=now,
    )
    assert g["lead_share_pct"] == 57.1
    assert g["lead_runner_share_pct"] == 42.9
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert g["lead_share_vs_delta"] == "clash"
    assert g["lead_share_vs_delta_ahead"] == "thin"
    assert g["lead_share_vs_delta_share"] == "mid"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×4 · 57% · ahead thin · +1 · vs regime ×3 · 43% · "
        "share vs Δ clash · ahead thin · share mid"
    )
    assert "share Δ" not in g["lead_bit"]


def test_soft_allow_glance_lead_share_delta_thin() -> None:
    """Thin ownership spread speaks when |Δ| < 10pp; align when ahead thin."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": f"a{i}"}
            for i in range(6)
        ]
        + [
            {"at": fresh, "gate": "regime", "reason": f"b{i}"}
            for i in range(5)
        ],
        now=now,
    )
    assert g["lead_share_delta_pp"] == 9.0
    assert g["lead_share_delta_severity"] == "thin"
    assert g["lead_share_vs_delta"] == "align"
    assert g["lead_share_vs_delta_ahead"] == "thin"
    assert g["lead_share_vs_delta_share"] == "thin"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×6 · 54% · ahead thin · +1 · vs regime ×5 · 46% · "
        "share Δ thin · +9pp · share vs Δ align · thin"
    )


def test_soft_allow_glance_last_vs_lead() -> None:
    """Newest gate vs band lead — FinRobot last ≠ ring tilt (LAYA parity)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Newest print is breadth; fresh band still led by rs.
    clash = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert clash["lead_gate"] == "rs"
    assert clash["last_gate"] == "breadth"
    assert clash["last_vs_lead"] == "last vs lead · breadth · ×2 · 67%"
    assert clash["last_vs_lead_freshness"] == (
        "last/lead clash · fresh · vs breadth · ×2 · 67%"
    )
    assert "last vs lead · breadth" in clash["line"]
    assert "last vs lead · breadth" in clash["soft_lean"]
    assert clash["soft_lean_warn"] is True
    assert clash["soft_lean_meta"] == (
        "clash · last/lead breadth ×2 67% · "
        "last/lead clash fresh vs breadth ×2 67%"
    )
    assert clash["line"].startswith(
        "hot · rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp · last vs lead · breadth · "
    )
    # Last≠lead clash alone opens the lean fold (no gen-clash / RS-gap).
    # Aging ring + newest gate ≠ lead stays flat on glance tone;
    # aging stays silent on last/lead freshness.
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cooling = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": aging, "gate": "rs", "reason": "insufficient a"},
            {"at": aging, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert cooling["severity"] == "aging"
    assert cooling["last_vs_lead"] == "last vs lead · breadth · ×2 · 67%"
    assert cooling["last_vs_lead_freshness"] == ""
    assert cooling["tone"] == "flat"  # last≠lead does not escalate tone
    assert cooling["soft_lean"] == "last vs lead · breadth · ×2 · 67%"
    assert cooling["soft_lean_warn"] is True
    assert cooling["soft_lean_meta"] == "clash · last/lead breadth ×2 67%"

    # Newest matches lead — speak agree (silent confirm hid match).
    match = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert match["lead_gate"] == "rs"
    assert match["last_gate"] == "rs"
    assert match["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 67%"
    assert match["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 67%"
    )
    assert "agree · last rs · lead rs" in match["line"]
    assert "agree · last rs · lead rs" in match["soft_lean"]
    assert match["soft_lean_warn"] is False
    assert match["soft_lean_meta"] == (
        "quiet · 2 folds · last/lead rs ×2 67% · "
        "last/lead align fresh agree ×2 67%"
    )
    assert "last vs lead" not in match["line"]

    # Expired + agree → stale match warns (gap last/lead freshness parity).
    expired = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_agree = build_soft_allow_glance(
        [
            {"at": expired, "gate": "rs", "reason": "insufficient a"},
            {"at": expired, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert stale_agree["severity"] == "cool"
    assert stale_agree["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 100%"
    assert stale_agree["last_vs_lead_freshness"] == (
        "last/lead clash · expired · agree · ×2 · 100%"
    )
    assert stale_agree["last_vs_lead_freshness_warn"] is True
    assert stale_agree["tone"] == "warn"
    assert stale_agree["soft_lean_warn"] is True
    assert (
        "last/lead clash · expired · agree · ×2 · 100%"
        in stale_agree["soft_lean"]
    )
    assert stale_agree["soft_lean_meta"] == (
        "clash · last/lead rs ×2 100% · "
        "last/lead clash expired agree ×2 100%"
    )

    # No lead (thin) — speak n=1 (last-row ≠ ring tilt; LAYA sample-gap parity).
    thin = build_soft_allow_glance(
        [{"at": fresh, "gate": "breadth", "reason": "unknown scan"}],
        now=now,
    )
    assert thin["lead_gate"] == ""
    assert thin["last_vs_lead"] == ""
    assert thin["sample_gap"] == "n=1"
    assert "n=1" in thin["line"]
    assert thin["line"].startswith("hot · n=1 · ")
    assert "last vs lead" not in thin["line"]
    assert "agree" not in thin["line"]

    # No lead (ties) — speak tied (≥2 in band, no strict winner).
    tied = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert tied["lead_gate"] == ""
    assert tied["sample_gap"] == "tied"
    assert "tied" in tied["line"]
    assert tied["line"].startswith("hot · tied · ")
    assert "leads" not in tied["line"]

    # Lead cases stay silent on sample_gap.
    assert match["sample_gap"] == ""
    assert "n=1" not in match["line"]
    assert "tied" not in match["line"]


def test_soft_allow_glance_scan_clash_expired_vs_fresh() -> None:
    """xang1234 #549: expired soft-allow ≠ fresh scan → clash · scan fresh."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["last_freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == (
        "clash · scan fresh · soft-only · scan-only"
    )
    assert g["tone"] == "warn"
    assert g["severity"] == "cool"
    assert g["line"].startswith(
        "cool · clash · scan fresh · soft-only · scan-only"
    )
    assert "clash" in g["line"]
    assert g["line_core"].startswith("cool · ")
    assert "clash · scan" not in g["line_core"]
    assert g["soft_lean"].startswith(
        "clash · scan fresh · soft-only · scan-only"
    )
    assert g["soft_lean_warn"] is True
    assert g["soft_lean_meta"].startswith("clash · scan")
    assert "soft-only" in g["soft_lean_meta"]
    assert "scan-only" in g["soft_lean_meta"]
    same = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=expired_at,
        scan_interval_sec=900,
    )
    assert same["scan_freshness"] == "stale"
    assert same["scan_vs_soft_allow_clash"] == ""
    # Soft↔scan same band — soft≠cash may still speak (pinned print age).
    assert "clash · scan" not in same["line"]
    if same["soft_vs_cash_clock_clash"]:
        assert same["tone"] == "warn"
        assert same["soft_vs_cash_clock_clash"] in same["line"]
    else:
        assert same["tone"] == "flat"


def test_soft_allow_glance_scan_clash_fresh_vs_stale() -> None:
    """Fresh fail-open vs stale scan → clash · scan stale (mixed generation)."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_scan = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        scan_time=stale_scan,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "stale"
    assert g["scan_vs_soft_allow_clash"] == (
        "clash · scan stale · soft-only · scan-only"
    )
    assert g["tone"] == "warn"
    assert g["line"].startswith(
        "hot · clash · scan stale · soft-only · scan-only"
    )
    # Soft ring share lied soft coverage was the archive; pins stay
    # soft-only · scan-only even when the soft ring is mixed.
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mixed = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            },
        ],
        now=now,
        scan_time=stale_scan,
        scan_interval_sec=900,
    )
    assert mixed["scan_vs_soft_allow_clash"] == (
        "clash · scan stale · soft-only · scan-only"
    )
    assert "soft-only" in mixed["soft_lean_meta"]
    assert "scan-only" in mixed["soft_lean_meta"]
    assert "×1" not in mixed["scan_vs_soft_allow_clash"]


def test_soft_allow_glance_gap_vs_scan_when_last_matches_scan() -> None:
    """xang1234 #549/e3c84e1: soft-allow last matching scan ≠ live gap cursor."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    # Soft-allow last matches scan — no ring-level clash.
    assert g["scan_vs_soft_allow_clash"] == ""
    # Soft last ≠ gap cursor — close the generation triangle; soft matches
    # scan so keep scan-only (peer soft keep-scan-only / #660).
    assert g["soft_vs_gap_clock_clash"] == (
        "clash · soft fresh · gap expired · soft-only · gap-only · scan-only"
    )
    assert g["soft_vs_gap_clock_clash_warn"] is True
    assert (
        "clash · soft fresh · gap expired · soft-only · gap-only · scan-only"
        in g["line"]
    )
    # Gap cursor is a different generation — speak both sides; soft≠gap
    # names soft-only · gap-only; gap≠scan names gap-only · scan-only.
    assert g["anchor_gap_vs_scan_clash"] == (
        "clash · gap expired · scan fresh · gap-only · scan-only"
    )
    assert g["anchor_gap_vs_scan_clash_warn"] is True
    assert g["tone"] == "warn"
    assert "clash · gap expired · scan fresh · gap-only · scan-only" in (
        g["anchor_gap_bit"]
    )
    assert "last AAPL · expired · clash · gap expired · scan fresh" in (
        g["anchor_gap_bit"]
    )
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert same["soft_vs_gap_clock_clash"] == ""
    assert same["soft_vs_gap_clock_clash_warn"] is False
    assert "clash · soft fresh · gap" not in same["line"]
    assert "clash · soft stale · gap" not in same["line"]
    assert same["anchor_gap_vs_scan_clash"] == ""
    assert same["anchor_gap_vs_scan_clash_warn"] is False
    # Soft↔gap + gap↔scan silent; soft≠cash / gap≠cash may still speak
    # and keep scan-only when the archive match is silent; soft≠cash also
    # keeps gap-only when soft matches the gap cursor; gap≠cash keeps
    # soft-only after scan-only (#660 speak-both-sides).
    assert "clash · gap" not in same["anchor_gap_bit"] or "scan fresh" not in (
        same["anchor_gap_bit"]
    )
    if same["soft_vs_cash_clock_clash"]:
        assert same["soft_vs_cash_clock_clash"] in same["line"]
        assert " · scan-only" in same["soft_vs_cash_clock_clash"]
        assert same["soft_vs_cash_clock_clash"].endswith(" · gap-only")
    if same["anchor_gap_vs_cash_clock_clash"]:
        assert same["anchor_gap_vs_cash_clock_clash"] in same["anchor_gap_bit"]
        assert " · scan-only" in same["anchor_gap_vs_cash_clock_clash"]
        assert same["anchor_gap_vs_cash_clock_clash"].endswith(" · soft-only")


def test_soft_allow_glance_soft_vs_gap_same_when_last_is_gap() -> None:
    """When soft last *is* the gap row, soft≠gap stays silent."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            }
        ],
        now=now,
    )
    assert g["last_freshness"] == "stale"
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["soft_vs_gap_clock_clash_warn"] is False
    assert "clash · soft" not in g["line"]


def test_soft_allow_glance_soft_vs_cash_when_soft_matches_scan() -> None:
    """xang1234 #549: soft matching scan ≠ pinned cash print generation."""
    # Saturday afternoon UTC — both cash sleeves last-published; US Fri
    # close is ~17h ago → cash aging while a fresh soft-allow + fresh
    # scan archive stay soft↔scan silent.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == ""
    cash = g["soft_vs_cash_clock_clash"]
    assert cash.startswith("clash · soft fresh · cash ")
    # Soft-only then cash pin sleeve (not soft ring): sole → venue-only;
    # dual half → named venue · 50%; both same band → ×2 · 100%; soft
    # matches scan → keep scan-only (#647 / #531 / #660; peer soft keep
    # scan-only parity; gap≠* own+other pin parity).
    assert " · soft-only · " in cash
    assert cash.endswith(" · scan-only")
    assert (
        " · US-only · scan-only" in cash
        or " · Xetra-only · scan-only" in cash
        or " · US · 50% · scan-only" in cash
        or " · Xetra · 50% · scan-only" in cash
        or " · ×2 · 100% · scan-only" in cash
    )
    assert g["soft_vs_cash_clock_clash_warn"] is True
    assert cash in g["line"]
    assert g["tone"] == "warn"
    # Same-evening last-published: soft fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    same = build_soft_allow_glance(
        [
            {
                "at": even_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=even,
        scan_time=even_at,
        scan_interval_sec=900,
    )
    assert same["last_freshness"] == "fresh"
    assert same["soft_vs_cash_clock_clash"] == ""
    assert same["soft_vs_cash_clock_clash_warn"] is False
    assert "cash" not in same["line"] or "clash · soft" not in same["line"]


def test_soft_allow_glance_gap_vs_cash_when_soft_matches_cash() -> None:
    """xang1234 #549: soft≠cash can still hide gap≠cash on the gap bit."""
    # Saturday afternoon UTC — cash sleeves last-published (US aging).
    # Soft last aging (12–24h) matches cash aging → soft≠cash silent;
    # expired gap cursor ≠ cash → gap≠cash speaks on the gap bit.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Fresh scan archive so soft aging ≠ scan is a separate bit; gap≠cash
    # still speaks on the gap bit after gap≠scan.
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "aging"
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["soft_vs_cash_clock_clash"] == ""
    # Soft matches cash → keep cash pin on soft≠scan / soft≠gap so those
    # bits cannot hide the match (keep-scan-only parity + #660 / #647).
    soft_scan = g["scan_vs_soft_allow_clash"]
    # _clock_clash names the other sleeve only (scan …); soft pin follows.
    assert soft_scan.startswith("clash · scan fresh · soft-only · scan-only · ")
    assert (
        soft_scan.endswith("US-only")
        or soft_scan.endswith("Xetra-only")
        or soft_scan.endswith("US · 50%")
        or soft_scan.endswith("Xetra · 50%")
        or soft_scan.endswith("×2 · 100%")
    )
    soft_gap = g["soft_vs_gap_clock_clash"]
    assert soft_gap.startswith(
        "clash · soft aging · gap expired · soft-only · gap-only · "
    )
    assert (
        soft_gap.endswith("US-only")
        or soft_gap.endswith("Xetra-only")
        or soft_gap.endswith("US · 50%")
        or soft_gap.endswith("Xetra · 50%")
        or soft_gap.endswith("×2 · 100%")
    )
    gap_cash = g["anchor_gap_vs_cash_clock_clash"]
    assert gap_cash.startswith("clash · gap expired · cash ")
    # Gap-only sole cursor pin; cash pin names coverage (#647 / #531).
    assert " · gap-only · " in gap_cash
    assert (
        gap_cash.endswith(" · US-only")
        or gap_cash.endswith(" · Xetra-only")
        or gap_cash.endswith(" · US · 50%")
        or gap_cash.endswith(" · Xetra · 50%")
        or gap_cash.endswith(" · ×2 · 100%")
    )
    assert g["anchor_gap_vs_cash_clock_clash_warn"] is True
    assert gap_cash in g["anchor_gap_bit"]
    assert g["tone"] == "warn"
    # Same-evening last-published: gap fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    same = build_soft_allow_glance(
        [
            {
                "at": even_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=even,
        scan_time=even_at,
        scan_interval_sec=900,
    )
    assert same["anchor_gap_last_freshness"] == "fresh"
    assert same["anchor_gap_vs_cash_clock_clash"] == ""
    assert same["anchor_gap_vs_cash_clock_clash_warn"] is False
    assert "cash" not in same["anchor_gap_bit"] or "clash · gap" not in (
        same["anchor_gap_bit"]
    )


def test_soft_allow_glance_vs_memory_clock_clash() -> None:
    """xang1234 #549: soft matching scan ≠ live LAYA/debate print."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="stale",
        debate_freshness="aging",
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == ""
    assert g["laya_freshness"] == "stale"
    assert g["debate_freshness"] == "aging"
    assert g["soft_vs_memory_clock_clash"] == (
        "clash · laya stale · debate aging · soft-only · ×2 · 100% · scan-only"
    )
    assert g["soft_vs_memory_clock_clash_warn"] is True
    assert g["tone"] == "warn"
    assert "clash · laya stale · debate aging" in g["line"]

    # Same band as soft — silent (no false mixed-generation warn).
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="fresh",
        debate_freshness="fresh",
    )
    assert same["soft_vs_memory_clock_clash"] == ""
    assert same["soft_vs_memory_clock_clash_warn"] is False
    assert "clash · laya" not in same["line"]
    assert "clash · debate" not in same["line"]

    # Only debate disagrees — soft-only then half-owner pin (dual
    # advisory configured; soft ring size no longer rides).
    one = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        laya_freshness="fresh",
        debate_freshness="stale",
    )
    assert one["soft_vs_memory_clock_clash"] == (
        "clash · debate stale · soft-only · debate · 50%"
    )
    assert one["soft_vs_memory_clock_clash_warn"] is True
    assert "clash · debate stale" in one["line"]
    assert "laya" not in one["soft_vs_memory_clock_clash"].split(" · debate ")[0]

    # Sole configured advisory that clashes → soft-only · debate-only.
    sole = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert sole["soft_vs_memory_clock_clash"] == (
        "clash · debate stale · soft-only · debate-only"
    )


def test_soft_allow_glance_soft_vs_memory_keeps_cash_when_soft_matches_cash() -> None:
    """Soft matching cash keeps cash pin on soft≠memory (#660 / #647)."""
    # Saturday afternoon UTC — soft aging matches cash aging; fresh scan
    # ≠ soft so keep-scan does not ride soft≠memory; stale debate ≠ soft
    # → soft≠memory speaks and must keep the cash pin.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["last_freshness"] == "aging"
    assert g["soft_vs_cash_clock_clash"] == ""
    assert g["scan_vs_soft_allow_clash"].startswith(
        "clash · scan fresh · soft-only · scan-only · "
    )
    mem = g["soft_vs_memory_clock_clash"]
    assert mem.startswith("clash · debate stale · soft-only · debate-only · ")
    assert (
        mem.endswith("US-only")
        or mem.endswith("Xetra-only")
        or mem.endswith("US · 50%")
        or mem.endswith("Xetra · 50%")
        or mem.endswith("×2 · 100%")
    )
    assert " · scan-only" not in mem
    assert mem in g["line"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_soft_keeps_gap_when_soft_matches_gap() -> None:
    """Soft matching gap keeps gap-only on soft≠scan / soft≠memory (#660)."""
    # Saturday afternoon UTC — soft last is the gap cursor (same stamp)
    # → soft≠gap silent; fresh scan ≠ soft → soft≠scan keeps gap-only;
    # stale debate ≠ soft → soft≠memory keeps gap-only (and cash when
    # soft also matches cash). LAYA keep gap-only + soft keep-cash mirror.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["last_freshness"] == "aging"
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["soft_vs_gap_clock_clash"] == ""
    soft_scan = g["scan_vs_soft_allow_clash"]
    assert soft_scan.startswith("clash · scan fresh · soft-only · scan-only · ")
    assert soft_scan.endswith(" · gap-only")
    mem = g["soft_vs_memory_clock_clash"]
    assert mem.startswith("clash · debate stale · soft-only · debate-only · ")
    assert mem.endswith(" · gap-only")
    assert " · scan-only" not in mem
    assert soft_scan in g["line"] or soft_scan in (g.get("soft_lean") or "")
    assert mem in g["line"] or mem in (g.get("soft_lean") or "")
    assert g["tone"] == "warn"


def test_soft_allow_glance_gap_keeps_soft_when_gap_matches_soft() -> None:
    """Gap matching soft keeps soft-only on gap≠scan / gap≠memory (#660)."""
    # Saturday afternoon UTC — soft last is the gap cursor (same stamp)
    # → soft≠gap silent; fresh scan ≠ gap → gap≠scan keeps soft-only;
    # stale debate ≠ gap → gap≠memory keeps soft-only (soft≠* keep
    # gap-only speak-both-sides + #660 / #647 / #531). Cash keep may
    # also ride when gap matches cash.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["anchor_gap_last_freshness"] == "aging"
    gap_scan = g["anchor_gap_vs_scan_clash"]
    assert gap_scan.startswith(
        "clash · gap aging · scan fresh · gap-only · scan-only · "
    )
    assert gap_scan.endswith(" · soft-only")
    gap_mem = g["anchor_gap_vs_memory_clock_clash"]
    assert gap_mem.startswith(
        "clash · gap aging · debate stale · gap-only · debate-only · "
    )
    assert gap_mem.endswith(" · soft-only")
    assert " · scan-only" not in gap_mem
    assert gap_scan in g["anchor_gap_bit"]
    assert gap_mem in g["anchor_gap_bit"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_gap_keeps_cash_when_gap_matches_cash() -> None:
    """Gap matching cash keeps cash pin on gap≠scan / gap≠memory (#660)."""
    # Saturday afternoon UTC — cash last-published aging. Gap aging
    # matches cash → gap≠cash silent; fresh scan ≠ gap → gap≠scan keeps
    # cash; stale debate ≠ gap → gap≠memory keeps cash (soft≠* keep-cash
    # mirror + #660 / #647 / #531). Soft also matches gap → soft-only
    # rides after cash (gap keep soft-only speak-both-sides).
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_vs_cash_clock_clash"] == ""
    gap_scan = g["anchor_gap_vs_scan_clash"]
    assert gap_scan.startswith(
        "clash · gap aging · scan fresh · gap-only · scan-only · "
    )
    assert gap_scan.endswith(" · soft-only")
    assert (
        "US-only" in gap_scan
        or "Xetra-only" in gap_scan
        or "US · 50%" in gap_scan
        or "Xetra · 50%" in gap_scan
        or "×2 · 100%" in gap_scan
    )
    gap_mem = g["anchor_gap_vs_memory_clock_clash"]
    assert gap_mem.startswith(
        "clash · gap aging · debate stale · gap-only · debate-only · "
    )
    assert gap_mem.endswith(" · soft-only")
    assert (
        "US-only" in gap_mem
        or "Xetra-only" in gap_mem
        or "US · 50%" in gap_mem
        or "Xetra · 50%" in gap_mem
        or "×2 · 100%" in gap_mem
    )
    assert " · scan-only" not in gap_mem
    assert gap_scan in g["anchor_gap_bit"]
    assert gap_mem in g["anchor_gap_bit"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_soft_keeps_memory_when_soft_matches_memory() -> None:
    """Soft matching advisory keeps memory pin on soft≠scan / soft≠gap (#660)."""
    # Soft aging matches dual fresh→aging advisories → soft≠memory silent;
    # fresh scan ≠ soft → soft≠scan keeps ×2 · 100%; soft≠gap silent when
    # gap cursor is the same stamp (gap keep-memory speak-both-sides below).
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="aging",
        debate_freshness="aging",
    )
    assert g["last_freshness"] == "aging"
    assert g["soft_vs_memory_clock_clash"] == ""
    soft_scan = g["scan_vs_soft_allow_clash"]
    assert soft_scan.startswith("clash · scan fresh · soft-only · scan-only · ")
    assert soft_scan.endswith(" · ×2 · 100%")
    assert " · debate-only" not in soft_scan
    assert soft_scan in g["line"] or soft_scan in (g.get("soft_lean") or "")
    # Sole advisory match → debate-only on soft≠scan.
    sole = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="aging",
    )
    assert sole["soft_vs_memory_clock_clash"] == ""
    assert sole["scan_vs_soft_allow_clash"].endswith(" · debate-only")
    assert g["tone"] == "warn"


def test_soft_allow_glance_gap_keeps_memory_when_gap_matches_memory() -> None:
    """Gap matching advisory keeps memory pin on gap≠scan (#660)."""
    # Soft/gap aging matches dual aging advisories → gap≠memory silent;
    # fresh scan ≠ gap → gap≠scan keeps ×2 · 100% after soft-only / cash.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="aging",
        debate_freshness="aging",
    )
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_vs_memory_clock_clash"] == ""
    gap_scan = g["anchor_gap_vs_scan_clash"]
    assert gap_scan.startswith(
        "clash · gap aging · scan fresh · gap-only · scan-only · "
    )
    assert gap_scan.endswith(" · ×2 · 100%")
    assert gap_scan in g["anchor_gap_bit"]
    assert g["tone"] == "warn"


def test_memory_advisory_pin_size_matched() -> None:
    """Keep-memory pins matching sleeves; clash mode still disagrees only."""
    from openbb_backend.desk import memory_advisory_pin_size

    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="fresh",
            debate_freshness="fresh",
            matched=True,
        )
        == " · ×2 · 100%"
    )
    assert (
        memory_advisory_pin_size(
            own_clock="aging",
            laya_freshness="",
            debate_freshness="aging",
            matched=True,
        )
        == " · debate-only"
    )
    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="fresh",
            debate_freshness="stale",
            matched=True,
        )
        == " · laya · 50%"
    )
    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="stale",
            debate_freshness="stale",
            matched=True,
        )
        == ""
    )
    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="stale",
            debate_freshness="",
        )
        == " · laya-only"
    )


def test_soft_allow_glance_gap_vs_memory_when_soft_matches_memory() -> None:
    """xang1234 #549: soft≠memory can still hide gap≠memory on the gap bit."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Soft last fresh matches laya/debate fresh → soft≠memory silent;
    # expired gap cursor ≠ memory → gap≠memory speaks on the gap bit.
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="fresh",
        debate_freshness="fresh",
    )
    assert g["last_freshness"] == "fresh"
    assert g["soft_vs_memory_clock_clash"] == ""
    assert g["anchor_gap_last_freshness"] == "expired"
    gap_mem = g["anchor_gap_vs_memory_clock_clash"]
    assert gap_mem == (
        "clash · gap expired · laya fresh · debate fresh · "
        "gap-only · ×2 · 100%"
    )
    assert g["anchor_gap_vs_memory_clock_clash_warn"] is True
    assert gap_mem in g["anchor_gap_bit"]
    assert g["tone"] == "warn"
    # Same band as gap (expired≡stale) — silent.
    same = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        laya_freshness="stale",
        debate_freshness="stale",
    )
    assert same["anchor_gap_vs_memory_clock_clash"] == ""
    assert same["anchor_gap_vs_memory_clock_clash_warn"] is False
    assert "laya" not in same["anchor_gap_bit"]
    assert "debate" not in same["anchor_gap_bit"]


def test_soft_allow_lean_fold_in_templates_css_charts() -> None:
    """Desk + Charts render soft lean fold (Yahoo mix lean parity)."""
    root = Path(__file__).resolve().parents[1]
    macros = (root / "openbb_backend/templates/macros.html").read_text(
        encoding="utf-8"
    )
    assert "soft-allow-lean" in macros
    assert "soft_lean_meta" in macros
    assert "line_core" in macros
    css = (root / "openbb_backend/static/desk.css").read_text(encoding="utf-8")
    assert ".soft-allow-glance .soft-allow-lean" in css
    charts = (root / "openbb_backend/static/charts.js").read_text(
        encoding="utf-8"
    )
    assert "soft_lean" in charts
    assert "soft-allow-lean" in charts
    assert "line_core" in charts
