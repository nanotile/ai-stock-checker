"""Book folds screener/AI Group Matrix under details (MonsterDeveloper declutter)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.desk import book_matrix_fold_meta

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "openbb_backend" / "templates" / "desk_book.html"
CSS = ROOT / "openbb_backend" / "static" / "desk.css"

ABOVE_FOLD = (
    ">Slots</span>",
    ">Cash</span>",
    ">Largest</span>",
    ">Mix</span>",
    ">Marks</span>",
    ">Tenure</span>",
    ">Win/Lose</span>",
    ">Size</span>",
    ">Leader</span>",
    ">Venue</span>",
    ">Exit</span>",
    ">Hold</span>",
    ">Scan</span>",
)

INSIDE_DETAILS = (
    ">Session</span>",
    ">Hours</span>",
    ">Rebuy</span>",
    ">Gap</span>",
    ">Post-SL</span>",
    ">Post-TP</span>",
    ">Post-rot</span>",
    ">Post-trim</span>",
    ">Fee</span>",
    ">Buy-c</span>",
    ">Buy-s</span>",
    ">Strat</span>",
    ">Buy-%</span>",
    ">Src</span>",
    ">Cap</span>",
    ">RR</span>",
    ">List</span>",
    ">Score</span>",
    ">Near</span>",
    ">Move</span>",
    ">Vol</span>",
    ">AI</span>",
    ">Conf</span>",
    ">Roles</span>",
)


def test_book_matrix_fold_meta_spoken_inventory() -> None:
    assert book_matrix_fold_meta(None) == ("quiet", False)
    assert book_matrix_fold_meta({}) == ("quiet", False)
    meta, warn = book_matrix_fold_meta(
        {
            "entry_session_marks_ready": True,
            "live_rr_marks_ready": True,
            "live_rr_thin_lots": 0,
            "live_rr_hit_lots": 0,
            "ai_debate_marks_ready": True,
        }
    )
    assert meta == "Session · RR · AI"
    assert warn is False


def test_book_matrix_fold_meta_rr_thin_hit_warn() -> None:
    meta, warn = book_matrix_fold_meta(
        {
            "live_rr_marks_ready": True,
            "live_rr_thin_lots": 2,
            "live_rr_hit_lots": 0,
        }
    )
    assert meta == "RR thin"
    assert warn is True
    meta, warn = book_matrix_fold_meta(
        {
            "live_rr_marks_ready": True,
            "entry_hours_marks_ready": True,
            "live_rr_thin_lots": 1,
            "live_rr_hit_lots": 1,
        }
    )
    assert meta == "Hours · RR hit"
    assert warn is True


def test_book_matrix_honesty_details() -> None:
    text = BOOK.read_text(encoding="utf-8")
    assert "matrix-honesty" in text
    assert 'id="matrix-honesty"' in text
    assert "matrix_meta" in text
    assert "matrix_warn" in text
    open_idx = text.index("matrix-honesty")
    close_idx = text.index("</details>", open_idx)
    above = text[:open_idx]
    body = text[open_idx:close_idx]
    for needle in ABOVE_FOLD:
        assert needle in above, f"{needle} should stay above fold"
        assert needle not in body, f"{needle} must not be inside details"
    for needle in INSIDE_DETAILS:
        assert needle in body, f"{needle} should be inside details"
        assert needle not in above, f"{needle} must not stay above fold"
    assert "Screener &amp; AI marks" in body
    # Static full inventory hid thin subsets — meta chip speaks ready only.
    assert (
        "Session · Hours · Rebuy · Gap · Post-SL · Post-TP · Post-rot · "
        "Post-trim · Fee · Buy-c · Buy-s · Strat · Buy-% · Src · Cap · RR · "
        "List · Score · Near · Move · Vol · AI · Conf · Roles"
    ) not in body


def test_book_matrix_honesty_css() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert ".matrix-honesty" in css
    assert ".matrix-honesty > summary" in css
    assert ".matrix-honesty.warn" in css
