"""Ops mutating-action audit (xang1234 #613 / #628 pattern).

Write a ``requested`` row *before* the side effect. If that commit fails,
do not act. After the action, write an outcome row (``accepted`` / ``error``).
Outcome write failure must not disguise a successful change — return the
real result and keep the request row so friends see intent without a
silent mutation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

OPS_ACTIONS_FILE = "ops_actions.json"
OPS_ACTIONS_CAP = 40
# Refuse a second same-kind mutation while a fresh ``requested`` row is still
# hanging (xang1234 #606/#613 double-click / in-flight refuse). Older hangings
# fail-open for Save but the glance speaks ``stale pending`` (crash leftover ≠
# in-flight) so friends do not treat an aged hang as a live refuse window.
OPS_PENDING_REFUSE_SECONDS = 120

T = TypeVar("T")


def ops_actions_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / OPS_ACTIONS_FILE


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ops_at(raw: Any) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def pending_ops_in_flight(
    data_dir: Path | str,
    *,
    kind: str,
    now: datetime | None = None,
    refuse_seconds: int = OPS_PENDING_REFUSE_SECONDS,
) -> dict[str, Any] | None:
    """Newest same-kind ``requested`` row when still inside the refuse window.

    Unparseable / aged-out hangings return ``None`` (fail-open) so Ops can save
    again after a crashed mid-flight; the glance speaks ``stale pending`` for
    aged hangings (see ``format_last_ops_action_bit``).
    """
    last = last_ops_action(data_dir, kind=kind)
    if not isinstance(last, dict):
        return None
    band = ops_pending_freshness_band(
        last, now=now, refuse_seconds=refuse_seconds
    )
    if band != "fresh":
        return None
    return last


def ops_pending_freshness_band(
    row: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    refuse_seconds: int = OPS_PENDING_REFUSE_SECONDS,
) -> str | None:
    """``fresh`` / ``stale`` for a hanging ``requested`` row; else ``None``.

    Fresh = still inside the refuse window (in-flight). Stale = aged past it
    (crash leftover / abandoned). Unparseable stamps stay ``None`` (fail-open
    label: plain ``pending``).
    """
    if not isinstance(row, dict):
        return None
    if str(row.get("outcome") or "") != "requested":
        return None
    stamp = _parse_ops_at(row.get("at"))
    if stamp is None:
        return None
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    age = (clock.astimezone(timezone.utc) - stamp).total_seconds()
    if age < 0:
        return None
    if age < max(1, int(refuse_seconds)):
        return "fresh"
    return "stale"


def trader_config_mtime_utc(data_dir: Path | str) -> datetime | None:
    """``trader_config.json`` mtime as UTC, or ``None`` when missing/unreadable."""
    from stock_checker.trader_config import config_path

    path = config_path(data_dir)
    try:
        if not path.is_file():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def ops_pending_no_outcome(
    row: dict[str, Any] | None,
    *,
    config_mtime: datetime | None = None,
) -> bool:
    """True when hanging ``requested`` and Ops file is strictly newer.

    xang1234 #630: a queued job with no responding worker looks live forever.
    Here a hanging request whose outcome writer never answered while
    ``trader_config.json`` already moved looks forever-pending — speak
    ``no outcome`` so friends do not wait for an accepted stamp that will
    not arrive. Missing / unparseable clocks fail-open (False).
    """
    if not isinstance(row, dict):
        return False
    if str(row.get("outcome") or "") != "requested":
        return False
    if config_mtime is None:
        return False
    stamp = _parse_ops_at(row.get("at"))
    if stamp is None:
        return False
    mtime = config_mtime
    if mtime.tzinfo is None:
        mtime = mtime.replace(tzinfo=timezone.utc)
    else:
        mtime = mtime.astimezone(timezone.utc)
    return mtime > stamp


def load_ops_actions(data_dir: Path | str) -> list[dict[str, Any]]:
    """Newest-first ring of Ops audit rows (empty on missing/junk)."""
    path = ops_actions_path(data_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        events = raw
    elif isinstance(raw, dict):
        events = raw.get("events")
    else:
        return []
    if not isinstance(events, list):
        return []
    out: list[dict[str, Any]] = []
    for row in events:
        if isinstance(row, dict):
            out.append(row)
    return out


def append_ops_action(
    data_dir: Path | str,
    row: dict[str, Any],
    *,
    cap: int = OPS_ACTIONS_CAP,
) -> bool:
    """Append one audit row. Returns False if the write failed."""
    path = ops_actions_path(data_dir)
    try:
        events = load_ops_actions(data_dir)
        events.append(dict(row))
        keep = max(1, int(cap))
        events = events[-keep:]
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = str(events[-1].get("at") or _now_iso())
        path.write_text(
            json.dumps({"updated_at": stamp, "events": events}, indent=2) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        logger.warning("ops audit write failed: %s", exc)
        return False


def last_ops_action(
    data_dir: Path | str,
    *,
    kind: str | None = None,
) -> dict[str, Any] | None:
    """Newest audit row (optionally filtered by kind). Newest-last on disk."""
    events = load_ops_actions(data_dir)
    want = (kind or "").strip()
    for row in reversed(events):
        if want and str(row.get("kind") or "") != want:
            continue
        return row
    return None


def ops_skip_reason_label(row: dict[str, Any] | None) -> str:
    """Compact why for a ``skipped`` row (xang1234 #599/#623 skip-says-why).

    Bare ``skipped`` hid whether Ops refused a no-op Save vs some other
    preflight. Unknown / empty reasons stay silent so the glance does not
    invent a cause.
    """
    if not isinstance(row, dict):
        return ""
    if str(row.get("outcome") or "") != "skipped":
        return ""
    raw = str(row.get("reason") or "").strip().lower().replace("_", "-")
    if not raw:
        detail = row.get("detail")
        if isinstance(detail, dict):
            raw = str(detail.get("reason") or "").strip().lower().replace("_", "-")
    if raw in ("no-op", "noop", "no-change", "nochange"):
        return "no-op"
    if raw and len(raw) <= 24 and all(c.isalnum() or c in "-." for c in raw):
        return raw
    return ""


def format_last_ops_action_bit(
    row: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    refuse_seconds: int = OPS_PENDING_REFUSE_SECONDS,
    config_mtime: datetime | None = None,
) -> str:
    """Compact Ops honesty line: ``last config · accepted · …Z``.

    A hanging ``requested`` row (no accepted/error yet) speaks ``pending`` when
    still inside the refuse window, or ``stale pending`` when aged out — so a
    crash leftover is not read as a live in-flight Save (xang1234 #613/#628
    outcome pairing + RyanJHamby/xang1234 fresh|stale age triad).

    When the Ops file is newer than that hanging request, also speak
    ``no outcome`` (xang1234 #630 no-worker-for-queue adapted) — the save
    likely landed without an accepted stamp, so waiting forever is wrong.

    A ``skipped`` row speaks ``skipped · no-op`` (or another compact reason)
    when the refuse recorded why — bare ``skipped`` hid intentional no-op
    vs other preflight (xang1234 #599/#623 skip-says-why).
    """
    if not isinstance(row, dict):
        return ""
    kind = str(row.get("kind") or "").strip() or "?"
    outcome = str(row.get("outcome") or "").strip() or "?"
    if outcome == "requested":
        band = ops_pending_freshness_band(
            row, now=now, refuse_seconds=refuse_seconds
        )
        outcome = "stale pending" if band == "stale" else "pending"
        if ops_pending_no_outcome(row, config_mtime=config_mtime):
            outcome = f"{outcome} · no outcome"
    elif outcome == "skipped":
        why = ops_skip_reason_label(row)
        if why:
            outcome = f"skipped · {why}"
    at = str(row.get("at") or "").strip()
    if at:
        return f"last {kind} · {outcome} · {at}"
    return f"last {kind} · {outcome}"


def record_ops_skipped(
    data_dir: Path | str,
    *,
    kind: str,
    reason: str = "no-op",
    detail: dict[str, Any] | None = None,
) -> bool:
    """Append a single ``skipped`` outcome (no requested/act dance).

    Used when Ops refuses a mutation that would only no-op (xang1234 #623
    refuse-before-queue when the run would only skip). Glance speaks
    ``last … · skipped · no-op`` so friends see the refuse was intentional
    and why (xang1234 #599/#623 skip-says-why).
    """
    kind_s = str(kind or "").strip() or "ops"
    reason_s = str(reason or "").strip() or "no-op"
    return append_ops_action(
        data_dir,
        {
            "id": str(uuid.uuid4()),
            "action_id": str(uuid.uuid4()),
            "at": _now_iso(),
            "kind": kind_s,
            "outcome": "skipped",
            "reason": reason_s,
            "detail": _safe_detail(detail),
        },
    )


def audited_ops_action(
    data_dir: Path | str,
    *,
    kind: str,
    detail: dict[str, Any] | None,
    act: Callable[[], T],
) -> tuple[T | None, dict[str, Any]]:
    """Run ``act`` only after a durable ``requested`` audit row.

    Returns ``(result, meta)``. When blocked (request write failed),
    ``result`` is ``None`` and ``meta["blocked"]`` is True. When ``act``
    raises, an ``error`` outcome is recorded (best effort) and the
    exception is re-raised.
    """
    action_id = str(uuid.uuid4())
    kind_s = str(kind or "").strip() or "ops"
    detail_safe = _safe_detail(detail)
    in_flight = pending_ops_in_flight(data_dir, kind=kind_s)
    if in_flight is not None:
        return None, {
            "blocked": True,
            "action_id": str(in_flight.get("action_id") or ""),
            "outcome": "blocked",
            "reason": "pending_in_flight",
            "pending_at": str(in_flight.get("at") or ""),
        }
    requested = {
        "id": str(uuid.uuid4()),
        "action_id": action_id,
        "at": _now_iso(),
        "kind": kind_s,
        "outcome": "requested",
        "detail": detail_safe,
    }
    if not append_ops_action(data_dir, requested):
        return None, {
            "blocked": True,
            "action_id": action_id,
            "outcome": "blocked",
            "reason": "audit_request_failed",
        }

    try:
        result = act()
    except Exception:
        append_ops_action(
            data_dir,
            {
                "id": str(uuid.uuid4()),
                "action_id": action_id,
                "at": _now_iso(),
                "kind": kind_s,
                "outcome": "error",
                "detail": detail_safe,
            },
        )
        raise

    accepted = {
        "id": str(uuid.uuid4()),
        "action_id": action_id,
        "at": _now_iso(),
        "kind": kind_s,
        "outcome": "accepted",
        "detail": detail_safe,
    }
    outcome_ok = append_ops_action(data_dir, accepted)
    return result, {
        "blocked": False,
        "action_id": action_id,
        "outcome": "accepted",
        "outcome_recorded": outcome_ok,
    }


def _safe_detail(detail: dict[str, Any] | None) -> dict[str, Any]:
    """Keep a small non-secret summary of what Ops asked to change."""
    if not isinstance(detail, dict):
        return {}
    out: dict[str, Any] = {}
    for key, val in list(detail.items())[:24]:
        k = str(key)
        kl = k.lower()
        if any(s in kl for s in ("key", "token", "secret", "password")):
            continue
        if isinstance(val, (bool, int, float)):
            out[k] = val
        elif isinstance(val, str):
            out[k] = val[:80]
        elif val is None:
            out[k] = None
        else:
            out[k] = type(val).__name__
    return out
