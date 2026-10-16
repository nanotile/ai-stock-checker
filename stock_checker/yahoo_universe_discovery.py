"""
Yahoo Finance movers → curated universe discovery (not auto-buy).

Pulls day gainers / losers via yfinance screen presets and proposes symbols
for StockUniverseManager. Trading still goes through regime / RS / breadth /
fees gates.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, List, Sequence

from stock_checker.symbol_filters import is_tradeable_symbol

# Keep discovery calm — we are not RyanJHamby's 3800-name firehose.
DEFAULT_MOVER_COUNT = 25
# Re-pull Yahoo movers when last discovery is older than this (desk shows age).
DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS = 24
# xang1234 dfb6a86: do not refetch an empty/dead slice every scan cycle.
# Failed Yahoo still retries sooner than the 24h success throttle, but not
# on every 15m scan — calm the thrash when movers stay blocked.
DEFAULT_YAHOO_FAIL_BACKOFF_HOURS = 1
# xang1234 #639: bound hung Yahoo screens (feedparser/requests had no timeout
# and looked like quiet empty forever). Per-screen join ceiling for yf.screen.
DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC = 20
DEFAULT_SCREENS: tuple[str, ...] = ("day_gainers", "day_losers", "most_actives")
# xang1234: a mostly empty snapshot is a failed fetch, not a quiet day.
EMPTY_SCREEN_FRACTION = 0.2


class YahooScreenEmptyError(Exception):
    """Yahoo screen returned nothing usable (block / empty payload)."""


def _quotes_from_screen_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        quotes = payload.get("quotes")
        if isinstance(quotes, list):
            return [q for q in quotes if isinstance(q, dict)]
    return []


def screen_payload_failed(payload: Any, *, expected: int) -> bool:
    """True when the screen looks blocked or mostly empty (do not stamp cache)."""
    quotes = _quotes_from_screen_payload(payload)
    if not quotes:
        return True
    want = max(1, int(expected))
    floor = max(1, int(want * EMPTY_SCREEN_FRACTION))
    return len(quotes) < floor


def screens_bundle_failed(ok: int, failed: int) -> bool:
    """True when the mover bundle is blocked or majority-failed.

    xang1234: a 403 / empty Finviz snapshot must not raise, and a mostly
    dead refresh is a failed fetch — do not stamp cache fresh or mix in
    leftover quotes from the one screen that still answered.
    """
    ok_n = max(0, int(ok))
    fail_n = max(0, int(failed))
    if ok_n <= 0:
        return True
    return fail_n > ok_n


def screens_bundle_partial(ok: int, failed: int) -> bool:
    """True when some screens answered and some failed (not majority-dead).

    xang1234 7e0df1e: skip prune baselines for partly failed fetches — leftover
    quotes from the live screens are still addable, but missing names are not
    a complete drop list.
    """
    if screens_bundle_failed(ok, failed):
        return False
    return max(0, int(failed)) > 0


def yahoo_cache_freshness(
    age_sec: float | None,
    *,
    max_age_hours: int = DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    parsed: bool = True,
) -> str:
    """Bound a reused seed by last-good discovery age (xang1234 317b6bb).

    ``never`` = no stamp. ``unknown`` = stamp present but unparsed.
    Otherwise fresh < max_age, aging < 2×, else stale.
    """
    if not parsed:
        return "unknown"
    if age_sec is None:
        return "never"
    limit = max(1, int(max_age_hours)) * 3600.0
    age = max(0.0, float(age_sec))
    if age < limit:
        return "fresh"
    if age < 2 * limit:
        return "aging"
    return "stale"


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def yahoo_fail_streak(meta: Any) -> int:
    """Consecutive failed Yahoo discovery attempts (xang1234 #639).

    Failures that looked like a quiet seed reused the same fail stamp without
    naming how many times in a row movers stayed dead. ``0`` when absent /
    unparseable / success cleared the counter.
    """
    if not isinstance(meta, dict):
        return 0
    raw = meta.get("yahoo_discovery_fail_streak")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def bump_yahoo_fail_streak(meta: dict[str, Any]) -> int:
    """Increment consecutive-fail counter on a blocked / empty movers fetch."""
    n = yahoo_fail_streak(meta) + 1
    meta["yahoo_discovery_fail_streak"] = n
    return n


def clear_yahoo_fail_streak(meta: dict[str, Any]) -> None:
    """Reset streak after a successful movers snapshot (last_success honesty)."""
    meta["yahoo_discovery_fail_streak"] = 0


# Compact fail reasons for desk (xang1234 #639 last-error chip — not a full
# Manage Sources tooltip). Allowlist only so junk meta cannot inflate the line.
YAHOO_FAIL_ERROR_CLASSES: frozenset[str] = frozenset(
    ("timeout", "http", "empty", "thin", "error")
)


def classify_yahoo_discovery_error(
    exc: BaseException | None = None,
    *,
    screens_ok: int | None = None,
    screens_failed: int | None = None,
    timeout_fails: int = 0,
) -> str:
    """Map a dead Yahoo movers fetch to a compact error class.

    xang1234 #639 reports content-source failures by kind so friends see
    *why* movers stayed dead — not only N× / fail age. Bundle path:
    ``empty`` when no screen answered; ``thin`` when majority failed but
    some answered. Transport timeouts own the class when they are the
    majority of failed screens (hung ≠ quiet empty). Exception path:
    ``timeout`` / ``http`` / ``error``.
    """
    try:
        timed_out = max(0, int(timeout_fails))
    except (TypeError, ValueError):
        timed_out = 0
    if screens_ok is not None and screens_failed is not None:
        ok_n = max(0, int(screens_ok))
        fail_n = max(0, int(screens_failed))
        other_fails = max(0, fail_n - timed_out)
        # Prefer timeout when transport death owns (or ties) the fail side.
        if timed_out > 0 and timed_out >= max(1, other_fails):
            if ok_n <= 0 or screens_bundle_failed(ok_n, fail_n):
                return "timeout"
        if ok_n <= 0:
            return "empty"
        if screens_bundle_failed(ok_n, fail_n):
            return "thin"
    if exc is None:
        return "error"
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if (
        isinstance(exc, TimeoutError)
        or "timeout" in name
        or "timed out" in msg
        or "timeout" in msg
    ):
        return "timeout"
    if (
        "http" in name
        or "403" in msg
        or "404" in msg
        or "429" in msg
        or "http error" in msg
    ):
        return "http"
    if isinstance(exc, YahooScreenEmptyError) or "empty" in msg:
        return "empty"
    return "error"


def set_yahoo_discovery_error(meta: dict[str, Any], klass: str) -> str:
    """Persist allowlisted fail class on universe meta (clear junk)."""
    clean = str(klass or "").strip().lower()
    if clean not in YAHOO_FAIL_ERROR_CLASSES:
        clean = "error"
    meta["last_yahoo_discovery_error"] = clean
    return clean


def clear_yahoo_discovery_error(meta: dict[str, Any]) -> None:
    """Drop last-error class after a successful movers snapshot."""
    meta.pop("last_yahoo_discovery_error", None)


def yahoo_discovery_error_class(meta: Any) -> str:
    """Read allowlisted last-error class; unknown / missing → ``\"\"``."""
    if not isinstance(meta, dict):
        return ""
    raw = str(meta.get("last_yahoo_discovery_error") or "").strip().lower()
    if raw in YAHOO_FAIL_ERROR_CLASSES:
        return raw
    return ""


def yahoo_fail_error_vs_seed(error: str, seed_freshness: str) -> str:
    """Typed last-error vs reused-seed extremes (xang1234 #639 + portfolio AI).

    Allowlisted ``empty|thin|timeout|http|error`` alone hid a still-fresh
    reused list on the *first* fail (N× / streak/seed stay silent until ≥2).
    Same polarity as ``yahoo_fail_streak_vs_seed``: fresh seed clashes with a
    typed dead Yahoo; stale seed aligns. Mid ``aging`` / missing class /
    never|unknown stay silent. Returns ``clash · fresh`` / ``align · stale``
    / ``""``.
    """
    klass = str(error or "").strip().lower()
    if klass not in YAHOO_FAIL_ERROR_CLASSES:
        return ""
    band = str(seed_freshness or "").strip().lower()
    if band == "fresh":
        return "clash · fresh"
    if band == "stale":
        return "align · stale"
    return ""


def yahoo_fail_error_vs_fail(error: str, fail_freshness: str) -> str:
    """Typed last-error vs fail-stamp extremes (xang1234 #639 + portfolio AI).

    Allowlisted class alone hid a stale fail stamp on the *first* fail
    (N× / streak/fail stay silent until ≥2). Same polarity as
    ``yahoo_fail_streak_vs_fail``: fresh fail aligns with typed death; stale
    fail clashes (class printed without a live death clock). Mid ``aging`` /
    missing class / never|unknown stay silent. Returns ``align · fresh`` /
    ``clash · stale`` / ``""``.
    """
    klass = str(error or "").strip().lower()
    if klass not in YAHOO_FAIL_ERROR_CLASSES:
        return ""
    band = str(fail_freshness or "").strip().lower()
    if band == "fresh":
        return "align · fresh"
    if band == "stale":
        return "clash · stale"
    return ""


def yahoo_fail_streak_vs_seed(streak: int, seed_freshness: str) -> str:
    """Streak vs reused-seed extremes when N× already spoke (xang1234 #639).

    Chronic ``N×`` beside a still-fresh seed looks healthy; a stale seed with
    a hot streak agrees. Mid ``aging`` / streak <2 / never|unknown stay
    silent. Returns ``clash · fresh`` / ``align · stale`` / ``""``.
    """
    try:
        n = int(streak)
    except (TypeError, ValueError):
        return ""
    if n < 2:
        return ""
    band = str(seed_freshness or "").strip().lower()
    if band == "fresh":
        return "clash · fresh"
    if band == "stale":
        return "align · stale"
    return ""


def yahoo_fail_streak_vs_fail(streak: int, fail_freshness: str) -> str:
    """Streak vs fail-stamp extremes when N× already spoke (xang1234 #639).

    Chronic ``N×`` with a fresh fail stamp agrees (live dead Yahoo). A stale
    fail stamp beside a hot streak clashes — counter kept climbing without a
    live death clock. Mid ``aging`` / streak <2 / never|unknown stay silent.
    Polarity is inverted vs ``yahoo_fail_streak_vs_seed`` (seed fresh = clash).
    Returns ``align · fresh`` / ``clash · stale`` / ``""``.
    """
    try:
        n = int(streak)
    except (TypeError, ValueError):
        return ""
    if n < 2:
        return ""
    band = str(fail_freshness or "").strip().lower()
    if band == "fresh":
        return "align · fresh"
    if band == "stale":
        return "clash · stale"
    return ""


def yahoo_fail_streak_vs_budget(
    streak: int,
    *,
    retry_due: bool,
    retry_remain_sec: int | None,
) -> str:
    """Streak vs fetch-budget spend when N× already spoke (xang1234 #640).

    Chronic ``N×`` alone hid whether discovery is still spending Yahoo fetch
    budget or holding unused capacity in fail backoff. Cooling (remain > 0)
    clashes with a hot streak (counter ≠ live spend). Retry due aligns
    (about to spend / spending again). Streak <2 / missing remain while not
    due stay silent. Returns ``clash · held · not spent`` / ``align · due`` /
    ``""``.
    """
    try:
        n = int(streak)
    except (TypeError, ValueError):
        return ""
    if n < 2:
        return ""
    if retry_due:
        return "align · due"
    try:
        remain = int(retry_remain_sec) if retry_remain_sec is not None else None
    except (TypeError, ValueError):
        return ""
    if remain is not None and remain > 0:
        # xang1234 #642: cooling = reservation not dispatched — speak not spent
        # so held backoff ≠ a live fetch that already burned budget.
        return "clash · held · not spent"
    return ""


def yahoo_fail_streak_seed_vs_fail(
    streak_vs_seed: str,
    streak_vs_fail: str,
) -> tuple[str, bool]:
    """Streak/seed vs streak/fail relationship agreement (display only).

    Returns ``(bit, warn)``. N×↔seed ≠ N×↔fail stamp. When both already
    spoke: same verb speaks ``align · both align|clash`` — ``both align``
    stays calm; ``both clash`` warns (dual-clash agreement ≠ quiet confirm).
    Crossed verbs speak ``clash · seed align|clash · fail align|clash``
    (warn). Missing either stays silent — portfolio AI speak-both-sides +
    soft-allow share/lean parity after streak/seed + streak/fail alone hid
    whether the two relationships agree. Not a gate.
    """
    seed_bit = str(streak_vs_seed or "").strip()
    fail_bit = str(streak_vs_fail or "").strip()
    if not seed_bit or not fail_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    seed_verb = _verb(seed_bit)
    fail_verb = _verb(fail_bit)
    if seed_verb is None or fail_verb is None:
        return "", False
    if seed_verb == fail_verb:
        return f"align · both {seed_verb}", seed_verb == "clash"
    return f"clash · seed {seed_verb} · fail {fail_verb}", True


def yahoo_fail_streak_seed_fail_vs_budget(
    seed_vs_fail: str,
    streak_vs_budget: str,
) -> tuple[str, bool]:
    """Seed/fail meta vs streak/budget agreement (display only).

    Returns ``(bit, warn)``. Seed/fail relationship ≠ fetch-budget hold.
    When both already spoke: same verb speaks ``align · both align|clash``
    — outer ``both clash`` warns; calm ``both align`` warns when seed/fail
    already spoke ``both clash`` and budget is ``due`` (inner dual-clash
    about to spend ≠ quiet confirm; soft-allow share/lean both-clash warn
    parity). Crossed verbs speak
    ``clash · seed/fail align|clash · budget align|clash`` (warn). Missing
    either stays silent — portfolio AI speak-both-sides + soft-allow
    share/lean parity after seed/fail + streak/budget alone hid whether
    the two relationships agree. Not a gate.
    """
    sf_bit = str(seed_vs_fail or "").strip()
    budget_bit = str(streak_vs_budget or "").strip()
    if not sf_bit or not budget_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    sf_verb = _verb(sf_bit)
    budget_verb = _verb(budget_bit)
    if sf_verb is None or budget_verb is None:
        return "", False
    if sf_verb == budget_verb:
        bit = f"align · both {sf_verb}"
        # RyanJHamby + soft-allow both-clash warn: outer both-align can still
        # hide seed/fail dual-clash under retry-due (about to spend Yahoo).
        adverse_due = (
            sf_verb == "align"
            and "both clash" in sf_bit
            and "due" in budget_bit
        )
        return bit, sf_verb == "clash" or adverse_due
    return f"clash · seed/fail {sf_verb} · budget {budget_verb}", True


def yahoo_fail_retry_remaining_sec(
    meta: Any,
    *,
    now: datetime | None = None,
    fail_backoff_hours: int = DEFAULT_YAHOO_FAIL_BACKOFF_HOURS,
) -> int | None:
    """Seconds left on the fail backoff, or ``0`` when retry is due.

    ``None`` when status is not failed or the fail stamp is missing/unparsed
    (caller should treat missing stamp as retry-due immediately).
    """
    if not isinstance(meta, dict):
        return None
    status = str(meta.get("last_yahoo_discovery_status") or "").strip().lower()
    if status != "failed":
        return None
    fail_raw = str(meta.get("last_yahoo_discovery_fail") or "").strip()
    if not fail_raw:
        return None
    try:
        then = datetime.fromisoformat(fail_raw.replace("Z", "+00:00"))
        then = _naive_utc(then)
        clock = _naive_utc(now) if now is not None else datetime.now()
        age_sec = max(0.0, (clock - then).total_seconds())
        limit = max(0, int(fail_backoff_hours)) * 3600.0
        return max(0, int(limit - age_sec))
    except (TypeError, ValueError):
        return None


def yahoo_discovery_due_from_meta(
    meta: Any,
    *,
    now: datetime | None = None,
    max_age_hours: int = DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    fail_backoff_hours: int = DEFAULT_YAHOO_FAIL_BACKOFF_HOURS,
) -> bool:
    """True when movers have never succeeded or last success is older than max_age.

    xang1234: a failed fetch does not inherit the success-age throttle.
    xang1234 dfb6a86: after a failed fetch, wait ``fail_backoff_hours`` before
    retrying (missing fail stamp → retry immediately).
    """
    if not isinstance(meta, dict):
        return True
    status = str(meta.get("last_yahoo_discovery_status") or "").strip().lower()
    if status == "failed":
        remain = yahoo_fail_retry_remaining_sec(
            meta, now=now, fail_backoff_hours=fail_backoff_hours
        )
        # No / bad fail stamp → try again (cannot apply backoff).
        if remain is None:
            return True
        return remain <= 0
    last = str(meta.get("last_yahoo_discovery") or "").strip()
    if not last:
        return True
    try:
        then = datetime.fromisoformat(last.replace("Z", "+00:00"))
        then = _naive_utc(then)
        clock = _naive_utc(now) if now is not None else datetime.now()
        age_h = (clock - then).total_seconds() / 3600.0
        return age_h >= float(max(1, int(max_age_hours)))
    except (TypeError, ValueError):
        return True


def fetch_yahoo_screen_symbols(
    screen: str,
    *,
    count: int = DEFAULT_MOVER_COUNT,
    timeout_sec: int | None = None,
) -> List[str]:
    """
    Return tradeable equity symbols from a yfinance predefined screen.

    Network call — wrap in try/except at call sites. Offline tests should mock.
    xang1234 #639: join ceiling so a hung Yahoo cannot stall the scan loop;
    timeout raises ``TimeoutError`` (not quiet empty).
    """
    import yfinance as yf

    want = max(1, min(100, int(count)))
    limit = (
        DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC
        if timeout_sec is None
        else max(1, int(timeout_sec))
    )
    box: dict[str, Any] = {}

    def _call() -> None:
        try:
            box["payload"] = yf.screen(screen, count=want)
        except Exception as e:
            box["error"] = e

    worker = threading.Thread(target=_call, name=f"yahoo-screen-{screen}", daemon=True)
    worker.start()
    worker.join(timeout=float(limit))
    if worker.is_alive():
        raise TimeoutError(f"yahoo screen {screen} timed out after {limit}s")
    if "error" in box:
        err = box["error"]
        if isinstance(err, TimeoutError):
            raise err
        # xang1234 008f0ca: HTTP 403 / soft block → failed screen, not a raise
        # out of universe refresh.
        raise YahooScreenEmptyError(screen) from err
    payload = box.get("payload")
    if screen_payload_failed(payload, expected=want):
        raise YahooScreenEmptyError(screen)
    out: list[str] = []
    seen: set[str] = set()
    for q in _quotes_from_screen_payload(payload):
        sym = str(q.get("symbol") or "").strip().upper()
        if not sym or sym in seen:
            continue
        if not is_tradeable_symbol(sym):
            continue
        # Skip obvious non-common noise (warrants / units) if any slip through.
        if any(ch in sym for ch in ("=", "^", "/")):
            continue
        seen.add(sym)
        out.append(sym)
    return out


def discover_yahoo_mover_report(
    *,
    screens: Sequence[str] = DEFAULT_SCREENS,
    per_screen: int = DEFAULT_MOVER_COUNT,
    timeout_sec: int | None = None,
) -> tuple[List[str], int, int, int]:
    """Symbols plus screens ok / failed / timed-out (empty/blocked/hang)."""
    out: list[str] = []
    seen: set[str] = set()
    ok = 0
    failed = 0
    timeouts = 0
    for name in screens:
        try:
            batch = fetch_yahoo_screen_symbols(
                name, count=per_screen, timeout_sec=timeout_sec
            )
            ok += 1
        except TimeoutError:
            failed += 1
            timeouts += 1
            continue
        except Exception:
            failed += 1
            continue
        for sym in batch:
            if sym in seen:
                continue
            if not is_tradeable_symbol(sym):
                continue
            seen.add(sym)
            out.append(sym)
    return out, ok, failed, timeouts


def discover_yahoo_mover_symbols(
    *,
    screens: Sequence[str] = DEFAULT_SCREENS,
    per_screen: int = DEFAULT_MOVER_COUNT,
) -> List[str]:
    """Union of symbols across screens, stable order, de-duplicated."""
    symbols, _ok, _failed, _timeouts = discover_yahoo_mover_report(
        screens=screens, per_screen=per_screen
    )
    return symbols


def sector_hint_from_quote(quote: dict[str, Any] | None) -> str:
    if not isinstance(quote, dict):
        return "unknown"
    sector = quote.get("sector")
    if isinstance(sector, str) and sector.strip():
        return sector.strip().lower().replace(" ", "_")
    return "unknown"


def exchange_hint_from_quote(quote: dict[str, Any] | None) -> str:
    if not isinstance(quote, dict):
        return "unknown"
    for key in ("fullExchangeName", "exchange"):
        val = quote.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().upper()
    return "unknown"
