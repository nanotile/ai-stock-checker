"""Policy honesty fold summary names why it opened (fold-meta parity)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.desk import policy_honesty_fold_meta

QUIET = "crypto · exits · AI · gates · fees"

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "openbb_backend" / "templates"
CSS = ROOT / "openbb_backend" / "static" / "desk.css"
JS = ROOT / "openbb_backend" / "static" / "charts.js"

POLICY_SCREENS = (
    "desk_overview.html",
    "desk_screener.html",
    "desk_ideas.html",
    "desk_book.html",
    "desk_breadth.html",
    "desk_ops.html",
    "desk_scan_log.html",
)


def test_policy_honesty_fold_meta_quiet() -> None:
    assert policy_honesty_fold_meta(None) == (QUIET, False)
    assert policy_honesty_fold_meta({}) == (QUIET, False)
    meta, warn = policy_honesty_fold_meta(
        {
            "fee_burn_glance": {"ready": True, "tone": "quiet"},
            "laya_glance": {"ready": True, "tone": "advisory"},
        }
    )
    assert meta == QUIET
    assert warn is False


def test_policy_honesty_fold_meta_warn_and_clock() -> None:
    meta, warn = policy_honesty_fold_meta(
        {
            "fee_burn_glance": {"ready": True, "tone": "warn"},
            "stuck_capital_glance": {"ready": True, "tone": "warn"},
            "laya_glance": {"ready": True, "tone": "stale"},
            "ai_debate_glance": {"ready": True, "tone": "aging"},
        }
    )
    assert warn is True
    assert meta == (
        "warn · 4 hot of 4 · fees · stuck · LAYA stale · debate aging"
    )


def test_policy_honesty_fold_meta_inventory_quiet_remainder() -> None:
    """Hot names + quiet count + calm labels (Close honesty hot quiet folds)."""
    meta, warn = policy_honesty_fold_meta(
        {
            "fee_burn_glance": {"ready": True, "tone": "warn"},
            "stuck_capital_glance": {"ready": True, "tone": "warn"},
            "laya_glance": {"ready": True, "tone": "advisory"},
            "crypto_policy_glance": {"ready": True, "tone": "flat"},
            "ai_mode_glance": {"ready": True, "tone": "quiet"},
        }
    )
    assert warn is True
    assert meta == (
        "warn · 2 hot of 5 · fees · stuck · quiet · 3 · LAYA · crypto · AI"
    )


def test_policy_honesty_fold_meta_quiet_names_capped() -> None:
    """Calm name list caps at 4 +N; quiet count stays full."""
    snap = {
        "fee_burn_glance": {"ready": True, "tone": "warn"},
        "laya_glance": {"ready": True, "tone": "advisory"},
        "crypto_policy_glance": {"ready": True, "tone": "flat"},
        "book_limits_glance": {"ready": True, "tone": "flat"},
        "fee_allowance_glance": {"ready": True, "tone": "quiet"},
        "ai_mode_glance": {"ready": True, "tone": "quiet"},
        "session_glance": {"ready": True, "tone": "flat"},
    }
    meta, warn = policy_honesty_fold_meta(snap)
    assert warn is True
    assert meta == (
        "warn · 1 hot of 7 · fees · quiet · 6 · LAYA · crypto · book · "
        "allowance · +2"
    )


def test_policy_honesty_fold_meta_caps_storm() -> None:
    snap = {
        key: {"ready": True, "tone": "warn"}
        for key, _ in (
            ("fee_burn_glance", ""),
            ("stuck_capital_glance", ""),
            ("laya_glance", ""),
            ("ai_debate_glance", ""),
            ("universe_discovery_glance", ""),
            ("equity_hours_glance", ""),
            ("daily_loss_glance", ""),
            ("concentration_glance", ""),
        )
    }
    meta, warn = policy_honesty_fold_meta(snap)
    assert warn is True
    assert meta.startswith("warn · 8 hot of 8 · ")
    assert meta.endswith("+2")
    # inventory + six named labels + +2
    assert "fees · stuck · LAYA · debate · Yahoo · Hours · +2" in meta


def test_policy_honesty_templates_use_fold_meta() -> None:
    for name in POLICY_SCREENS:
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "policy_honesty_meta" in text, name
        assert "policy_honesty_warn" in text, name
        assert 'class="policy-honesty{% if policy_warn %} warn{% endif %}"' in text, name
        assert "{% if policy_warn %} open{% endif %}" in text, name


def test_policy_honesty_css_warn() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert ".policy-honesty.warn" in css


def test_charts_js_policy_honesty_fold_meta() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "policy_honesty_warn" in js
    assert "policy_honesty_meta" in js
    assert 'details.open = true' in js or "details.open = true" in js
