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
    assert meta == "quiet · 2 folds · fees · LAYA"
    assert warn is False


def test_policy_honesty_fold_meta_all_calm_names() -> None:
    """Calm ready set names loaded glances; category index hid exits/gates."""
    meta, warn = policy_honesty_fold_meta(
        {"fee_burn_glance": {"ready": True, "tone": "quiet"}}
    )
    assert meta == "quiet · 1 fold · fees"
    assert warn is False
    snap = {
        key: {"ready": True, "tone": "flat"}
        for key in (
            "laya_glance",
            "crypto_policy_glance",
            "book_limits_glance",
            "fee_allowance_glance",
            "ai_mode_glance",
            "session_glance",
        )
    }
    meta, warn = policy_honesty_fold_meta(snap)
    assert warn is False
    assert meta == (
        "quiet · 6 folds · LAYA · crypto · book · allowance · +2"
    )


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
        "warn · 4 hot of 4 · fees · stuck · LAYA stale · debate aging · "
        "quiet · 0 folds"
    )


def test_policy_honesty_fold_meta_inventory_quiet_remainder() -> None:
    """Hot names + quiet · K folds + calm labels (Close honesty parity)."""
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
        "warn · 2 hot of 5 · fees · stuck · quiet · 3 folds · LAYA · crypto · AI"
    )


def test_policy_honesty_fold_meta_quiet_one_fold() -> None:
    """Singular fold unit when exactly one tracked glance stays calm."""
    meta, warn = policy_honesty_fold_meta(
        {
            "fee_burn_glance": {"ready": True, "tone": "warn"},
            "laya_glance": {"ready": True, "tone": "advisory"},
        }
    )
    assert warn is True
    assert meta == "warn · 1 hot of 2 · fees · quiet · 1 fold · LAYA"


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
        "warn · 1 hot of 7 · fees · quiet · 6 folds · LAYA · crypto · book · "
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
    assert meta.endswith("quiet · 0 folds")
    # inventory + six named labels + +2, then the empty calm remainder
    assert "fees · stuck · LAYA · debate · Yahoo · Hours · +2 · quiet · 0 folds" in meta


def test_policy_honesty_fold_meta_counts_static_fold_glances() -> None:
    """Exits/earnings/roles sit in the fold; the census used to skip them."""
    meta, warn = policy_honesty_fold_meta(
        {
            "exit_policy_glance": {"ready": True, "tone": "stock"},
            "earnings_blackout_glance": {"ready": True, "tone": "stock"},
            "ai_roles_glance": {"ready": True, "tone": "roles"},
            "stale_rotation_glance": {"ready": True, "tone": "stale"},
        }
    )
    assert warn is False
    assert meta == "quiet · 4 folds · exits · earnings · roles · stale-rot"


def test_policy_honesty_fold_meta_stale_rotation_warn_still_hot() -> None:
    """Identity tone stale stays calm; a real warn on that glance still opens."""
    meta, warn = policy_honesty_fold_meta(
        {"stale_rotation_glance": {"ready": True, "tone": "warn"}}
    )
    assert warn is True
    assert meta == "warn · 1 hot of 1 · stale-rot · quiet · 0 folds"


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
